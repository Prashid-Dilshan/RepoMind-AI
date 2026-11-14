import { readText, writeText } from './storage.js';

const KEY = 'repomind.theme';

export function initialTheme() {
  const saved = readText(KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  writeText(KEY, theme);
}
