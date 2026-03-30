#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { registerImageAnalysisTool } from './image-analysis-service.js';

const MODELSCOPE_TOKEN = process.env.MODELSCOPE_TOKEN;
const MODELSCOPE_MODEL = process.env.MODELSCOPE_MODEL;

if (!MODELSCOPE_TOKEN) {
  process.stderr.write('Error: MODELSCOPE_TOKEN environment variable is not set.\n');
  process.exit(1);
}

const apiKey = MODELSCOPE_TOKEN;
const model = MODELSCOPE_MODEL;

class McpServerApplication {
  private server: Server;

  constructor() {
    this.server = new Server({
      name: 'vision-mcp-server-pro',
      version: '1.0.0',
      capabilities: { tools: {} },
    });
    this.setupErrorHandling();
  }

  async registerTools(): Promise<void> {
    registerImageAnalysisTool(this.server, apiKey, model);
  }

  private setupErrorHandling(): void {
    process.on('uncaughtException', (error: Error) => {
      process.stderr.write(`Uncaught exception: ${error.message}\n`);
      process.exit(1);
    });

    process.on('unhandledRejection', (reason: unknown) => {
      process.stderr.write(`Unhandled rejection: ${reason instanceof Error ? reason.message : String(reason)}\n`);
      process.exit(1);
    });

    process.on('SIGINT', () => {
      process.stderr.write('Received SIGINT, shutting down...\n');
      process.exit(0);
    });

    process.on('SIGTERM', () => {
      process.stderr.write('Received SIGTERM, shutting down...\n');
      process.exit(0);
    });
  }

  async start(): Promise<void> {
    await this.registerTools();
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    process.stderr.write('[vision-mcp-server-pro] Server started\n');
  }
}

async function main(): Promise<void> {
  try {
    const app = new McpServerApplication();
    await app.start();
  } catch (error: unknown) {
    process.stderr.write(`Application startup failed: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }
}

main();
