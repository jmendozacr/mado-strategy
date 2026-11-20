import { randomUUID } from 'node:crypto';
import { defineConfig } from '@playwright/test';

const journal = `../runtime/playwright-e2e-${randomUUID()}.jsonl`;

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    channel: 'msedge',
    viewport: { width: 1366, height: 768 },
  },
  webServer: [
    {
      command: `python ../server.py --port 8766 --journal ${journal}`,
      url: 'http://127.0.0.1:8766/api/health',
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
});
