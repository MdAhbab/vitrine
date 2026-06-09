import { motion } from 'motion/react';
import { ArrowRight, Sparkles, ChevronRight } from 'lucide-react';
import { CATEGORIES, type Product } from '../lib/mockData';
import { useCatalogProducts } from '../lib/store';
import { ProductCard } from '../components/ProductCard';

export function Home({
  onOpenProduct,
  onPreview,
  onConcierge,
  onBrowse,
  onBargain,
}: {
  onOpenProduct: (slug: string) => void;
  onPreview: (p: Product) => void;
  onConcierge: () => void;
  onBrowse: () => void;
  onBargain: (p: Product) => void;
}) {
  const products = useCatalogProducts();
  const top = [...products].sort((a, b) => b.vitrineScore - a.vitrineScore);
  const featured = top[0];
  const bestUi = Array.from(
    new Map(
      [...top.filter((p) => p.badges.includes('best-ui')), ...top].map((p) => [p.id, p])
    ).values()
  ).slice(0, 6);
  const newThisWeek = [...products].sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)).slice(0, 6);

  return (
    <main className="relative">
      {/* Hero — editorial split */}
      <section className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-10 sm:pt-14 lg:pt-20 pb-16 sm:pb-24">
        <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-12 lg:gap-20 items-end">
          <motion.div
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center gap-3 mb-6 font-mono text-[10px] uppercase tracking-[0.3em] text-text-muted">
              <span className="w-8 h-px bg-accent" />
              Curated · Issue 06 / 2026
            </div>
            <h1 className="font-serif leading-[0.95]">
              Try the software.<br />
              <em className="text-accent not-italic">Then own it.</em>
            </h1>
            <p className="mt-8 max-w-xl leading-relaxed text-lg" style={{ color: 'var(--text-soft)' }}>
              Vitrine is a boutique gallery for production-ready software. Every piece ships with a live, runnable preview — held under glass and the light — so you can decide with your eyes before you decide with your wallet.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <button
                onClick={onBrowse}
                className="bg-text text-bg rounded-full pl-5 pr-6 h-12 text-sm font-medium inline-flex items-center gap-2 hover:opacity-90 transition-opacity"
              >
                Enter the gallery <ArrowRight size={14} />
              </button>
              <button
                onClick={onConcierge}
                className="hairline rounded-full pl-4 pr-5 h-12 text-sm inline-flex items-center gap-2 hover:border-accent hover:text-accent transition-colors"
              >
                <Sparkles size={14} /> Ask the Concierge
              </button>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
            className="relative"
          >
            <div className="relative aspect-[5/6] rounded-2xl overflow-hidden hairline bg-surface">
              {featured ? (
                <>
                  <img src={featured.cover} alt="" className="w-full h-full object-cover" />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
                  <div className="absolute top-5 left-5 right-5 flex items-center justify-between text-white/90 font-mono text-[10px] uppercase tracking-[0.25em]">
                    <span className="flex items-center gap-2"><span className="live-dot" /> Now showing</span>
                    <span>#001 / 2026</span>
                  </div>
                  <div className="absolute bottom-5 left-5 right-5 text-white">
                    <div className="font-serif text-4xl">{featured.name}</div>
                    <div className="text-sm opacity-85 mt-1.5">{featured.tagline}</div>
                    <div className="mt-5 flex items-center justify-between gap-2">
                      <button
                        onClick={() => onPreview(featured)}
                        className="bg-accent text-[var(--accent-ink)] rounded-full pl-3 pr-4 h-10 text-sm font-medium inline-flex items-center gap-1.5"
                      >
                        <Sparkles size={13} /> Open the vitrine
                      </button>
                      <button onClick={() => onOpenProduct(featured.slug)} className="text-sm opacity-90 border-b border-white/40">
                        View piece →
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="absolute inset-0 grid place-items-center p-8 text-center">
                  <div>
                    <div className="font-serif text-3xl">Catalog is empty</div>
                    <div className="text-sm text-text-soft mt-2">No listings are live yet. Add or seed listings to populate the gallery.</div>
                  </div>
                </div>
              )}
            </div>
            <div className="absolute -bottom-6 -left-6 hidden md:block hairline rounded-xl bg-surface px-4 py-3 shadow-2xl">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Vitrine Score</div>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span className="font-serif text-3xl tabular">{featured?.vitrineScore ?? '--'}</span>
                <span className="text-xs text-text-muted">/ 100</span>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Concierge bar */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="mt-20 max-w-2xl"
        >
          <button
            onClick={onConcierge}
            className="group w-full text-left bg-surface hairline rounded-2xl p-2 flex items-center gap-3 hover:border-accent transition-colors"
          >
            <span className="w-11 h-11 grid place-items-center rounded-xl gold-gradient text-[var(--accent-ink)] shrink-0">
              <Sparkles size={16} />
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm">Describe what you need…</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted mt-0.5">Concierge · streamed in real time</div>
            </div>
            <span className="hidden sm:flex items-center gap-1.5 text-text-muted pr-3">
              <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
            </span>
          </button>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {CATEGORIES.slice(0, 8).map((c) => (
              <button key={c} onClick={onBrowse} className="font-mono text-[10px] uppercase tracking-wider px-2.5 py-1.5 hairline rounded-full text-text-soft hover:text-accent hover:border-accent transition-colors">
                {c}
              </button>
            ))}
          </div>
        </motion.div>

      </section>

      <hr className="editorial-rule max-w-[1400px] mx-auto" />

      {/* Top of the gallery rail */}
      <Rail title="Top of the Gallery" eyebrow="Highest Vitrine Score" items={top.slice(0, 8)} onOpen={onOpenProduct} onPreview={onPreview} onBargain={onBargain} />

      {/* Best UI editorial grid */}
      <section className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-16">
        <Header eyebrow="Curatorial pick" title="Best UI, this quarter" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-10">
          {bestUi.slice(0, 6).map((p) => (
            <ProductCard key={p.id} product={p} onOpen={() => onOpenProduct(p.slug)} onPreview={() => onPreview(p)} onBargain={() => onBargain(p)} />
          ))}
        </div>
      </section>

      <hr className="editorial-rule max-w-[1400px] mx-auto" />

      {/* Built this week */}
      <Rail title="Built this week" eyebrow="New on the floor" items={newThisWeek} onOpen={onOpenProduct} onPreview={onPreview} onBargain={onBargain} />

      {/* Categories editorial block */}
      <section className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-20">
        <Header eyebrow="By department" title="Wander the floor" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border-c mt-10 hairline rounded-2xl overflow-hidden">
          {CATEGORIES.map((c) => {
            const count = products.filter((p) => p.category === c).length;
            return (
              <button
                key={c}
                onClick={onBrowse}
                className="bg-surface hover:bg-surface-2 p-8 text-left transition-colors group"
              >
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{String(CATEGORIES.indexOf(c) + 1).padStart(2, '0')}</div>
                <div className="font-serif text-2xl mt-3 flex items-center justify-between">
                  {c}
                  <ChevronRight size={18} className="text-text-muted group-hover:text-accent group-hover:translate-x-1 transition-all" />
                </div>
                <div className="text-xs text-text-muted mt-2">{count || '—'} pieces on display</div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Closing manifesto */}
      <section className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-24 grid lg:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted">Manifesto</div>
        <div>
          <h2 className="font-serif">
            Software, framed like the objects it is.
          </h2>
          <p className="mt-8 text-text-soft leading-relaxed max-w-2xl">
            We believe a great app deserves the same treatment as a great print — a clean wall, generous margins, a label that respects you. Vitrine exists to slow you down for the thirty seconds it takes to notice what a piece of software actually does. Try it. Turn it over. Then decide.
          </p>
          <div className="mt-8 font-mono text-xs tracking-widest text-text-muted">— The curators</div>
        </div>
      </section>
    </main>
  );
}

function Header({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-6 flex-wrap">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">{eyebrow}</div>
        <h2 className="font-serif mt-2">{title}</h2>
      </div>
      {action}
    </div>
  );
}

function Rail({
  title, eyebrow, items, onOpen, onPreview, onBargain,
}: {
  title: string; eyebrow: string; items: Product[];
  onOpen: (slug: string) => void; onPreview: (p: Product) => void; onBargain: (p: Product) => void;
}) {
  return (
    <section className="py-16">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 mb-8">
        <Header eyebrow={eyebrow} title={title} />
      </div>
      <div className="scroll-rail flex gap-5 overflow-x-auto px-6 lg:px-10 pb-4 max-w-[1400px] mx-auto">
        {items.map((p) => (
          <div key={p.id} className="w-[300px] sm:w-[340px] shrink-0">
            <ProductCard product={p} onOpen={() => onOpen(p.slug)} onPreview={() => onPreview(p)} onBargain={() => onBargain(p)} />
          </div>
        ))}
      </div>
    </section>
  );
}
