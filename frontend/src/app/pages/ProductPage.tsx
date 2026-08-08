import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Play, Share2, Check, Star, Bot, Sparkles, Lightbulb, Wrench, Workflow, MessagesSquare, Briefcase, Layers, Flag } from 'lucide-react';
import { toast } from 'sonner';
import { Typewriter } from '../components/Typewriter';
import { type Product } from '../lib/mockData';
import { useCatalogProducts } from '../lib/store';
import { ProductCard } from '../components/ProductCard';
import { VitrineScoreRing } from '../components/VitrineScoreRing';
import { SpecSheet } from '../components/SpecSheet';
import { Badge } from '../components/Badge';
import { ImageWithFallback } from '../components/ImageWithFallback';
import { PromptDialog, type PromptRequest } from '../components/PromptDialog';
import { api, USE_MOCKS } from '../lib/api';

export function ProductPage({
  slug, onOpenProduct, onPreview, onBargain, onRequestFeatures, onCheckout,
}: { slug: string; onOpenProduct: (s: string) => void; onPreview: (p: Product) => void; onBargain: (p: Product) => void; onRequestFeatures: (p: Product) => void; onCheckout: (p: Product, tier: number) => void }) {
  const products = useCatalogProducts();
  const product = products.find((p) => p.slug === slug);
  const [activeScreen, setActiveScreen] = useState(0);
  const [tier, setTier] = useState(1);
  const [reviews, setReviews] = useState<{ id: string; rating: number; body: string; verified: boolean; ts: number }[]>([]);
  const [prompt, setPrompt] = useState<PromptRequest | null>(null);

  useEffect(() => {
    if (!product || USE_MOCKS) return;
    // Navigating between products quickly could let a slow response for the
    // previous listing resolve last and overwrite the current one's reviews.
    let active = true;
    api.reviews(product.id)
      .then((r) => { if (active) setReviews(r); })
      .catch(() => { if (active) setReviews([]); });
    return () => { active = false; };
  }, [product?.id]);

  if (!product) {
    return (
      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-10 pb-24 text-center">
        <h1 className="font-serif text-3xl">Piece not found</h1>
        <p className="text-text-muted mt-3 text-sm">This listing may have been removed or the URL is incorrect.</p>
        <button onClick={() => { window.location.hash = '#/browse'; }} className="mt-6 text-accent hover:underline text-sm">
          Return to gallery
        </button>
      </main>
    );
  }

  const similar = products.filter((p) => p.category === product.category && p.id !== product.id).slice(0, 4);

  // A freshly published listing is the *normal* case, not an edge case: the
  // API returns empty arrays for tiers/ratings/spec and the seller fills them
  // in later. Everything below has to survive that shape.
  const screenshots = product.screenshots ?? [];
  const screenIndex = screenshots.length ? Math.min(Math.max(activeScreen, 0), screenshots.length - 1) : 0;
  const tiers = product.tiers ?? [];
  const hasTiers = tiers.length > 0;
  // `tier` is free-running state (it defaults to 1 and the seller may delete
  // tiers under it), so clamp before it ever indexes the array.
  const tierIndex = hasTiers ? Math.min(Math.max(tier, 0), tiers.length - 1) : 0;
  const buyPrice = (hasTiers ? tiers[tierIndex]?.price : product.price) ?? 0;
  const distribution = product.ratingDistribution ?? [];
  const reviewsCount = product.reviewsCount ?? 0;
  const hasRatings = reviewsCount > 0 && distribution.some((v) => Number(v) > 0);
  const sdlc = product.sdlc ?? { problem: '', solution: '', methodology: '', discussions: '' };
  const businessModel = product.businessModel ?? { kind: 'for-profit' as const, pitch: '', revenueStreams: [] };
  const releasedAt = product.createdAt ? new Date(product.createdAt) : null;

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-10 pb-24">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted mb-6">
        Gallery / {product.category} / <span className="text-text">{product.name}</span>
      </div>

      {/* Hero */}
      <section className="grid lg:grid-cols-[1.4fr_1fr] gap-8 lg:gap-12 items-start">
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="hairline rounded-2xl overflow-hidden bg-surface"
        >
          <div className="aspect-[16/10] bg-surface-2 relative group">
            <ImageWithFallback src={screenshots[screenIndex] ?? product.cover} alt={product.name} className="w-full h-full object-cover" />
            <button
              onClick={() => onPreview(product)}
              className="absolute inset-0 grid place-items-center bg-black/10 md:bg-black/0 md:hover:bg-black/30 transition-colors"
            >
              <span className="inline-flex items-center gap-2 bg-accent text-[var(--accent-ink)] rounded-full pl-4 pr-5 h-11 sm:h-12 font-medium shadow-2xl md:hover:scale-105 transition-all">
                <Play size={14} fill="currentColor" /> Open the vitrine
              </span>
            </button>
            {/* Only claim a live demo when the listing actually has one — the
                catalogue now holds CLIs, firmware and mobile binaries that
                legitimately have no hosted preview. */}
            {product.hasLiveDemo && (
              <div className="absolute top-4 left-4 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-white/90">
                <span className="live-dot" /> live demo
              </div>
            )}
          </div>
          {screenshots.length > 1 && (
            <div className="flex gap-2 p-3 overflow-x-auto scroll-rail">
              {screenshots.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setActiveScreen(i)}
                  className={`shrink-0 w-24 h-16 rounded-lg overflow-hidden hairline transition-all ${i === screenIndex ? 'border-accent ring-1 ring-accent' : 'opacity-70 hover:opacity-100'}`}
                >
                  <ImageWithFallback src={s} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}
          className="space-y-6"
        >
          <div className="flex flex-wrap gap-1.5">
            {(product.badges ?? []).map((b) => <Badge key={b} kind={b} />)}
          </div>
          <div>
            <h1 className="font-serif">{product.name}</h1>
            <p className="text-text-muted mt-3 leading-relaxed">{product.tagline}</p>
          </div>
          <div className="flex items-center justify-between hairline rounded-2xl p-5 bg-surface">
            <VitrineScoreRing score={product.vitrineScore} />
            <button
              onClick={() => {
                const oid = (product as any).ownerId;
                if (oid) {
                  window.location.hash = `#/profile/${oid}`;
                }
              }}
              className="text-right hover:text-accent transition-colors cursor-pointer group"
            >
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted group-hover:text-accent/80">by</div>
              <div className="font-serif text-lg">{product.seller?.name}</div>
              <div className="text-xs text-text-muted group-hover:text-accent/60">{product.seller?.handle}</div>
            </button>
          </div>

          {/* Tiers */}
          <div className="hairline rounded-2xl bg-surface overflow-hidden">
            <div className="px-5 py-3 border-b font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
              {hasTiers ? 'Choose a tier' : 'Price'}
            </div>
            {hasTiers ? (
              <div className="divide-y">
                {tiers.map((t, i) => (
                  <button
                    key={t.name ?? i}
                    onClick={() => setTier(i)}
                    className={`w-full text-left p-5 flex items-start gap-4 transition-colors ${tierIndex === i ? 'bg-surface-2/70' : 'hover:bg-surface-2/40'}`}
                  >
                    <span className={`mt-1 w-4 h-4 rounded-full hairline grid place-items-center shrink-0 ${tierIndex === i ? 'border-accent' : ''}`}>
                      {tierIndex === i && <span className="w-2 h-2 rounded-full bg-accent" />}
                    </span>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-serif text-lg">
                          {t.name}
                          {t.recommended && <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-accent">recommended</span>}
                        </span>
                        <span className="font-mono tabular">${t.price}</span>
                      </div>
                      <ul className="mt-2 space-y-1">
                        {(t.features ?? []).map((f) => (
                          <li key={f} className="text-xs text-text-muted flex items-center gap-1.5">
                            <Check size={11} className="text-accent" /> {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              // No tiers published yet — fall back to the listing's own price so
              // the buy path stays intact instead of collapsing to $undefined.
              <div className="p-5 flex items-baseline justify-between">
                <span className="font-serif text-lg">One-time purchase</span>
                <span className="font-mono tabular text-lg">${buyPrice.toLocaleString()}</span>
              </div>
            )}
            <div className="p-4 flex gap-2 border-t">
              <button onClick={() => onCheckout(product, tierIndex)} className="flex-1 h-11 rounded-xl bg-text text-bg font-medium hover:opacity-90 transition-opacity">
                Buy · ${buyPrice.toLocaleString()}
              </button>
              <button
                onClick={async () => {
                  const url = `${window.location.origin}${window.location.pathname}#/p/${product.slug}`;
                  try {
                    await navigator.clipboard.writeText(url);
                    toast.success('Link copied');
                  } catch {
                    toast.error('Could not copy the link');
                  }
                }}
                className="w-11 h-11 rounded-xl hairline grid place-items-center hover:border-accent transition-colors" aria-label="Share"
              >
                <Share2 size={15} />
              </button>
              <button onClick={() => setPrompt({
                title: `Report ${product.name}`,
                description: 'Tell a curator what looks wrong — misleading claims, a broken demo, or stolen work.',
                input: { label: 'Reason', placeholder: 'What should we look at?' },
                confirmLabel: 'Submit report',
                danger: true,
                onConfirm: async (reason) => {
                  try {
                    await api.submitReport({ target_type: 'listing', target_id: product.id, reason });
                    toast.success('Report submitted — a curator will review it.');
                  } catch {
                    toast.error('Could not submit that report');
                  }
                },
              })} className="w-11 h-11 rounded-xl hairline grid place-items-center hover:border-danger text-text-muted hover:text-danger transition-colors" aria-label="Report">
                <Flag size={15} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => onBargain(product)} className="group hairline rounded-xl h-11 text-sm inline-flex items-center justify-center gap-2 hover:border-accent hover:text-accent transition-colors overflow-hidden">
              <Bot size={14} className="text-accent group-hover:rotate-6 transition-transform" />
              <Typewriter words={['AI Bargain', 'Negotiate for me', 'Send my rep']} className="font-mono text-[12px] uppercase tracking-wider" />
            </button>
            <button onClick={() => onRequestFeatures(product)} className="group hairline rounded-xl h-11 text-sm inline-flex items-center justify-center gap-2 hover:border-accent hover:text-accent transition-colors">
              <Sparkles size={14} className="text-accent group-hover:scale-110 transition-transform" /> Request features
            </button>
          </div>

          <div className="text-xs text-text-soft leading-relaxed">
            <span className="text-text">Pay an advance</span> to commission a custom variant — Vitrine escrows the funds until delivery.
          </div>
        </motion.div>
      </section>

      <hr className="editorial-rule my-20" />

      {/* Description + Spec sheet */}
      <section className="grid lg:grid-cols-[1fr_1.4fr] gap-10">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">The story</div>
          <h2 className="font-serif mt-3">A piece built with care.</h2>
          <p className="text-text-muted mt-6 leading-relaxed">{product.description}</p>
          <p className="text-text-muted mt-4 leading-relaxed">
            {product.name} comes with seed data, themed light and dark modes, and a documented architecture. Plug in your keys and you're shipping by the end of the day.
          </p>
          <dl className="mt-8 grid grid-cols-2 gap-y-3 font-mono text-xs">
            <dt className="text-text-muted uppercase tracking-wider text-[10px]">Framework</dt><dd>{product.framework}</dd>
            <dt className="text-text-muted uppercase tracking-wider text-[10px]">License</dt><dd>{product.license}</dd>
            <dt className="text-text-muted uppercase tracking-wider text-[10px]">Category</dt><dd>{product.category}</dd>
            <dt className="text-text-muted uppercase tracking-wider text-[10px]">Released</dt>
            <dd>{releasedAt && !Number.isNaN(releasedAt.getTime()) ? releasedAt.toLocaleDateString() : '—'}</dd>
          </dl>
        </div>
        <SpecSheet sections={product.spec ?? []} />
      </section>

      <hr className="editorial-rule my-20" />

      {/* SDLC */}
      <section>
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Software development lifecycle</div>
            <h2 className="font-serif mt-3">How it was built.</h2>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-wider text-accent inline-flex items-center gap-1.5 hairline border-accent/40 rounded-full px-2.5 py-1">
            <Bot size={11} /> AI-drafted · seller-edited
          </span>
        </div>
        <div className="grid md:grid-cols-2 gap-4 mt-8">
          {[
            { icon: <Lightbulb size={14} />, title: 'Problem statement', body: sdlc.problem },
            { icon: <Wrench size={14} />, title: 'Solution', body: sdlc.solution },
            { icon: <Workflow size={14} />, title: 'Methodology', body: sdlc.methodology },
            { icon: <MessagesSquare size={14} />, title: 'Discussions', body: sdlc.discussions },
          ].map((s) => (
            <motion.article
              key={s.title}
              initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="hairline rounded-2xl bg-surface p-6"
            >
              <div className="flex items-center gap-2 text-accent">
                {s.icon}
                <span className="font-mono text-[10px] uppercase tracking-[0.18em]">{s.title}</span>
              </div>
              <p className="text-text-soft leading-relaxed mt-3 text-sm">
                {s.body?.trim() ? s.body : <span className="text-text-muted italic">Not documented yet.</span>}
              </p>
            </motion.article>
          ))}
        </div>
      </section>

      {/* Business model + tech stack */}
      <section className="grid lg:grid-cols-[1fr_1fr] gap-6 mt-10">
        <div className="hairline rounded-2xl bg-surface p-6">
          <div className="flex items-center gap-2 text-accent">
            <Briefcase size={14} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em]">Business model</span>
          </div>
          <div className="font-serif text-2xl mt-3 capitalize">{(businessModel.kind ?? '').replace('-', ' ') || 'Not specified'}</div>
          {businessModel.pitch?.trim() && (
            <p className="text-text-soft leading-relaxed mt-3 text-sm">{businessModel.pitch}</p>
          )}
          <div className="mt-5">
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Revenue streams</div>
            <ul className="mt-2 space-y-1.5">
              {(businessModel.revenueStreams ?? []).map((r) => (
                <li key={r} className="flex items-center gap-2 text-sm">
                  <Check size={12} className="text-accent shrink-0" /> {r}
                </li>
              ))}
            </ul>
            {(businessModel.revenueStreams ?? []).length === 0 && (
              <p className="text-sm text-text-muted mt-2">Not documented yet.</p>
            )}
          </div>
        </div>
        <div className="hairline rounded-2xl bg-surface p-6">
          <div className="flex items-center gap-2 text-accent">
            <Layers size={14} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em]">Tech stack</span>
          </div>
          <div className="font-serif text-2xl mt-3">Built with</div>
          <div className="mt-4 flex flex-wrap gap-2">
            {(product.techStack ?? []).map((t) => (
              <span key={t} className="hairline rounded-full px-3 py-1 text-xs font-mono">{t}</span>
            ))}
          </div>
          <div className="mt-6 grid grid-cols-2 gap-y-2 font-mono text-xs">
            <div className="text-text-muted uppercase tracking-wider text-[10px]">Framework</div><div>{product.framework}</div>
            <div className="text-text-muted uppercase tracking-wider text-[10px]">License</div><div>{product.license}</div>
          </div>
        </div>
      </section>

      <hr className="editorial-rule my-20" />

      {/* Reviews */}
      <section className="mt-20 grid lg:grid-cols-[1fr_1.4fr] gap-10">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Reception</div>
          <h2 className="font-serif mt-3">
            {hasRatings
              ? `${Number(product.rating ?? 0).toFixed(1)} · ${reviewsCount} ${reviewsCount === 1 ? 'review' : 'reviews'}`
              : 'Not yet rated'}
          </h2>
          {hasRatings ? (
            <div className="mt-6 space-y-2">
              {[5,4,3,2,1].map((star) => {
                // Empty distributions used to yield `undefined` here and render
                // `width: undefined%` — a NaN bar. Clamp to a real percentage.
                const raw = Number(distribution[5 - star]);
                const v = Number.isFinite(raw) ? Math.min(Math.max(raw, 0), 100) : 0;
                return (
                  <div key={star} className="flex items-center gap-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted w-6">{star}★</span>
                    <div className="flex-1 h-1 bg-surface-2 rounded-full overflow-hidden">
                      <div className="h-full bg-accent" style={{ width: `${v}%` }} />
                    </div>
                    <span className="font-mono text-xs tabular text-text-muted w-8 text-right">{v}%</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-text-muted mt-6 leading-relaxed">
              This piece hasn't been reviewed yet. Ratings appear here once verified buyers weigh in.
            </p>
          )}
        </div>
        <div className="space-y-4">
          {reviews.length === 0 ? (
            <p className="text-sm text-text-muted">No reviews yet — be the first after purchase.</p>
          ) : reviews.map((r) => (
            <article key={r.id} className="hairline rounded-2xl p-5 bg-surface">
              <header className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="w-8 h-8 rounded-full bg-surface-2 grid place-items-center font-serif text-sm">★</span>
                  <div>
                    <div className="text-sm">{r.verified ? 'Verified buyer' : 'Buyer'}</div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                      {new Date(r.ts).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <div className="flex gap-0.5 text-accent">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} size={12} fill={i < r.rating ? 'currentColor' : 'none'} className={i < r.rating ? '' : 'opacity-30'} />
                  ))}
                </div>
              </header>
              <p className="text-sm text-text-muted mt-3 leading-relaxed">{r.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Similar */}
      <section className="mt-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Adjacent pieces</div>
        <h2 className="font-serif mt-3 mb-8">In the same room</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {similar.map((p) => (
            <ProductCard key={p.id} product={p} onOpen={() => onOpenProduct(p.slug)} onPreview={() => onPreview(p)} onBargain={() => onBargain(p)} size="sm" />
          ))}
        </div>
      </section>

      <PromptDialog request={prompt} onClose={() => setPrompt(null)} />
    </main>
  );
}
