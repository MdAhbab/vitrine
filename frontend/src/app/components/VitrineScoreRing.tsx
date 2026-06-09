export function VitrineScoreRing({ score, size = 64, label = true }: { score: number; size?: number; label?: boolean }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - score / 100);
  return (
    <div className="inline-flex items-center gap-2.5" title={`Vitrine Score · ${score}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--border-c)" strokeWidth="2" fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="var(--accent)"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 700ms cubic-bezier(.22,1,.36,1)' }}
        />
        <text
          x="50%" y="50%"
          textAnchor="middle"
          dominantBaseline="central"
          transform={`rotate(90 ${size / 2} ${size / 2})`}
          className="font-mono tabular"
          style={{ fontSize: size * 0.28, fill: 'var(--text)' }}
        >
          {score}
        </text>
      </svg>
      {label && (
        <div className="leading-tight">
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted">Vitrine Score</div>
          <div className="text-xs text-text-muted">out of 100</div>
        </div>
      )}
    </div>
  );
}
