import { Check, Sparkles, Award, Radio } from 'lucide-react';

const map = {
  verified: { label: 'Verified', icon: Check },
  'best-ui': { label: 'Best UI', icon: Award },
  new: { label: 'New', icon: Sparkles },
  'live-demo': { label: 'Live demo', icon: Radio },
} as const;

export function Badge({ kind, overlay = false }: { kind: keyof typeof map; overlay?: boolean }) {
  const { label, icon: Icon } = map[kind];
  const isAccent = kind === 'best-ui';

  if (overlay && (kind === 'verified' || kind === 'live-demo')) {
    return (
      <span
        className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em] px-2 py-1 rounded-full border border-white/50 text-white mix-blend-difference"
      >
        <Icon size={10} strokeWidth={2} />
        {label}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em] px-2 py-1 rounded-full hairline ${
        isAccent ? 'text-accent border-accent/40' : 'text-text-muted'
      }`}
    >
      <Icon size={10} strokeWidth={2} />
      {label}
    </span>
  );
}

