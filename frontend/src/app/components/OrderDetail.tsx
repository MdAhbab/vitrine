import { motion, AnimatePresence } from 'motion/react';
import { X, Download, KeyRound, Receipt, Play, Star, FileText, Headphones, Copy, Bot } from 'lucide-react';
import { PRODUCTS } from '../lib/mockData';
import type { Transaction } from '../lib/store';

export function OrderDetail({
  order, onClose, onOpenProduct, onPreview,
}: {
  order: Transaction;
  onClose: () => void;
  onOpenProduct: (slug: string) => void;
  onPreview: (demoUrl: string, name: string) => void;
}) {
  const product = PRODUCTS.find((p) => p.id === order.productId) ?? PRODUCTS[0];
  const licenseKey = `VTR-${order.id.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4)}-${product.id.toUpperCase()}-${order.tier.replace(/\s+/g, '').slice(0, 4).toUpperCase()}`;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm overflow-y-auto"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="max-w-3xl mx-auto my-12 hairline rounded-2xl bg-bg shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <header className="border-b px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Order · {order.id}</div>
            <button onClick={onClose} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-accent" aria-label="Close"><X size={14} /></button>
          </header>

          {/* Product banner */}
          <div className="relative aspect-[16/7]">
            <img src={product.cover} alt="" className="absolute inset-0 w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/40 to-transparent" />
            <div className="absolute bottom-5 left-6 right-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/85">{product.category}</div>
              <h2 className="font-serif text-3xl mt-2 text-white">{product.name}</h2>
              <p className="text-sm text-white/80 mt-1">{product.tagline}</p>
            </div>
          </div>

          <div className="px-6 lg:px-8 py-8 space-y-6">
            {/* Meta row */}
            <div className="grid sm:grid-cols-4 gap-4">
              <Meta k="Status" v={order.status} accent={order.status === 'paid' ? 'text-success' : order.status === 'refunded' ? 'text-danger' : 'text-accent'} />
              <Meta k="Tier" v={order.tier} />
              <Meta k="Amount" v={`$${order.amount.toLocaleString()}`} />
              <Meta k="Date" v={new Date(order.ts).toLocaleDateString()} />
            </div>

            {/* License key */}
            <section className="hairline rounded-2xl bg-surface p-5">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted inline-flex items-center gap-1.5"><KeyRound size={11} /> License key</div>
                  <div className="font-mono text-lg mt-1 tracking-wide">{licenseKey}</div>
                </div>
                <button onClick={() => navigator.clipboard?.writeText(licenseKey)} className="hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:border-accent">
                  <Copy size={13} /> Copy
                </button>
              </div>
            </section>

            {/* Actions */}
            <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
              <Action icon={<Download size={14} />} label="Download source" />
              <Action icon={<Play size={14} />} label="Open live demo" onClick={() => onPreview(product.demoUrl, product.name)} />
              <Action icon={<FileText size={14} />} label="Open docs" />
              <Action icon={<Headphones size={14} />} label="Contact seller" />
            </section>

            {/* What you bought */}
            <section className="hairline rounded-2xl bg-surface p-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">What you bought</div>
              <p className="text-text-soft text-sm leading-relaxed mt-3">{product.description}</p>
              <div className="mt-5 grid sm:grid-cols-2 gap-4">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Problem</div>
                  <p className="text-sm mt-1">{product.sdlc.problem}</p>
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Solution</div>
                  <p className="text-sm mt-1">{product.sdlc.solution}</p>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-1.5">
                {product.techStack.map((t) => <span key={t} className="hairline rounded-full px-2.5 py-1 text-xs font-mono">{t}</span>)}
              </div>
            </section>

            {/* Footer actions */}
            <section className="flex flex-wrap gap-2">
              <button onClick={() => onOpenProduct(product.slug)} className="hairline rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2 hover:border-accent">Open product page</button>
              <button className="hairline rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2 hover:border-accent"><Star size={13} /> Leave a review</button>
              <button className="hairline rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2 hover:border-accent"><Receipt size={13} /> Download invoice</button>
              <button className="hairline rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2 hover:border-accent hover:text-accent"><Bot size={13} /> Ask my AI rep</button>
            </section>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function Meta({ k, v, accent = '' }: { k: string; v: string; accent?: string }) {
  return (
    <div className="hairline rounded-xl p-3 bg-surface">
      <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{k}</div>
      <div className={`text-sm capitalize mt-1 ${accent}`}>{v}</div>
    </div>
  );
}

function Action({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="hairline rounded-xl h-11 text-sm inline-flex items-center justify-center gap-2 hover:border-accent transition-colors">
      <span className="text-accent">{icon}</span> {label}
    </button>
  );
}
