# vision-mcp-server-pro

MCP server for vision capabilities with **automatic model fallback** via ModelScope API.

## Features

- Analyze images via URL or local file path
- **Automatic model fallback**: when the primary model hits rate limits, it automatically tries the next model
- Configurable model list via environment variables

## Default Model List (fallback order)

1. `Qwen/Qwen3.5-397B-A17B`
2. `Qwen/Qwen3-VL-235B-A22B-Instruct`
3. `moonshotai/Kimi-K2.5`
4. `Qwen/Qwen3.5-122B-A10B`

## Usage

Add to your MCP client (e.g., Claude Code) using **uvx** (no global install needed):

```bash
claude mcp add vision-mcp-server-pro --scope user \
  -e MODELSCOPE_TOKEN=your_token_here \
  -- uvx vision-mcp-server-pro
```

## Environment Variables

使用前，需要设置以下环境变量：

| Variable | Required | Description |
|----------|----------|-------------|
| `MODELSCOPE_TOKEN` | Yes | 魔搭社区的 API 密钥 |
| `MODELSCOPE_MODEL` | No | 首选模型（默认使用回落列表中的第一个） |
| `MODELSCOPE_FALLBACK_MODELS` | No | 自定义回落模型列表，逗号分隔（覆盖默认列表） |

### 获取 MODELSCOPE_TOKEN

访问 [魔搭社区](https://modelscope.cn/) → 个人中心 → API令牌

### Specify Primary Model

```bash
claude mcp add vision-mcp-server-pro --scope user \
  -e MODELSCOPE_TOKEN=your_token_here \
  -e MODELSCOPE_MODEL=Qwen/Qwen3-VL-235B-A22B-Instruct \
  -- uvx vision-mcp-server-pro
```

### Custom Fallback Models

```bash
claude mcp add vision-mcp-server-pro --scope user \
  -e MODELSCOPE_TOKEN=your_token_here \
  -e MODELSCOPE_FALLBACK_MODELS="Qwen/Qwen3.5-397B-A17B,Qwen/Qwen3-VL-235B-A22B-Instruct" \
  -- uvx vision-mcp-server-pro
```

## Tool

The server provides an `analyze_image` tool:

- **`image`** (required): Image URL or local file path
- **`prompt`** (optional): Question or analysis request (default: "请描述这张图片的内容")

## License

MIT
