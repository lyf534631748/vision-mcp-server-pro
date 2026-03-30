import { OpenAI } from 'openai';

const DEFAULT_MODELS = [
  'Qwen/Qwen3.5-397B-A17B',
  'Qwen/Qwen3-VL-235B-A22B-Instruct',
  'moonshotai/Kimi-K2.5',
  'Qwen/Qwen3.5-122B-A10B',
];

function parseModelList(): string[] {
  const envModels = process.env.MODELSCOPE_FALLBACK_MODELS;
  if (envModels) {
    return envModels.split(',').map(m => m.trim()).filter(Boolean);
  }
  return DEFAULT_MODELS;
}

export class ChatService {
  private client: OpenAI;
  private models: string[];

  constructor(apiKey: string, model?: string) {
    this.client = new OpenAI({
      baseURL: 'https://api-inference.modelscope.cn/v1',
      apiKey: apiKey,
    });

    const fallbackModels = parseModelList();
    // If a specific model is provided, put it first; otherwise use default list
    if (model) {
      this.models = [model, ...fallbackModels.filter(m => m !== model)];
    } else {
      this.models = fallbackModels;
    }
  }

  async visionCompletions(
    imageUrl: string,
    prompt?: string,
    options: { temperature?: number; topP?: number; maxTokens?: number } = {}
  ): Promise<{ text: string; model: string }> {
    const messages: OpenAI.ChatCompletionMessageParam[] = [
      {
        role: 'user',
        content: [
          { type: 'text', text: prompt || '请描述这张图片的内容' },
          { type: 'image_url' as const, image_url: { url: imageUrl, detail: 'auto' as const } },
        ],
      },
    ];

    const errors: string[] = [];

    for (const model of this.models) {
      try {
        const response = await this.client.chat.completions.create({
          model,
          messages,
          stream: false,
          temperature: options.temperature ?? 0.7,
          top_p: options.topP ?? 1.0,
          ...(options.maxTokens && { max_tokens: options.maxTokens }),
        });

        const result = response.choices[0]?.message?.content;
        if (!result) {
          throw new Error('Invalid API response: missing content');
        }

        if (model !== this.models[0]) {
          process.stderr.write(`[vision-mcp-server-pro] Fallback to model: ${model}\n`);
        }

        return { text: result, model };
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : String(error);
        process.stderr.write(`[vision-mcp-server-pro] Model ${model} failed: ${msg}\n`);
        errors.push(`${model}: ${msg}`);
        continue;
      }
    }

    throw new Error(`All models failed:\n${errors.join('\n')}`);
  }
}
