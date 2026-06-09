import { useEffect, useState } from 'react';

export function Typewriter({
  words,
  speed = 60,
  pause = 1400,
  className = '',
}: { words: string[]; speed?: number; pause?: number; className?: string }) {
  const [wi, setWi] = useState(0);
  const [text, setText] = useState('');
  const [phase, setPhase] = useState<'typing' | 'holding' | 'erasing'>('typing');

  useEffect(() => {
    const w = words[wi % words.length];
    let t: number;
    if (phase === 'typing') {
      if (text.length < w.length) t = window.setTimeout(() => setText(w.slice(0, text.length + 1)), speed);
      else t = window.setTimeout(() => setPhase('holding'), pause);
    } else if (phase === 'holding') {
      t = window.setTimeout(() => setPhase('erasing'), pause);
    } else {
      if (text.length > 0) t = window.setTimeout(() => setText(text.slice(0, -1)), speed / 1.8);
      else {
        setPhase('typing');
        setWi((i) => i + 1);
        t = 0;
      }
    }
    return () => clearTimeout(t);
  }, [text, phase, wi, words, speed, pause]);

  return (
    <span className={className}>
      {text}
      <span className="inline-block w-[2px] h-[1em] align-[-2px] ml-0.5 bg-current opacity-80 animate-[blink_1s_steps(2,end)_infinite]" />
      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
    </span>
  );
}

export function ShimmerText({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`bg-clip-text text-transparent ${className}`}
      style={{
        backgroundImage:
          'linear-gradient(90deg, var(--text) 0%, var(--accent) 35%, var(--text) 70%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 3.6s linear infinite',
      }}
    >
      {children}
      <style>{`@keyframes shimmer { to { background-position: -200% 0; } }`}</style>
    </span>
  );
}
