import { z } from 'zod';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { FileService } from './file-service.js';
import { ChatService } from './chat-service.js';
import type { Server } from '@modelcontextprotocol/sdk/server/index.js';

const AnalyzeImageParamsSchema = z.object({
  image: z.string().describe('图片URL或本地文件路径'),
  prompt: z.string().optional().default('请描述这张图片的内容').describe('对图片的问题或分析要求'),
});

export function registerImageAnalysisTool(server: Server, apiKey: string, model?: string): void {
  const chatService = new ChatService(apiKey, model);

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: 'analyze_image',
        description: '分析图片内容并提供详细描述，支持自动模型回落',
        inputSchema: {
          type: 'object',
          properties: {
            image: {
              type: 'string',
              description: '图片URL或本地文件路径',
            },
            prompt: {
              type: 'string',
              description: '对图片的问题或分析要求',
              default: '请描述这张图片的内容',
            },
          },
          required: ['image'],
        },
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (name === 'analyze_image') {
      try {
        const validatedParams = AnalyzeImageParamsSchema.parse(args);
        const imageUrl = await FileService.processImageInput(validatedParams.image);
        const result = await chatService.visionCompletions(imageUrl, validatedParams.prompt);

        return {
          content: [
            {
              type: 'text' as const,
              text: result.text,
            },
          ],
        };
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : String(error);
        process.stderr.write(`[vision-mcp-server-pro] Error: ${msg}\n`);
        return {
          content: [{ type: 'text' as const, text: `分析图片时出错: ${msg}` }],
          isError: true,
        };
      }
    }

    return {
      content: [{ type: 'text' as const, text: `未知工具: ${name}` }],
      isError: true,
    };
  });
}
