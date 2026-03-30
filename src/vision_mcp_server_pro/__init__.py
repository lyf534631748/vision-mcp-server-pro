import os
import sys
import base64
from pathlib import Path
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_MODELS = [
    "Qwen/Qwen3.5-397B-A17B",
    "Qwen/Qwen3-VL-235B-A22B-Instruct",
    "moonshotai/Kimi-K2.5",
    "Qwen/Qwen3.5-122B-A10B",
]

MODELSCOPE_TOKEN = os.environ.get("MODELSCOPE_TOKEN", "")
MODELSCOPE_MODEL = os.environ.get("MODELSCOPE_MODEL", "")
FALLBACK_MODELS_ENV = os.environ.get("MODELSCOPE_FALLBACK_MODELS", "")

if not MODELSCOPE_TOKEN:
    print("Error: MODELSCOPE_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)


def get_model_list() -> list[str]:
    if FALLBACK_MODELS_ENV:
        models = [m.strip() for m in FALLBACK_MODELS_ENV.split(",") if m.strip()]
    else:
        models = DEFAULT_MODELS.copy()
    if MODELSCOPE_MODEL:
        models = [MODELSCOPE_MODEL] + [m for m in models if m != MODELSCOPE_MODEL]
    return models


MODELS = get_model_list()

mcp = FastMCP("vision-mcp-server-pro")


def is_url(source: str) -> bool:
    try:
        result = urlparse(source)
        return result.scheme in ("http", "https")
    except Exception:
        return False


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
        resp.raise_for_status()
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

    for model in MODELS:
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

    return f"All models failed:\n" + "\n".join(errors)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
