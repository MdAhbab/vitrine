import { motion } from 'motion/react';
import { Play, ArrowUpRight, Bot } from 'lucide-react';
import { ImageWithFallback } from './ImageWithFallback';
import type { Product } from '../lib/mockData';
import { Badge } from './Badge';

export function ProductCard({
  product,
  onOpen,
  onPreview,
  onBargain,
  size = 'md',
}: {
  product: Product;
  onOpen: () => void;
  onPreview: () => void;
  onBargain?: () => void;
  size?: 'sm' | 'md' | 'lg';
}) {
  const aspect = size === 'lg' ? 'aspect-[16/10]' : 'aspect-[4/3]';
  return (
    <motion.article
      whileHover={{ y: -3 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      className="group bg-surface hairline rounded-2xl overflow-hidden flex flex-col cursor-pointer transition-colors hover:border-accent/60"
      onClick={onOpen}
    >
      <div className={`relative ${aspect} overflow-hidden bg-surface-2`}>
        <ImageWithFallback
          src={product.cover}
          alt={product.name}
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.03]"
        />
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/55 to-transparent pointer-events-none" />
        <div className="absolute top-3 left-3 flex gap-1.5">
          {product.badges.slice(0, 2).map((b) => <Badge key={b} kind={b} overlay={true} />)}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onPreview(); }}
          className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 bg-accent text-[var(--accent-ink)] rounded-full pl-2.5 pr-3 h-8 text-xs font-medium shadow-lg opacity-90 md:opacity-0 md:translate-y-1 md:group-hover:opacity-100 md:group-hover:translate-y-0 transition-all duration-300"
        >
          <Play size={11} fill="currentColor" /> Run preview
        </button>
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-white/90">
          <span className="live-dot" />
          live
        </div>
      </div>

      <div className="p-5 flex flex-col gap-3 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-serif text-[1.25rem] leading-tight truncate">{product.name}</h3>
            <p className="text-xs text-text-muted mt-1 line-clamp-1">{product.tagline}</p>
          </div>
          <ArrowUpRight size={16} className="text-text-muted shrink-0 transition-transform group-hover:rotate-45 group-hover:text-accent" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {product.tags.slice(0, 3).map((t) => (
            <span key={t} className="font-mono text-[10px] uppercase tracking-wider text-text-muted px-1.5 py-0.5 hairline rounded">{t}</span>
          ))}
        </div>
        <div className="mt-auto pt-3 border-t flex flex-col gap-3">
          <div className="flex items-end justify-between">
            <div className="text-xs text-text-soft">
              by <span className="text-text">{product.seller.name}</span>
            </div>
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-accent tabular">{product.vitrineScore}</span>
              <span className="font-mono tabular text-text">${product.price.toLocaleString()}</span>
            </div>
          </div>
          {onBargain && (
            <button
              onClick={(e) => { e.stopPropagation(); onBargain(); }}
              className="group/btn w-full hairline rounded-lg h-9 text-xs inline-flex items-center justify-center gap-1.5 hover:border-accent hover:text-accent transition-colors overflow-hidden"
            >
              <Bot size={12} className="text-accent group-hover/btn:rotate-12 transition-transform" />
              <span className="font-mono text-[11px] uppercase tracking-wider">AI Bargain on my behalf</span>
            </button>
          )}
        </div>
      </div>
    </motion.article>
  );
}
