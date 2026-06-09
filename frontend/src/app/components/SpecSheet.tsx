import { Sparkles } from 'lucide-react';
import type { SpecSection } from '../lib/mockData';

export function SpecSheet({ sections }: { sections: SpecSection[] }) {
  return (
    <div className="hairline rounded-2xl overflow-hidden bg-surface">
      <div className="px-6 py-4 border-b flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Document</div>
          <h3 className="font-serif text-xl">Spec sheet</h3>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted flex items-center gap-2">
          <Sparkles size={11} className="text-accent" />
          AI-assisted
        </div>
      </div>
      <dl>
        {sections.map((sec) => (
          <section key={sec.title} className="border-b last:border-b-0">
            <div className="grid grid-cols-1 md:grid-cols-[180px_1fr]">
              <div className="px-6 py-4 bg-surface-2/50 border-b md:border-b-0 md:border-r">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Section</div>
                <div className="font-serif text-base mt-1">{sec.title}</div>
              </div>
              <div>
                {sec.fields.map((f, i) => (
                  <div key={f.label} className={`grid grid-cols-[160px_1fr] gap-4 px-6 py-3 ${i !== 0 ? 'border-t' : ''}`}>
                    <dt className="font-mono text-[11px] uppercase tracking-wider text-text-muted self-center">{f.label}</dt>
                    <dd className="flex items-start justify-between gap-3 text-sm">
                      <span>{f.value}</span>
                      {f.auto && (
                        <span
                          className={`font-mono text-[10px] uppercase tracking-wider shrink-0 mt-0.5 ${
                            f.confidence === 'low' ? 'text-danger' : f.confidence === 'med' ? 'text-text-muted' : 'text-accent'
                          }`}
                        >
                          ✦ auto · {f.confidence ?? 'high'}
                        </span>
                      )}
                    </dd>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ))}
      </dl>
    </div>
  );
}
