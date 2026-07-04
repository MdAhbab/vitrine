import { useEffect, useState } from 'react';

type Mode = 'light' | 'dark';

const STORAGE_KEY = 'vitrine-theme';

// Single module-level source of truth so every useTheme() instance (TopNav
// toggle, App, Profile preferences) stays in sync. The pre-paint init script
// in index.html applies the class before React mounts, so there is no flash.
function readInitial(): Mode {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

let current: Mode = typeof window !== 'undefined' ? readInitial() : 'light';
if (typeof window !== 'undefined') {
  // Normally a no-op (index.html applies it pre-paint); kept as a fallback.
  document.documentElement.classList.toggle('dark', current === 'dark');
}
const listeners = new Set<(m: Mode) => void>();

export function setTheme(mode: Mode) {
  current = mode;
  document.documentElement.classList.toggle('dark', mode === 'dark');
  localStorage.setItem(STORAGE_KEY, mode);
  listeners.forEach((fn) => fn(mode));
}

export function useTheme() {
  const [mode, setMode] = useState<Mode>(current);

  useEffect(() => {
    listeners.add(setMode);
    return () => {
      listeners.delete(setMode);
    };
  }, []);

  return {
    mode,
    setTheme,
    toggle: () => setTheme(current === 'light' ? 'dark' : 'light'),
  };
}
