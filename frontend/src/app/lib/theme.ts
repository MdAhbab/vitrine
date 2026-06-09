import { useEffect, useState } from 'react';

type Mode = 'light' | 'dark';

export function useTheme() {
  const [mode, setMode] = useState<Mode>('light');

  useEffect(() => {
    const saved = localStorage.getItem('vitrine-theme') as Mode | null;
    const initial = saved ?? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    setMode(initial);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', mode === 'dark');
    localStorage.setItem('vitrine-theme', mode);
  }, [mode]);

  return {
    mode,
    toggle: () => setMode((m) => (m === 'light' ? 'dark' : 'light')),
  };
}
