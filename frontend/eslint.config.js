import eslint from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...svelte.configs['flat/recommended'],
  {
    files: ['**/*.svelte', '**/*.svelte.ts'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser
      }
    }
  },
  {
    // TypeScript already reports undefined names, including browser globals.
    rules: { 'no-undef': 'off' }
  },
  {
    ignores: ['.svelte-kit/**', 'build/**', 'node_modules/**', 'test-results/**']
  }
);
