import { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { ChevronLeft, ChevronRight, SlidersHorizontal, X } from 'lucide-react';
import { type Product } from '../lib/mockData';
import { useCatalogProducts, useStore } from '../lib/store';
import { ProductCard } from '../components/ProductCard';

type Sort = 'score' | 'new' | 'price' | 'rating';
const PAGE_SIZE = 18;

export function Browse({ onOpenProduct, onPreview, onBargain }: { onOpenProduct: (slug: string) => void; onPreview: (p: Product) => void; onBargain: (p: Product) => void }) {
  const products = useCatalogProducts();
  const { categories } = useStore();
  const [cats, setCats] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState(50000);
  const [hasDemo, setHasDemo] = useState(false);
  const [framework, setFramework] = useState<string>('All');
  const [sort, setSort] = useState<Sort>('score');
  const [openFilters, setOpenFilters] = useState(false);
  const [page, setPage] = useState(1);

  const frameworks = useMemo(() => ['All', ...Array.from(new Set(products.map((p) => p.framework)))], [products]);

  const filtered = useMemo(() => {
    let r = products.filter((p) => p.price <= maxPrice);
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
  }, [products, cats, maxPrice, hasDemo, framework, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);
  const rangeStart = filtered.length ? (page - 1) * PAGE_SIZE + 1 : 0;
  const rangeEnd = Math.min(page * PAGE_SIZE, filtered.length);

  useEffect(() => {
    setPage(1);
  }, [cats, maxPrice, hasDemo, framework, sort]);

  useEffect(() => {
    setPage((p) => Math.min(p, totalPages));
  }, [totalPages]);

  const goPage = (next: number) => {
    setPage(Math.min(Math.max(next, 1), totalPages));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const toggleCat = (c: string) => setCats((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  const Filters = (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-3">Category</div>
        <div className="space-y-1.5">
          {categories.map((c) => (
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
          <p className="text-text-muted mt-3 text-sm">
            {filtered.length} pieces on display · showing {rangeStart}-{rangeEnd} · max {PAGE_SIZE} per page
          </p>
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
          key={`${sort}-${cats.join()}-${maxPrice}-${framework}-${hasDemo}-${page}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="grid sm:grid-cols-2 xl:grid-cols-3 gap-6"
        >
          {visible.map((p) => (
            <ProductCard key={p.id} product={p} onOpen={() => onOpenProduct(p.slug)} onPreview={() => onPreview(p)} onBargain={() => onBargain(p)} />
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full hairline rounded-2xl p-16 text-center">
              <div className="font-serif text-2xl">Nothing matches yet</div>
              <p className="text-text-muted mt-2 text-sm">Loosen a filter or two and the gallery will fill back in.</p>
            </div>
          )}
        </motion.div>

        {filtered.length > PAGE_SIZE && (
          <div className="lg:col-start-2 mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 border-t pt-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
              Page {page} of {totalPages}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => goPage(page - 1)}
                disabled={page === 1}
                className="hairline rounded-full h-9 px-3 text-xs inline-flex items-center gap-1.5 disabled:opacity-40 disabled:pointer-events-none hover:border-accent transition-colors"
              >
                <ChevronLeft size={13} /> Previous
              </button>
              {Array.from({ length: totalPages }).map((_, i) => {
                const n = i + 1;
                return (
                  <button
                    key={n}
                    onClick={() => goPage(n)}
                    aria-label={`Page ${n}`}
                    className={`w-9 h-9 rounded-full font-mono text-[10px] transition-colors ${
                      n === page ? 'bg-text text-bg' : 'hairline text-text-muted hover:text-text hover:border-accent'
                    }`}
                  >
                    {n}
                  </button>
                );
              })}
              <button
                onClick={() => goPage(page + 1)}
                disabled={page === totalPages}
                className="hairline rounded-full h-9 px-3 text-xs inline-flex items-center gap-1.5 disabled:opacity-40 disabled:pointer-events-none hover:border-accent transition-colors"
              >
                Next <ChevronRight size={13} />
              </button>
            </div>
          </div>
        )}
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
