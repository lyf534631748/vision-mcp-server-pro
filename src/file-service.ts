import fs from 'fs';
import path from 'path';
import { URL } from 'url';

export class FileService {
  static isUrl(source: string): boolean {
    try {
      const url = new URL(source);
      return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
      return false;
    }
  }

  static async encodeImageToBase64(imagePath: string): Promise<string> {
    const imageBuffer = fs.readFileSync(imagePath);
    const mimeType = this.getMimeType(imagePath);
    const base64 = imageBuffer.toString('base64');
    return `data:${mimeType};base64,${base64}`;
  }

  static getMimeType(filePath: string): string {
    const ext = path.extname(filePath).toLowerCase();
    const mimeTypes: Record<string, string> = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
    };
    return mimeTypes[ext] || 'image/jpeg';
  }

  static async validateImageSource(source: string): Promise<{ type: 'url' | 'local'; source: string }> {
    if (this.isUrl(source)) {
      return { type: 'url', source };
    }

    let absolutePath = source;
    if (!path.isAbsolute(source)) {
      absolutePath = path.resolve(process.cwd(), source);
    }

    if (!fs.existsSync(absolutePath)) {
      throw new Error(`Image file not found: ${absolutePath} (original: ${source})`);
    }
    return { type: 'local', source: absolutePath };
  }

  static async processImageInput(imageInput: string): Promise<string> {
    const validatedSource = await this.validateImageSource(imageInput);
    if (validatedSource.type === 'url') {
      return imageInput;
    }
    return await this.encodeImageToBase64(validatedSource.source);
  }
}
