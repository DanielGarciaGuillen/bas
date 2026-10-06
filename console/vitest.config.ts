import path from 'node:path';

import { defineConfig } from 'vitest/config';

// Mirrors vite.config.ts / tsconfig.json's "@/*" -> "./src/*" alias so tests import the
// same way application code does.
export default defineConfig({
    resolve: {
        alias: {
            '@': path.resolve(import.meta.dirname, './src')
        }
    },
    test: {
        coverage: {
            provider: 'v8',
            reporter: ['text', 'lcov', 'json']
        }
    }
});
