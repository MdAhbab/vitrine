export function Logo({ size = 22 }: { size?: number }) {
  return (
    <a href="#/" className="flex items-center gap-2.5 group">
      <svg width={size} height={size} viewBox="0 0 32 32" fill="none" className="text-text">
        <rect x="3" y="6" width="26" height="20" rx="3.5" stroke="currentColor" strokeWidth="1.4" />
        <rect x="7" y="10" width="18" height="12" rx="1.5" stroke="currentColor" strokeWidth="1" opacity="0.55" />
        <circle cx="16" cy="16" r="1.6" fill="var(--accent)" />
      </svg>
      <span className="font-serif tracking-[-0.02em]" style={{ fontSize: size + 2 }}>
        vitrine
      </span>
    </a>
  );
}
