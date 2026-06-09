import { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { SlidersHorizontal, X } from 'lucide-react';
import { PRODUCTS, CATEGORIES, type Product } from '../lib/mockData';
import { ProductCard } from '../components/ProductCard';

type Sort = 'score' | 'new' | 'price' | 'rating';

export function Browse({ onOpenProduct, onPreview, onBargain }: { onOpenProduct: (slug: string) => void; onPreview: (p: Product) => void; onBargain: (p: Product) => void }) {
  const [cats, setCats] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState(50000);
  const [hasDemo, setHasDemo] = useState(false);
  const [framework, setFramework] = useState<string>('All');
  const [sort, setSort] = useState<Sort>('score');
  const [openFilters, setOpenFilters] = useState(false);

  const frameworks = useMemo(() => ['All', ...Array.from(new Set(PRODUCTS.map((p) => p.framework)))], []);

  const filtered = useMemo(() => {
    let r = PRODUCTS.filter((p) => p.price <= maxPrice);
    if (cats.length) r = r.filter((p) => cats.includes(p.category));
    if (hasDemo) r = r.filter((p) => p.hasLiveDemo);
    if (framework !== 'All') r = r.filter((p) => p.framework === framework);
    switch (sort) {
      case 'score': r.sort((a, b) => b.vitrineScore - a.vitrineScore); break;
      case 'new': r.sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt)); break;
      case 'price': r.sort((a, b) => a.price - b.price); break;
      case 'rating': r.sort((a, b) => b.rating - a.rating); break;
    }
    return r;
  }, [cats, maxPrice, hasDemo, framework, sort]);

  const toggleCat = (c: string) => setCats((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  const Filters = (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-3">Category</div>
        <div className="space-y-1.5">
          {CATEGORIES.map((c) => (
            <label key={c} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={cats.includes(c)}
                onChange={() => toggleCat(c)}
                className="accent-[var(--accent)]"
              />
              <span className={cats.includes(c) ? 'text-text' : 'text-text-muted'}>{c}</span>
            </label>
          ))}
        </div>
      </div>
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-3">Framework</div>
        <div className="flex flex-wrap gap-1.5">
          {frameworks.map((f) => (
            <button
              key={f}
              onClick={() => setFramework(f)}
              className={`font-mono text-[10px] uppercase tracking-wider px-2 py-1 rounded-full hairline transition-colors ${
                framework === f ? 'bg-text text-bg border-transparent' : 'text-text-muted hover:text-text'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Price</div>
          <div className="font-mono text-xs tabular">≤ ${maxPrice.toLocaleString()}</div>
        </div>
        <input
          type="range"
          min={29} max={50000} step={50}
          value={maxPrice}
          onChange={(e) => setMaxPrice(+e.target.value)}
          className="w-full accent-[var(--accent)]"
        />
      </div>
      <div>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input type="checkbox" checked={hasDemo} onChange={(e) => setHasDemo(e.target.checked)} className="accent-[var(--accent)]" />
          <span>Live demo only</span>
        </label>
      </div>
    </div>
  );

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-12 pb-24">
      <div className="flex items-end justify-between gap-6 flex-wrap mb-10">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">The Gallery</div>
          <h1 className="font-serif mt-3">Browse the collection</h1>
          <p className="text-text-muted mt-3 text-sm">{filtered.length} pieces on display</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOpenFilters(true)}
            className="lg:hidden hairline rounded-full px-3 h-9 text-sm flex items-center gap-1.5"
          >
            <SlidersHorizontal size={13} /> Filters
          </button>
          <SortMenu value={sort} onChange={setSort} />
        </div>
      </div>

      <div className="grid lg:grid-cols-[220px_1fr] gap-10">
        <aside className="hidden lg:block sticky top-24 self-start">{Filters}</aside>

        {openFilters && (
          <div className="fixed inset-0 z-50 lg:hidden bg-black/40" onClick={() => setOpenFilters(false)}>
            <aside className="absolute left-0 top-0 bottom-0 w-80 bg-bg p-6 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-6">
                <div className="font-serif text-xl">Filters</div>
                <button onClick={() => setOpenFilters(false)}><X size={18} /></button>
              </div>
              {Filters}
            </aside>
          </div>
        )}

        <motion.div
          key={`${sort}-${cats.join()}-${maxPrice}-${framework}-${hasDemo}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="grid sm:grid-cols-2 xl:grid-cols-3 gap-6"
        >
          {filtered.map((p) => (
            <ProductCard key={p.id} product={p} onOpen={() => onOpenProduct(p.slug)} onPreview={() => onPreview(p)} onBargain={() => onBargain(p)} />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full hairline rounded-2xl p-16 text-center">
              <div className="font-serif text-2xl">Nothing matches yet</div>
              <p className="text-text-muted mt-2 text-sm">Loosen a filter or two and the gallery will fill back in.</p>
            </div>
          )}
        </motion.div>
      </div>
    </main>
  );
}

function SortMenu({ value, onChange }: { value: 'score' | 'new' | 'price' | 'rating'; onChange: (s: any) => void }) {
  const opts: { id: any; label: string }[] = [
    { id: 'score', label: 'Vitrine Score' },
    { id: 'new', label: 'Newest' },
    { id: 'price', label: 'Price' },
    { id: 'rating', label: 'Rating' },
  ];
  return (
    <div className="hairline rounded-full p-1 flex gap-0.5">
      {opts.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`px-3 h-7 rounded-full font-mono text-[10px] uppercase tracking-wider transition-colors ${
            value === o.id ? 'bg-text text-bg' : 'text-text-muted hover:text-text'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
