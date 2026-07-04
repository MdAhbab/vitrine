import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Bot, Sparkles, Check, ShieldCheck, CreditCard, Lock, FileText, Upload } from 'lucide-react';
import { toast } from 'sonner';
import type { Product } from '../lib/mockData';
import { api, USE_MOCKS } from '../lib/api';
import { useStore, activeRepsForBuyer, sellerIdFor } from '../lib/store';
import { useShallow } from 'zustand/react/shallow';

function Shell({ open, onClose, children, max = 'max-w-lg' }: { open: boolean; onClose: () => void; children: React.ReactNode; max?: string }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm grid place-items-center p-4"
        >
          <motion.div
            initial={{ scale: 0.96, y: 12, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 240, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className={`bg-surface hairline rounded-2xl w-full ${max} shadow-2xl overflow-hidden max-h-[90vh] flex flex-col`}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Header({ title, eyebrow, onClose, icon }: { title: string; eyebrow: string; onClose: () => void; icon: React.ReactNode }) {
  return (
    <header className="px-6 h-16 border-b flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 grid place-items-center rounded-full gold-gradient text-[var(--accent-ink)]">{icon}</span>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{eyebrow}</div>
          <div className="font-serif text-lg leading-none mt-0.5">{title}</div>
        </div>
      </div>
      <button onClick={onClose} aria-label="Close"><X size={16} /></button>
    </header>
  );
}

export function BargainModal({ open, onClose, product, onOpenInbox }: { open: boolean; onClose: () => void; product: Product | null; onOpenInbox: () => void }) {
  const { user, threads, startThread, sendMessage, deactivateRep } = useStore(
    useShallow((s) => ({
      user: s.user, threads: s.threads, startThread: s.startThread,
      sendMessage: s.sendMessage, deactivateRep: s.deactivateRep,
    })),
  );
  const [step, setStep] = useState<'brief' | 'terms'>('brief');
  const [budget, setBudget] = useState(0);
  const [tone, setTone] = useState<'firm' | 'warm' | 'curious'>('warm');
  const [note, setNote] = useState('');
  const [productInfo, setProductInfo] = useState({ useCase: '', mustHaves: '', timeline: '', readme: '' });
  const [aiSummary, setAiSummary] = useState('');
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    if (product) { setBudget(Math.round(product.price * 0.85)); setStep('brief'); setProductInfo({ useCase: '', mustHaves: '', timeline: '', readme: '' }); setAiSummary(''); }
  }, [product?.id]);

  if (!product) return null;
  const reps = user ? activeRepsForBuyer(user.id, threads) : [];
  const atLimit = reps.length >= 2;
  const alreadyForThis = reps.find((r) => r.productId === product.id);

  const onReadmeFile = async (file: File | null) => {
    if (!file) return;
    const text = await file.text();
    setProductInfo((p) => ({ ...p, readme: text.slice(0, 8000) }));
  };

  const analyzeBrief = async () => {
    setAnalyzing(true);
    await new Promise((r) => setTimeout(r, 700));
    const useCase = productInfo.useCase || `general use of ${product.name}`;
    const must = productInfo.mustHaves ? productInfo.mustHaves.split(/[,\n]/).map((s) => s.trim()).filter(Boolean).slice(0, 3) : [];
    const summary =
      `Brief absorbed. Buyer wants to apply ${product.name} to ${useCase.toLowerCase()}` +
      (must.length ? `, prioritizing ${must.join(', ')}` : '') +
      (productInfo.timeline ? `, on a ${productInfo.timeline} timeline` : '') +
      (productInfo.readme ? ` — cross-referenced against the seller's README (${productInfo.readme.length} chars).` : '.');
    setAiSummary(summary);
    setAnalyzing(false);
    setStep('terms');
  };

  const dispatch = async () => {
    if (!user || atLimit) return;

    const { api, USE_MOCKS } = await import('../lib/api');
    if (USE_MOCKS) {
      const id = startThread({
        productId: product.id, productName: product.name, productCover: product.cover,
        buyerId: user.id, buyerName: user.name,
        sellerId: sellerIdFor(product), sellerName: product.seller.name,
        isAgent: true, agentBudget: budget,
      });
      const briefSummary = aiSummary || `Brief: ${productInfo.useCase || 'general use'}.`;
      const opener = {
        firm: `Hi — I represent ${user.name}. They are ready to close ${product.name} today at $${budget}. That's a firm offer in exchange for a same-day commit.\n\nContext I'm working from: ${briefSummary}`,
        warm: `Hello! I'm ${user.name}'s buying rep. They've been studying ${product.name} and would love to bring it home at $${budget}. Open to bundling Setup if it helps the math.\n\nContext I'm working from: ${briefSummary}`,
        curious: `Hi — quick one on behalf of ${user.name}. They're between ${product.name} and one other piece. Is there room at $${budget}? Happy to add a public review.\n\nContext I'm working from: ${briefSummary}`,
      }[tone];
      sendMessage(id, opener, { id: 'agent', name: `${user.name}'s AI Rep`, isAgent: true });
      if (productInfo.mustHaves.trim()) sendMessage(id, `Must-haves from ${user.name}: ${productInfo.mustHaves}`, { id: 'agent', name: `${user.name}'s AI Rep`, isAgent: true });
      if (note.trim()) sendMessage(id, `Note from ${user.name}: ${note}`, { id: 'agent', name: `${user.name}'s AI Rep`, isAgent: true });
      onClose();
      onOpenInbox();
      return;
    }

    try {
      const briefSummary = aiSummary || `Brief: ${productInfo.useCase || 'general use'}.`;
      const thread = await api.startNegotiation({
        listing_id: product.id,
        budget: budget,
        readme_context: productInfo.readme || briefSummary,
      });

      const opener = {
        firm: `Hi — I represent ${user.name}. They are ready to close ${product.name} today at $${budget}. That's a firm offer in exchange for a same-day commit.\n\nContext I'm working from: ${briefSummary}`,
        warm: `Hello! I'm ${user.name}'s buying rep. They've been studying ${product.name} and would love to bring it home at $${budget}. Open to bundling Setup if it helps the math.\n\nContext I'm working from: ${briefSummary}`,
        curious: `Hi — quick one on behalf of ${user.name}. They're between ${product.name} and one other piece. Is there room at $${budget}? Happy to add a public review.\n\nContext I'm working from: ${briefSummary}`,
      }[tone];

      await api.send(thread.id, opener, true);
      if (productInfo.mustHaves.trim()) {
        await api.send(thread.id, `Must-haves from ${user.name}: ${productInfo.mustHaves}`, true);
      }
      if (note.trim()) {
        await api.send(thread.id, `Note from ${user.name}: ${note}`, true);
      }

      // Reload chat list
      const store = useStore.getState();
      if ((store as any).loadData) {
        await (store as any).loadData();
      }

      // Trigger negotiate agent reply async
      api.negotiate(thread.id).catch(() => {});

      onClose();
      onOpenInbox();
    } catch (err: any) {
      alert(err.message || "Failed to start negotiation");
    }
  };

  return (
    <Shell open={open} onClose={onClose} max="max-w-xl">
      <Header eyebrow="AI Buyer Rep" title={`Bargain on ${product.name}`} onClose={onClose} icon={<Bot size={14} />} />

      {/* Step indicator */}
      <div className="px-4 sm:px-6 pt-4 flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-text-muted">
        <span className={`flex items-center gap-1.5 ${step === 'brief' ? 'text-accent' : ''}`}><span className={`w-5 h-5 rounded-full grid place-items-center ${step === 'brief' ? 'bg-accent text-[var(--accent-ink)]' : 'hairline'}`}>1</span> Brief</span>
        <span className="flex-1 h-px bg-border-c" />
        <span className={`flex items-center gap-1.5 ${step === 'terms' ? 'text-accent' : ''}`}><span className={`w-5 h-5 rounded-full grid place-items-center ${step === 'terms' ? 'bg-accent text-[var(--accent-ink)]' : 'hairline'}`}>2</span> Terms</span>
      </div>

      <div className="p-4 sm:p-6 space-y-5 overflow-y-auto">
        {!user && (
          <div className="hairline rounded-xl p-4 text-sm">
            Sign in as a buyer to dispatch an AI rep. <span className="text-accent">It's free.</span>
          </div>
        )}
        {user && atLimit && !alreadyForThis && (
          <div className="hairline border-danger/40 rounded-xl p-4 text-sm space-y-3">
            <div>
              You already have <span className="text-danger font-medium">2 active reps</span> in flight. Unassign one to start a new negotiation:
            </div>
            <div className="space-y-2.5">
              {reps.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-2 hairline">
                  <div className="flex items-center gap-2.5">
                    <img src={r.productCover} alt="" className="w-8 h-8 rounded object-cover" />
                    <div className="text-xs">
                      <span className="font-serif block leading-tight">{r.productName}</span>
                      <span className="text-[10px] text-text-muted">Budget: ${r.agentBudget}</span>
                    </div>
                  </div>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (confirm(`Are you sure you want to deactivate the AI representative for ${r.productName}?`)) {
                        await deactivateRep(r.id);
                      }
                    }}
                    className="hairline rounded-lg px-2.5 py-1 text-[11px] text-text-soft hover:border-danger hover:text-danger hover:bg-danger/5 transition-colors cursor-pointer"
                  >
                    Unassign
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {alreadyForThis && (
          <div className="hairline border-accent/40 rounded-xl p-4 text-sm">
            You already have an active rep on this piece. Continue the conversation in your inbox.
          </div>
        )}

        {step === 'brief' ? (
          <>
            <div className="hairline rounded-xl p-3 bg-accent/5 text-xs flex items-start gap-2">
              <FileText size={13} className="text-accent shrink-0 mt-0.5" />
              <span className="text-text-soft">Help your rep speak knowledgeably. Paste a README or describe what you'll use this for — the more it knows, the better it negotiates.</span>
            </div>

            <Label v="Primary use case">
              <input value={productInfo.useCase} onChange={(e) => setProductInfo({ ...productInfo, useCase: e.target.value })}
                placeholder={`e.g. internal admin for a ${product.category.toLowerCase()} workflow`}
                className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent" />
            </Label>

            <Label v="Must-haves (comma-separated)">
              <input value={productInfo.mustHaves} onChange={(e) => setProductInfo({ ...productInfo, mustHaves: e.target.value })}
                placeholder="e.g. SSO, audit log, white-label"
                className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent" />
            </Label>

            <Label v="Timeline">
              <div className="grid grid-cols-3 gap-2">
                {['this week', '30 days', 'q-after-next'].map((t) => (
                  <button key={t} onClick={() => setProductInfo({ ...productInfo, timeline: t })}
                    className={`hairline rounded-xl py-2.5 text-xs capitalize transition-colors ${productInfo.timeline === t ? 'border-accent bg-surface-2/60' : 'active:border-accent/60 md:hover:border-accent/60'}`}>
                    {t}
                  </button>
                ))}
              </div>
            </Label>

            <Label v="README / product info (paste or upload)">
              <textarea value={productInfo.readme} onChange={(e) => setProductInfo({ ...productInfo, readme: e.target.value })}
                rows={4} placeholder="Paste the seller's README, your spec, or any docs you want your rep to absorb."
                className="w-full hairline rounded-xl bg-bg p-3 text-sm outline-none focus:border-accent resize-y" />
              <label className="mt-2 inline-flex items-center gap-2 text-xs text-text-muted cursor-pointer hairline rounded-lg px-3 h-9 active:border-accent md:hover:border-accent">
                <Upload size={12} /> Upload .md / .txt
                <input type="file" accept=".md,.txt,.markdown,.json" className="hidden" onChange={(e) => onReadmeFile(e.target.files?.[0] ?? null)} />
              </label>
              {productInfo.readme && <div className="mt-2 text-[10px] font-mono uppercase tracking-wider text-accent">{productInfo.readme.length} chars absorbed</div>}
            </Label>
          </>
        ) : (
          <>
            {aiSummary && (
              <div className="hairline rounded-xl p-4 bg-surface-2/50 text-sm">
                <div className="flex items-center gap-1.5 text-accent">
                  <Sparkles size={12} /> <span className="font-mono text-[10px] uppercase tracking-wider">Brief absorbed</span>
                </div>
                <p className="mt-2 text-text-soft leading-relaxed">{aiSummary}</p>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Authorized budget</span>
                <span className="font-mono tabular">${budget} <span className="text-text-muted">/ ${product.price}</span></span>
              </div>
              <input type="range" min={Math.round(product.price * 0.5)} max={product.price} value={budget} onChange={(e) => setBudget(+e.target.value)} className="w-full accent-[var(--accent)]" />
              <p className="text-xs text-text-muted mt-2">Your rep will never exceed this without your approval.</p>
            </div>

            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-2">Negotiation tone</div>
              <div className="grid grid-cols-3 gap-2">
                {(['firm', 'warm', 'curious'] as const).map((t) => (
                  <button key={t} onClick={() => setTone(t)} className={`hairline rounded-xl py-3 text-sm capitalize transition-colors ${tone === t ? 'border-accent bg-surface-2/60' : 'md:hover:border-accent/60 active:border-accent/60'}`}>
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <Label v="Final note to your rep (optional)">
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="e.g. Care about a 30-day support window more than a discount."
                className="w-full hairline rounded-xl bg-bg p-3 text-sm outline-none focus:border-accent resize-y" />
            </Label>

            <div className="hairline rounded-xl p-4 bg-surface-2/50 text-xs space-y-1.5">
              <div className="flex items-center gap-2"><Sparkles size={12} className="text-accent" /> Reps negotiate on your behalf, share constraints in plain language, and ping you when they need approval.</div>
              <div className="flex items-center gap-2"><ShieldCheck size={12} className="text-accent" /> Max 2 active reps per buyer. {reps.length}/2 in flight.</div>
            </div>
          </>
        )}
      </div>

      <footer className="p-4 border-t flex flex-wrap gap-3 justify-between items-center bg-surface-2/40">
        {step === 'brief' ? (
          <>
            <button onClick={onClose} className="text-sm text-text-muted">Cancel</button>
            <button onClick={analyzeBrief} disabled={analyzing} className="bg-accent text-[var(--accent-ink)] rounded-xl px-4 sm:px-5 h-11 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-50">
              {analyzing ? 'Reading…' : <>Have AI absorb this <Sparkles size={13} /></>}
            </button>
          </>
        ) : (
          <>
            <button onClick={() => setStep('brief')} className="text-sm text-text-muted">← Back to brief</button>
            <button
              onClick={dispatch}
              disabled={!user || atLimit || !!alreadyForThis}
              className="bg-accent text-[var(--accent-ink)] rounded-xl px-4 sm:px-5 h-11 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40"
            >
              Dispatch the rep <Bot size={14} />
            </button>
          </>
        )}
      </footer>
    </Shell>
  );
}

function Label({ v, children }: { v: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-2">{v}</div>
      {children}
    </label>
  );
}

export function RequestFeaturesModal({ open, onClose, product }: { open: boolean; onClose: () => void; product: Product | null }) {
  const user = useStore((s) => s.user);
  const [features, setFeatures] = useState<string[]>([]);
  const [featurePrices, setFeaturePrices] = useState<Record<string, number>>({
    'Custom branding & domain': 380,
    'Stripe + invoicing integration': 1100,
    'Multi-tenant workspaces': 2400,
    'Role-based permissions': 850,
    'CSV import / export': 420,
    'Mobile-responsive polish': 540,
    'Analytics dashboard': 980,
    'Email notifications': 320,
  });
  const [featureRationales, setFeatureRationales] = useState<Record<string, string>>({});
  const [loadingFeatures, setLoadingFeatures] = useState<Record<string, boolean>>({});

  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const QUICK = ['Custom branding & domain', 'Stripe + invoicing integration', 'Multi-tenant workspaces', 'Role-based permissions', 'CSV import / export', 'Mobile-responsive polish', 'Analytics dashboard', 'Email notifications'];

  const total = features.reduce((sum, f) => sum + (featurePrices[f] ?? 0), 0);
  const toggle = (f: string) => setFeatures((s) => s.includes(f) ? s.filter((x) => x !== f) : [...s, f]);

  const addCustom = async () => {
    const desc = draft.trim();
    if (!desc) return;
    setDraft('');
    setFeatures((s) => [...s, desc]);
    setLoadingFeatures((l) => ({ ...l, [desc]: true }));

    if (USE_MOCKS) {
      setTimeout(() => {
        setFeaturePrices((p) => ({ ...p, [desc]: Math.round(280 + desc.length * 12) }));
        setLoadingFeatures((l) => ({ ...l, [desc]: false }));
      }, 500);
      return;
    }

    try {
      const res = await api.estimateFeature({ listing_id: product?.id ?? '', description: desc });
      setFeaturePrices((p) => ({ ...p, [desc]: res.estimated_charge }));
      setFeatureRationales((r) => ({ ...r, [desc]: res.rationale }));
    } catch (err) {
      setFeaturePrices((p) => ({ ...p, [desc]: Math.round(280 + desc.length * 12) }));
    } finally {
      setLoadingFeatures((l) => ({ ...l, [desc]: false }));
    }
  };

  if (!product) return null;
  return (
    <Shell open={open} onClose={onClose} max="max-w-2xl">
      <Header eyebrow="Custom build" title={`Request features for ${product.name}`} onClose={onClose} icon={<Sparkles size={14} />} />
      <div className="p-6 space-y-5 overflow-y-auto">
        <p className="text-sm text-text-soft">
          Tell us what you need on top of the base piece. Our pricing agent auto-quotes each line based on comparable work — the seller can accept, counter, or substitute.
        </p>

        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-2">Quick picks</div>
          <div className="flex flex-wrap gap-2">
            {QUICK.map((f) => (
              <button key={f} onClick={() => toggle(f)}
                className={`hairline rounded-full px-3 py-1.5 text-xs transition-colors ${features.includes(f) ? 'bg-accent text-[var(--accent-ink)] border-transparent' : 'hover:border-accent'}`}>
                {f} <span className="font-mono opacity-80 ml-1">${featurePrices[f] ?? 0}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="hairline rounded-xl bg-bg p-2 flex gap-2">
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addCustom()} placeholder="Describe a custom feature…" className="flex-1 bg-transparent outline-none px-2 text-sm" />
          <button onClick={addCustom} className="bg-text text-bg rounded-lg px-3 h-9 text-sm">Add</button>
        </div>

        {features.length > 0 && (
          <div className="hairline rounded-xl overflow-hidden">
            <div className="px-4 py-3 bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted flex items-center justify-between">
              <span>Quote · auto-priced</span>
              <span className="flex items-center gap-1"><Sparkles size={10} className="text-accent" /> AI</span>
            </div>
            <ul>
              {features.map((f) => (
                <li key={f} className="px-4 py-3 border-t text-sm">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0 pr-4">
                      <span className="font-medium text-text">{f}</span>
                      {loadingFeatures[f] ? (
                        <span className="block text-xs text-text-muted animate-pulse mt-0.5">AI estimating charge...</span>
                      ) : (
                        featureRationales[f] && (
                          <span className="block text-xs text-text-muted leading-relaxed mt-1">{featureRationales[f]}</span>
                        )
                      )}
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="font-mono tabular">
                        {loadingFeatures[f] ? '$...' : `$${(featurePrices[f] ?? 0).toLocaleString()}`}
                      </span>
                      <button onClick={() => toggle(f)} className="text-text-muted hover:text-danger cursor-pointer"><X size={13} /></button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <div className="px-4 py-3 border-t bg-surface-2/60 flex items-center justify-between">
              <span className="font-serif text-base">Total scope</span>
              <span className="font-mono tabular text-lg">${total.toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
      <footer className="p-4 border-t flex justify-between items-center bg-surface-2/40">
        <button onClick={onClose} className="text-sm text-text-muted">Cancel</button>
        <button
          onClick={async () => {
            if (!product || !features.length) return;
            if (!user && !USE_MOCKS) { toast.error('Sign in to request features'); return; }
            setSubmitting(true);
            const description = features.join('; ');
            if (USE_MOCKS) {
              toast.success('Feature request sent to seller');
              onClose();
              setSubmitting(false);
              return;
            }
            try {
              await api.featureRequest({ listing_id: product.id, description });
              toast.success('Feature request submitted — seller will review the AI estimate');
              onClose();
            } catch (e) {
              toast.error(e instanceof Error ? e.message : 'Request failed');
            } finally {
              setSubmitting(false);
            }
          }}
          disabled={!features.length || submitting}
          className="bg-text text-bg rounded-xl px-5 h-10 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40"
        >
          {submitting ? 'Sending…' : 'Send to seller →'}
        </button>
      </footer>
    </Shell>
  );
}

export function CheckoutModal({ open, onClose, product, tierIndex = 0 }: { open: boolean; onClose: () => void; product: Product | null; tierIndex?: number }) {
  const user = useStore((s) => s.user);
  const recordTransaction = useStore((s) => s.recordTransaction);
  const [step, setStep] = useState<'pay' | 'done'>('pay');
  const [card, setCard] = useState({ number: '4242 4242 4242 4242', exp: '12 / 28', cvc: '123', name: user?.name ?? 'June Park', zip: '10001' });
  const [processing, setProcessing] = useState(false);

  useEffect(() => { if (open) { setStep('pay'); setProcessing(false); } }, [open]);

  if (!product) return null;
  const tier = product.tiers?.[tierIndex] ?? { name: 'Source', price: product.price, features: [] };
  const fee = Math.round(tier.price * 0.02);
  const total = tier.price + fee;

  const submit = async () => {
    setProcessing(true);
    if (USE_MOCKS) {
      setTimeout(() => {
        recordTransaction({
          productId: product.id, productName: product.name,
          buyerId: user?.id ?? 'guest', buyerName: user?.name ?? 'Guest',
          sellerId: sellerIdFor(product), sellerName: product.seller.name,
          tier: tier.name, amount: total, commission: Math.round(tier.price * 0.12), status: 'paid',
        });
        setStep('done'); setProcessing(false);
      }, 1200);
      return;
    }
    try {
      const order = await api.checkout({ listing_id: product.id, tier_index: tierIndex, kind: 'purchase' });
      recordTransaction({
        productId: order.productId, productName: order.productName,
        buyerId: order.buyerId, buyerName: order.buyerName,
        sellerId: order.sellerId, sellerName: order.sellerName,
        tier: order.tier, amount: order.amount, commission: order.commission, status: order.status,
      });
      setStep('done');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Checkout failed');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <Shell open={open} onClose={onClose} max="max-w-3xl">
      <Header eyebrow="Checkout" title={step === 'pay' ? 'Pay & take it home' : 'Order complete'} onClose={onClose} icon={<CreditCard size={14} />} />
      {step === 'pay' ? (
        <div className="grid md:grid-cols-[1fr_320px]">
          <div className="p-6 space-y-4 overflow-y-auto">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Payment details</div>
            <label className="block">
              <div className="text-xs text-text-muted mb-1">Card number</div>
              <div className="hairline rounded-xl bg-bg p-2 flex items-center gap-2">
                <CreditCard size={14} className="ml-1 text-text-muted" />
                <input value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value })} className="flex-1 bg-transparent outline-none font-mono text-sm h-9" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted pr-2">Visa</span>
              </div>
            </label>
            <div className="grid grid-cols-3 gap-3">
              <FieldSimple label="Expiry" value={card.exp} onChange={(v) => setCard({ ...card, exp: v })} />
              <FieldSimple label="CVC" value={card.cvc} onChange={(v) => setCard({ ...card, cvc: v })} />
              <FieldSimple label="ZIP" value={card.zip} onChange={(v) => setCard({ ...card, zip: v })} />
            </div>
            <FieldSimple label="Cardholder" value={card.name} onChange={(v) => setCard({ ...card, name: v })} />
            <div className="hairline rounded-xl bg-surface-2/40 p-3 text-xs flex items-start gap-2">
              <Lock size={13} className="text-accent mt-0.5" />
              <span>Payments are escrowed by Vitrine and released to the seller upon delivery. PCI-DSS handled by our processor — we never see your card.</span>
            </div>
          </div>
          <aside className="border-t md:border-t-0 md:border-l bg-surface-2/40 p-6 flex flex-col">
            <div className="flex gap-3 items-center">
              <img src={product.cover} alt="" className="w-14 h-14 rounded-lg object-cover" />
              <div className="min-w-0">
                <div className="font-serif text-base truncate">{product.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{tier.name}</div>
              </div>
            </div>
            <dl className="mt-6 space-y-2 text-sm">
              <Row k="Tier" v={`$${tier.price.toLocaleString()}`} />
              <Row k="Processing" v={`$${fee.toLocaleString()}`} />
              <div className="border-t pt-3 mt-3 flex justify-between items-baseline">
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Total</span>
                <span className="font-mono text-2xl tabular">${total.toLocaleString()}</span>
              </div>
            </dl>
            <button onClick={submit} disabled={processing} className="mt-auto bg-accent text-[var(--accent-ink)] rounded-xl h-11 font-medium inline-flex items-center justify-center gap-2 disabled:opacity-50">
              {processing ? 'Processing…' : `Pay $${total.toLocaleString()}`}
            </button>
            <p className="text-[10px] text-text-muted mt-3 text-center">By paying you accept our Terms and the seller's license.</p>
          </aside>
        </div>
      ) : (
        <div className="p-10 text-center">
          <div className="w-16 h-16 mx-auto rounded-full gold-gradient grid place-items-center text-[var(--accent-ink)]"><Check size={24} /></div>
          <h3 className="font-serif text-3xl mt-5">It's yours.</h3>
          <p className="text-sm mt-3 max-w-md mx-auto">
            {product.name} is now in your library. Your payment is held in escrow while the seller
            prepares delivery — your license key appears on the order as soon as they deliver.
          </p>
          <button onClick={onClose} className="mt-8 bg-text text-bg rounded-xl px-6 h-11 font-medium">Done</button>
        </div>
      )}
    </Shell>
  );
}

function FieldSimple({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none font-mono text-sm focus:border-accent" />
    </label>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{k}</span>
      <span className="font-mono tabular">{v}</span>
    </div>
  );
}
