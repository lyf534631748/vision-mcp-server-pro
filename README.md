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

## Installation

```bash
npm install -g vision-mcp-server-pro
```

## Configuration

Add to your MCP client (e.g., Claude Code):

```bash
claude mcp add vision-mcp-server-pro --scope user \
  -e MODELSCOPE_TOKEN=your_token_here \
  -e MODELSCOPE_MODEL=Qwen/Qwen3.5-397B-A17B \
  -- vision-mcp-server-pro
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MODELSCOPE_TOKEN` | Yes | Your ModelScope API token |
| `MODELSCOPE_MODEL` | No | Primary model (defaults to first in fallback list) |
| `MODELSCOPE_FALLBACK_MODELS` | No | Comma-separated fallback model list (overrides defaults) |

### Custom Fallback Models

```bash
-e MODELSCOPE_FALLBACK_MODELS="ModelA,ModelB,ModelC"
```

## Usage

The server provides an `analyze_image` tool:

- **`image`** (required): Image URL or local file path
- **`prompt`** (optional): Question or analysis request (default: "请描述这张图片的内容")

## License

MIT
