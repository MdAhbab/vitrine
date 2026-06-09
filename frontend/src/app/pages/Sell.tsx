import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Github, ArrowRight, Check, Sparkles, Upload, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { SpecSheet } from '../components/SpecSheet';
import { PRODUCTS, type Product, type SpecSection } from '../lib/mockData';
import { api, USE_MOCKS } from '../lib/api';
import { useStore } from '../lib/store';

const STEPS = ['Import', 'Review spec', 'Preview & media', 'Price & pitch', 'Submit'];

function repoName(url: string): string {
  const m = url.match(/github\.com\/[\w.-]+\/([\w.-]+)/i);
  return m ? m[1].replace(/\.git$/, '') : url.split('/').filter(Boolean).pop() || 'New Listing';
}

export function Sell({ onDone }: { onDone: () => void }) {
  const { user } = useStore();
  const [step, setStep] = useState(0);
  const [url, setUrl] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [listingId, setListingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<Product>>({});
  const [spec, setSpec] = useState<SpecSection[]>(PRODUCTS[0].spec);
  const [demoUrl, setDemoUrl] = useState('https://your-app.vercel.app');
  const [tagline, setTagline] = useState('');
  const [price, setPrice] = useState(89);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!analyzing || !USE_MOCKS) return;
    let i = 0;
    const t = setInterval(() => {
      i += 6 + Math.random() * 8;
      setProgress(Math.min(100, i));
      if (i >= 100) {
        clearInterval(t);
        setTimeout(() => { setAnalyzing(false); setStep(1); setSpec(PRODUCTS[0].spec); }, 350);
      }
    }, 180);
    return () => clearInterval(t);
  }, [analyzing]);

  const runIntake = async () => {
    if (!url.trim()) return;
    if (!USE_MOCKS && (!user || user.role === 'buyer')) {
      toast.error('Sign in as a seller to list a piece');
      return;
    }
    setAnalyzing(true);
    setProgress(0);

    if (USE_MOCKS) return;

    try {
      const name = repoName(url.trim());
      const created = await api.createListing({ name, category: 'Web App', tagline: '', price: 0 });
      setListingId(created.id);
      setDraft(created);
      setTagline(created.tagline || '');
      setPrice(created.price || 89);

      const timer = setInterval(() => setProgress((p) => Math.min(95, p + 8)), 400);
      await api.aiIntake(created.id, { repo_url: url.trim().startsWith('http') ? url.trim() : `https://${url.trim()}` });
      clearInterval(timer);
      setProgress(100);

      const updated = await api.listing(created.slug);
      setDraft(updated);
      setSpec(updated.spec?.length ? updated.spec : []);
      setTagline(updated.tagline || tagline);
      setPrice(updated.price || price);
      setStep(1);
      toast.success('Agent drafted your spec sheet');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Intake failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async () => {
    if (USE_MOCKS) {
      setStep(4);
      return;
    }
    if (!listingId) {
      toast.error('No listing to submit');
      return;
    }
    setSubmitting(true);
    try {
      await api.updateListing(listingId, {
        tagline,
        price,
        demo_url: demoUrl,
        description: draft.description || tagline,
      });
      await api.submitListing(listingId);
      setStep(4);
      toast.success('Listing submitted for curator review');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="max-w-[1100px] mx-auto px-6 lg:px-10 pt-12 pb-24">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">For makers</div>
      <h1 className="font-serif mt-3">Place a new piece on the floor</h1>
      <p className="text-text-muted mt-3 max-w-xl">Drop in a repository — our agent reads it, drafts the spec, suggests a price, and gets you to a polished listing in five steps.</p>

      <ol className="mt-10 flex items-center gap-3 flex-wrap">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-3">
            <button
              onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider ${
                i === step ? 'text-text' : i < step ? 'text-accent' : 'text-text-muted'
              }`}
            >
              <span className={`w-6 h-6 grid place-items-center rounded-full hairline ${
                i === step ? 'border-accent text-accent' : i < step ? 'bg-accent text-[var(--accent-ink)] border-accent' : ''
              }`}>
                {i < step ? <Check size={11} /> : i + 1}
              </span>
              {s}
            </button>
            {i < STEPS.length - 1 && <span className="w-6 h-px bg-border-c" />}
          </li>
        ))}
      </ol>

      <div className="mt-12 hairline rounded-2xl bg-surface p-8 min-h-[420px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.3 }}
          >
            {step === 0 && (
              <div className="space-y-6 max-w-2xl">
                <div>
                  <h2 className="font-serif text-2xl">Step 1 · Import</h2>
                  <p className="text-text-muted mt-2 text-sm">Paste your GitHub URL. The agent will read the repo and draft the listing.</p>
                </div>
                <div className="hairline rounded-xl bg-bg flex items-center gap-2 p-2 focus-within:border-accent transition-colors">
                  <Github size={16} className="ml-2 text-text-muted" />
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="github.com/your-org/your-repo"
                    className="flex-1 bg-transparent outline-none text-sm py-2"
                  />
                  <button
                    onClick={runIntake}
                    disabled={!url.trim() || analyzing}
                    className="bg-text text-bg rounded-lg px-4 h-9 text-sm font-medium disabled:opacity-30 inline-flex items-center gap-1.5"
                  >
                    Analyze <ArrowRight size={13} />
                  </button>
                </div>

                <div className="text-center font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">or</div>

                <label className="hairline border-dashed rounded-xl p-8 grid place-items-center text-center cursor-pointer hover:border-accent transition-colors block">
                  <Upload size={18} className="text-text-muted" />
                  <div className="text-sm mt-2">Drop a README or zip</div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-1">Or click to browse</div>
                  <input type="file" className="hidden" />
                </label>

                {analyzing && (
                  <div className="mt-4 hairline rounded-xl p-5 bg-bg">
                    <div className="flex items-center gap-2.5 text-sm">
                      <Loader2 size={14} className="animate-spin text-accent" />
                      <span>AI is reading your repository…</span>
                      <span className="ml-auto font-mono text-xs tabular text-text-muted">{progress.toFixed(0)}%</span>
                    </div>
                    <div className="h-1 mt-3 bg-surface-2 rounded-full overflow-hidden">
                      <motion.div animate={{ width: `${progress}%` }} className="h-full bg-accent" />
                    </div>
                    <ul className="mt-3 space-y-1 font-mono text-[11px] text-text-muted">
                      <li>· detecting framework & stack</li>
                      <li>· extracting README and routes</li>
                      <li>· composing the spec sheet</li>
                    </ul>
                  </div>
                )}
              </div>
            )}

            {step === 1 && (
              <div className="space-y-6">
                <div className="flex items-end justify-between flex-wrap gap-4">
                  <div>
                    <h2 className="font-serif text-2xl">Step 2 · Review the spec</h2>
                    <p className="text-text-muted mt-2 text-sm flex items-center gap-1.5"><Sparkles size={13} className="text-accent" /> Fields marked auto were drafted by the agent — confirm or edit before submitting.</p>
                  </div>
                </div>
                <SpecSheet sections={spec.length ? spec : PRODUCTS[0].spec} />
              </div>
            )}

            {step === 2 && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="font-serif text-2xl">Step 3 · Preview & media</h2>
                <div>
                  <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Live demo URL</label>
                  <div className="mt-2 hairline rounded-xl bg-bg flex items-center gap-2 p-2">
                    <input value={demoUrl} onChange={(e) => setDemoUrl(e.target.value)} className="flex-1 bg-transparent outline-none text-sm py-2 px-2 font-mono" />
                    <span className="flex items-center gap-1.5 px-3 font-mono text-[10px] uppercase tracking-wider text-success"><span className="live-dot" /> healthy</span>
                  </div>
                </div>
                <div>
                  <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Screenshots</label>
                  <div className="grid grid-cols-3 gap-3 mt-2">
                    {(draft.screenshots || PRODUCTS[0].screenshots).slice(0, 3).map((s, i) => (
                      <div key={i} className="aspect-[4/3] rounded-xl overflow-hidden hairline">
                        <img src={s} alt="" className="w-full h-full object-cover" />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-6 max-w-2xl">
                <h2 className="font-serif text-2xl">Step 4 · Price & pitch</h2>
                <p className="text-text-muted text-sm flex items-center gap-1.5"><Sparkles size={13} className="text-accent" /> Pricing & Pitch Agent suggested these tiers based on comparable pieces.</p>
                <div className="grid sm:grid-cols-3 gap-3">
                  {[
                    { name: 'Source', price: price, note: 'Just the code' },
                    { name: 'Source + Setup', price: price + 80, note: 'Recommended', rec: true },
                    { name: 'Bespoke', price: price + 280, note: 'White-glove' },
                  ].map((t) => (
                    <div key={t.name} className={`hairline rounded-xl p-4 ${t.rec ? 'border-accent bg-surface-2/40' : ''}`}>
                      <div className="font-serif text-lg">{t.name}</div>
                      <div className="font-mono text-2xl tabular mt-2">${t.price}</div>
                      <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-1">{t.note}</div>
                    </div>
                  ))}
                </div>
                <div>
                  <label className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Drafted tagline</label>
                  <input
                    value={tagline}
                    onChange={(e) => setTagline(e.target.value)}
                    placeholder="A quiet operations cockpit, framed for the long haul."
                    className="mt-2 w-full hairline rounded-xl bg-bg px-4 h-11 text-sm font-serif"
                  />
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-6 text-center py-10">
                <div className="w-16 h-16 rounded-full grid place-items-center gold-gradient text-[var(--accent-ink)] mx-auto">
                  <Check size={24} />
                </div>
                <h2 className="font-serif text-3xl">Submitted</h2>
                <p className="text-text-muted text-sm max-w-md mx-auto">
                  Your piece is in verification. Curators usually respond within 24 hours. You'll get an email when it's framed and on the wall.
                </p>
                <button onClick={onDone} className="inline-flex items-center gap-2 text-sm group">
                  <span className="border-b border-text pb-0.5">Back to the gallery</span>
                  <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                </button>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {step > 0 && step < 4 && (
          <div className="flex items-center justify-between mt-10 pt-6 border-t">
            <button onClick={() => setStep((s) => Math.max(0, s - 1))} className="text-sm text-text-muted hover:text-text">← Back</button>
            <button
              onClick={() => step === 3 ? handleSubmit() : setStep((s) => Math.min(4, s + 1))}
              disabled={submitting}
              className="bg-text text-bg rounded-full px-5 h-10 text-sm font-medium inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {step === 3 ? (submitting ? 'Submitting…' : 'Submit listing') : 'Continue'} <ArrowRight size={13} />
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
