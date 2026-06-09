import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, X, ArrowRight, Send } from 'lucide-react';
import { toast } from 'sonner';
import { type Product } from '../lib/mockData';
import { conciergeStream, USE_MOCKS } from '../lib/api';
import { useCatalogProducts } from '../lib/store';

type Msg =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; results?: Product[] };

const SUGGESTIONS = [
  'React dashboard with Stripe, under $100, live demo',
  'AI chat surface with SSE streaming',
  'Headless commerce storefront with great taste',
  'Editorial analytics for serious teams',
];

export function ConciergePanel({ open, onClose, onOpenProduct }: { open: boolean; onClose: () => void; onOpenProduct: (slug: string) => void }) {
  const products = useCatalogProducts();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, streaming]);

  async function sendMock(q: string) {
    const tokens = [
      'Considering ', 'your ', 'constraints ', '— ', 'I ', 'looked ', 'across ', 'the ', 'gallery ',
      'and ', 'filtered ', 'by ', 'demo ', 'health, ', 'price, ', 'and ', 'UI ', 'craft. ',
      'Here ', 'are ', 'three ', 'that ', 'feel ', 'right.',
    ];
    let acc = '';
    setMessages((m) => [...m, { role: 'assistant', text: '' }]);
    for (const t of tokens) {
      await new Promise((r) => setTimeout(r, 35));
      acc += t;
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = { role: 'assistant', text: acc };
        return next;
      });
    }
    const lower = q.toLowerCase();
    const results = products
      .filter((p) =>
        p.tags.some((t) => lower.includes(t)) ||
        lower.includes(p.category.toLowerCase()) ||
        p.name.toLowerCase().includes(lower.split(' ')[0])
      )
      .slice(0, 3);
    const final = results.length ? results : products.slice(0, 3);
    setMessages((m) => {
      const next = [...m];
      next[next.length - 1] = { role: 'assistant', text: acc, results: final };
      return next;
    });
  }

  async function sendLive(q: string) {
    let acc = '';
    let resultSlugs: Product[] = [];
    setMessages((m) => [...m, { role: 'assistant', text: '' }]);

    await conciergeStream(q, (chunk) => {
      if (chunk.type === 'token' && chunk.text) {
        acc += chunk.text;
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = { role: 'assistant', text: acc };
          return next;
        });
      }
      if (chunk.type === 'results' && chunk.results) {
        resultSlugs = chunk.results.map((r: { slug: string; name: string; tagline: string; price: number; vitrineScore: number }) => {
          const full = products.find((p) => p.slug === r.slug || p.id === r.id);
          return full ?? {
            id: r.id || r.slug,
            slug: r.slug,
            name: r.name,
            tagline: r.tagline,
            price: r.price,
            vitrineScore: r.vitrineScore,
            cover: '',
            category: '',
            tags: [],
            seller: { name: '', handle: '', verified: false },
            scoreBreakdown: [],
            demoUrl: '',
            demoHealth: 'live' as const,
            badges: [],
            screenshots: [],
            ratingDistribution: [],
            rating: 0,
            reviewsCount: 0,
            description: '',
            spec: [],
            framework: '',
            license: 'MIT' as const,
            hasLiveDemo: false,
            createdAt: '',
            sdlc: { problem: '', solution: '', methodology: '', discussions: '' },
            businessModel: { kind: 'for-profit' as const, pitch: '', revenueStreams: [] },
            techStack: [],
          };
        });
      }
      if (chunk.type === 'done') {
        setMessages((m) => {
          const next = [...m];
          const last = next[next.length - 1];
          if (last.role === 'assistant') {
            next[next.length - 1] = { ...last, results: resultSlugs.length ? resultSlugs : products.slice(0, 3) };
          }
          return next;
        });
      }
    });
  }

  async function send(q: string) {
    if (!q.trim() || streaming) return;
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setInput('');
    setStreaming(true);
    try {
      if (USE_MOCKS) {
        await sendMock(q);
      } else {
        await sendLive(q);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Concierge unavailable');
      setMessages((m) => [...m, { role: 'assistant', text: 'Sorry — I could not reach the concierge service. Try again shortly.' }]);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.aside
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 220, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="absolute right-0 top-0 bottom-0 w-full sm:w-[480px] bg-bg hairline border-l flex flex-col"
          >
            <div className="px-6 h-16 flex items-center justify-between border-b">
              <div className="flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-full grid place-items-center gold-gradient text-[var(--accent-ink)]">
                  <Sparkles size={13} />
                </span>
                <div>
                  <div className="font-serif text-lg leading-none">Concierge</div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted mt-1">curator on duty</div>
                </div>
              </div>
              <button onClick={onClose} className="w-8 h-8 grid place-items-center text-text-muted hover:text-text" aria-label="Close">
                <X size={16} />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
              {messages.length === 0 && (
                <div className="space-y-5">
                  <p className="text-text-muted text-sm leading-relaxed">
                    Tell me what you're building. I'll cross-reference the gallery against your constraints — demo health, price, framework, taste — and present the three I'd actually buy.
                  </p>
                  <div className="space-y-2">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="w-full text-left hairline rounded-xl px-4 py-3 text-sm hover:border-accent hover:text-accent transition-colors flex items-center justify-between gap-3 group"
                      >
                        <span>{s}</span>
                        <ArrowRight size={13} className="text-text-muted group-hover:text-accent shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} className={m.role === 'user' ? 'flex justify-end' : ''}>
                  {m.role === 'user' ? (
                    <div className="max-w-[85%] bg-surface-2 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">{m.text}</div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm leading-relaxed text-text">{m.text}{streaming && i === messages.length - 1 && <span className="inline-block w-1.5 h-4 bg-accent ml-1 align-middle animate-pulse" />}</p>
                      {m.results && (
                        <div className="space-y-2">
                          {m.results.map((r) => (
                            <button
                              key={r.id}
                              onClick={() => onOpenProduct(r.slug)}
                              className="w-full text-left hairline rounded-xl bg-surface p-3 flex gap-3 hover:border-accent transition-colors group"
                            >
                              <img src={r.cover} alt="" className="w-16 h-16 rounded-lg object-cover" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-serif text-base truncate">{r.name}</span>
                                  <span className="font-mono text-[10px] uppercase tracking-wider text-accent shrink-0">{r.vitrineScore}</span>
                                </div>
                                <p className="text-xs text-text-muted line-clamp-1">{r.tagline}</p>
                                <div className="flex items-center gap-3 mt-1.5">
                                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{r.framework}</span>
                                  <span className="font-mono text-xs tabular">${r.price}</span>
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <form
              onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="border-t p-4"
            >
              <div className="hairline rounded-2xl bg-surface flex items-end gap-2 p-2 focus-within:border-accent transition-colors">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); }
                  }}
                  rows={1}
                  placeholder="Describe what you need…"
                  className="flex-1 bg-transparent outline-none resize-none text-sm py-1.5 px-2 max-h-28"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || streaming}
                  className="w-9 h-9 grid place-items-center rounded-xl bg-text text-bg disabled:opacity-30 transition-opacity"
                  aria-label="Send"
                >
                  <Send size={14} />
                </button>
              </div>
            </form>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
