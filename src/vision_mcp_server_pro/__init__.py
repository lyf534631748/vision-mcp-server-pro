import os
import sys
import base64
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from PIL import Image
import io

# 按视觉能力从高到低排序：VL专用大模型 > VL中型 > VL小型 > 通用大模型 > 通用中型
DEFAULT_MODELS = [
    "Qwen/Qwen3-VL-235B-A22B-Instruct",      # 235B VL旗舰
    "Shanghai_AI_Laboratory/Intern-S1-Pro",    # 多模态科学推理
    "Qwen/Qwen3-VL-30B-A3B-Instruct",         # 30B VL
    "Qwen/Qwen3-VL-8B-Thinking",              # 8B VL+推理
    "Qwen/Qwen3-VL-8B-Instruct",              # 8B VL基础
    "Qwen/Qwen3.5-122B-A10B",                 # 122B 通用
    "Qwen/Qwen3.5-35B-A3B",                   # 35B 通用
    "Qwen/Qwen3.5-27B",                       # 27B 通用
]

MODELSCOPE_TOKEN = os.environ.get("MODELSCOPE_TOKEN", "")
MODELSCOPE_MODEL = os.environ.get("MODELSCOPE_MODEL", "")
FALLBACK_MODELS_ENV = os.environ.get("MODELSCOPE_FALLBACK_MODELS", "")

if not MODELSCOPE_TOKEN:
    print("Error: MODELSCOPE_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)

CST = timezone(timedelta(hours=8))


def get_model_list() -> list[str]:
    if FALLBACK_MODELS_ENV:
        models = [m.strip() for m in FALLBACK_MODELS_ENV.split(",") if m.strip()]
    else:
        models = DEFAULT_MODELS.copy()
    if MODELSCOPE_MODEL:
        models = [MODELSCOPE_MODEL] + [m for m in models if m != MODELSCOPE_MODEL]
    return models


MODELS = get_model_list()

# 当日额度耗尽的模型黑名单: {model_id: expire_timestamp}
_exhausted_models: dict[str, float] = {}

mcp = FastMCP("vision-mcp-server-pro")


def _quota_reset_ts() -> float:
    """返回额度重置时间戳（次日凌晨3点北京时间）
    如果当前时间已过凌晨3点，返回明天凌晨3点；否则返回今天凌晨3点。
    边界情况：23:50耗尽额度 -> 次日3:00重置，而非当天3:00。
    """
    now_cst = datetime.now(CST)
    target = now_cst.replace(hour=3, minute=0, second=0, microsecond=0)
    if target <= now_cst:
        # 已过今天3点，重置时间在明天3点
        from datetime import timedelta as _td
        target += _td(days=1)
    return target.timestamp()


def _cleanup_expired() -> None:
    """清除已过期的黑名单条目"""
    now = time.time()
    expired = [k for k, v in _exhausted_models.items() if v <= now]
    for k in expired:
        del _exhausted_models[k]


def mark_exhausted(model: str) -> None:
    """将模型标记为今日额度耗尽"""
    _exhausted_models[model] = _quota_reset_ts()
    print(f"[vision-mcp-server-pro] Model {model} quota exhausted, blacklisted until end of day", file=sys.stderr)


def is_exhausted(model: str) -> bool:
    """检查模型是否在今日黑名单中"""
    _cleanup_expired()
    return model in _exhausted_models


def is_url(source: str) -> bool:
    try:
        result = urlparse(source)
        return result.scheme in ("http", "https")
    except Exception:
        return False


MAX_BASE64_SIZE = 4 * 1024 * 1024  # 4MB base64 limit (ModelScope 5MB with margin)
MAX_RESOLUTION = 2048  # ModelScope API max dimension

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}


def _compress_image(data: bytes) -> tuple[bytes, str]:
    """Compress image: first ensure resolution within MAX_RESOLUTION, then size within MAX_BASE64_SIZE.
    Returns (compressed_bytes, mime_type).
    """
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    orig_w, orig_h = img.size
    print(f"[vision-mcp-server-pro] Image compression: original size {orig_w}x{orig_h}, "
          f"file {len(data)} bytes", file=sys.stderr)

    # Step 1: Resolution check - scale down if width or height exceeds MAX_RESOLUTION
    if orig_w > MAX_RESOLUTION or orig_h > MAX_RESOLUTION:
        ratio = min(MAX_RESOLUTION / orig_w, MAX_RESOLUTION / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        print(f"[vision-mcp-server-pro] Resolution {orig_w}x{orig_h} exceeds {MAX_RESOLUTION}, "
              f"scaling to {new_w}x{new_h}", file=sys.stderr)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        orig_w, orig_h = new_w, new_h

    # Step 2: File size compression loop
    scale = 1.0
    quality = 85
    while True:
        buf = io.BytesIO()
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        resized.save(buf, format="JPEG", quality=quality)
        compressed = buf.getvalue()
        b64_size = len(base64.b64encode(compressed))
        print(f"[vision-mcp-server-pro] Compressed to {new_w}x{new_h} (scale={scale:.2f}), "
              f"file {len(compressed)} bytes, base64 ~{b64_size} bytes", file=sys.stderr)
        if b64_size <= MAX_BASE64_SIZE:
            break
        scale *= 0.75
        if scale < 0.05:
            break

    return compressed, "image/jpeg"


def encode_image_to_base64(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    data = path.read_bytes()

    # Auto-compress if resolution exceeds limit OR base64 would exceed size limit
    if ext in IMAGE_EXTENSIONS:
        needs_compress = False
        # Check resolution
        try:
            with Image.open(io.BytesIO(data)) as probe:
                w, h = probe.size
                if w > MAX_RESOLUTION or h > MAX_RESOLUTION:
                    print(f"[vision-mcp-server-pro] Resolution check: {w}x{h} exceeds {MAX_RESOLUTION}", file=sys.stderr)
                    needs_compress = True
        except Exception:
            pass
        # Check size
        estimated_b64 = len(data) * 4 // 3
        if estimated_b64 > MAX_BASE64_SIZE:
            needs_compress = True
        if needs_compress:
            data, mime_type = _compress_image(data)

    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def resolve_image(image: str) -> str:
    if is_url(image):
        return image
    return encode_image_to_base64(image)


def call_modelscope_api(model: str, image_url: str, prompt: str) -> str:
    url = "https://api-inference.modelscope.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MODELSCOPE_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "stream": False,
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            body = resp.text[:500]
            print(f"[vision-mcp-server-pro] API error {resp.status_code} from {model}: {body}", file=sys.stderr)

        # 429 = 限额耗尽，标记为当日黑名单
        if resp.status_code == 429:
            mark_exhausted(model)
            raise Exception(f"Rate limit exceeded (429) for {model}")

        if resp.status_code >= 400:
            raise Exception(f"HTTP {resp.status_code} from {model}: {body}")

        data = resp.json()

    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise ValueError(f"Invalid API response from {model}: missing content")
    return content


@mcp.tool()
def analyze_image(image: str, prompt: str = "请描述这张图片的内容") -> str:
    """分析图片内容并提供详细描述，支持自动模型回落

    Args:
        image: 图片URL或本地文件路径
        prompt: 对图片的问题或分析要求
    """
    image_url = resolve_image(image)
    errors: list[str] = []
    skipped: list[str] = []

    for model in MODELS:
        # 跳过今日已耗尽额度的模型
        if is_exhausted(model):
            skipped.append(model)
            continue
        try:
            result = call_modelscope_api(model, image_url, prompt)
            if model != MODELS[0]:
                print(f"[vision-mcp-server-pro] Fallback to model: {model}", file=sys.stderr)
            return result
        except Exception as e:
            msg = str(e)
            print(f"[vision-mcp-server-pro] Model {model} failed: {msg}", file=sys.stderr)
            errors.append(f"{model}: {msg}")
            continue

    parts = []
    if skipped:
        parts.append(f"Skipped (quota exhausted today): {', '.join(skipped)}")
    if errors:
        parts.append("Errors:\n" + "\n".join(errors))
    return "All models failed.\n" + "\n".join(parts)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
