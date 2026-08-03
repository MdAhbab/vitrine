import { useEffect, useState } from 'react';
import { X, Bot, Sparkles, Trash2, Save, Loader2, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { api, mediaUrl, USE_MOCKS } from '../lib/api';
import { Dialog } from './Dialog';
import { PromptDialog, type PromptRequest } from './PromptDialog';
import { useStore, type Listing } from '../lib/store';
import { MediaPicker, MediaPickerMulti } from './MediaPicker';
import { Typewriter } from './Typewriter';

type Mode = 'view' | 'edit';

export function ListingEditor({
  listing, mode: initialMode, onClose,
}: { listing: Listing; mode: Mode; onClose: () => void }) {
  const upsertListing = useStore((s) => s.upsertListing);
  const deleteListing = useStore((s) => s.deleteListing);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [draft, setDraft] = useState<Listing>(listing);
  const [drafting, setDrafting] = useState(false);
  const [prompt, setPrompt] = useState<PromptRequest | null>(null);

  useEffect(() => { setDraft(listing); setMode(initialMode); }, [listing, initialMode]);

  const update = <K extends keyof Listing>(k: K, v: Listing[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const updateSdlc = (k: keyof Listing['sdlc'], v: string) => setDraft((d) => ({ ...d, sdlc: { ...d.sdlc, [k]: v } }));
  const updateBusiness = (k: keyof Listing['businessModel'], v: any) => setDraft((d) => ({ ...d, businessModel: { ...d.businessModel, [k]: v } }));

  // Ask the real Pricing & Pitch agent for the copy. This used to be a 900ms
  // fake delay followed by hardcoded string templates and an invented tech
  // stack, all under a banner reading "filled by our AI" — the button never
  // touched the network.
  const aiRedraft = async () => {
    if (USE_MOCKS) return;
    if (!draft.name?.trim()) {
      toast.error('Give the piece a name first — the agent drafts from it.');
      return;
    }
    setDrafting(true);
    try {
      // Persist the basics so the agent reasons over what the seller actually typed.
      await api.updateListing(draft.id, {
        name: draft.name, category: draft.category,
        framework: draft.framework, price: draft.price,
      });
      const res = await api.pricing(draft.id);
      if (res?.stub) {
        toast.error('The drafting agent is unavailable right now. Try again shortly.');
        return;
      }
      setDraft((d) => ({
        ...d,
        tagline: d.tagline || res.tagline || d.tagline,
        description: d.description || res.long_description || res.short_description || d.description,
        businessModel: {
          ...d.businessModel,
          pitch: d.businessModel.pitch || res.short_description || '',
        },
        aiDraft: true,
      }));
      toast.success('Draft updated by the Pricing & Pitch agent');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Drafting failed');
    } finally {
      setDrafting(false);
    }
  };

  const save = () => { upsertListing({ ...draft, aiDraft: false }); setMode('view'); };
  const remove = () => setPrompt({
    title: `Delete "${listing.name}"?`,
    description: 'This removes the listing from your window permanently. It cannot be undone.',
    confirmLabel: 'Delete listing',
    danger: true,
    onConfirm: () => { deleteListing(listing.id); onClose(); },
  });

  return (
    <Dialog
      open
      onClose={onClose}
      label={`Listing ${draft.name}`}
      panelClassName="max-w-4xl w-full hairline rounded-2xl bg-bg shadow-2xl max-h-[90vh] overflow-y-auto outline-none"
    >
      <div>
          {/* Header */}
          <header className="sticky top-0 bg-bg/95 backdrop-blur border-b z-10 px-6 lg:px-8 py-4 flex items-center justify-between rounded-t-2xl">
            <div className="flex items-center gap-3 min-w-0">
              <img src={mediaUrl(draft.cover)} alt="" className="w-10 h-10 rounded-lg object-cover" />
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{mode === 'view' ? 'Listing' : 'Editing'}</div>
                <div className="font-serif text-lg truncate">{draft.name}</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {mode === 'view' ? (
                <>
                  <button onClick={() => setMode('edit')} className="hairline rounded-lg px-3 h-9 text-sm hover:border-accent">Edit</button>
                  <button onClick={remove} className="hairline rounded-lg w-11 h-11 grid place-items-center hover:border-danger hover:text-danger" aria-label="Delete"><Trash2 size={14} /></button>
                </>
              ) : (
                <>
                  <button onClick={aiRedraft} disabled={drafting} className="group hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:border-accent hover:text-accent">
                    {drafting ? <Loader2 size={13} className="animate-spin" /> : <Bot size={13} className="text-accent" />}
                    <Typewriter words={['AI redraft', 'Draft from idea', 'Fill in the gaps']} className="font-mono text-[11px] uppercase tracking-wider" />
                  </button>
                  <button onClick={save} className="bg-text text-bg rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2"><Save size={13} /> Save</button>
                </>
              )}
              <button onClick={onClose} className="hairline rounded-lg w-11 h-11 grid place-items-center hover:border-accent" aria-label="Close"><X size={14} /></button>
            </div>
          </header>

          <div className="px-6 lg:px-8 py-8 space-y-8">
            {/* AI draft notice */}
            {draft.aiDraft && (
              <div className="hairline border-accent/40 bg-accent/5 rounded-xl p-4 text-sm flex items-start gap-3">
                <Sparkles size={14} className="text-accent shrink-0 mt-0.5" />
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-accent">AI draft · review before publish</div>
                  <p className="text-text-soft mt-1">These fields were filled by our AI based on your title and category. Adjust anything that doesn't feel like you.</p>
                </div>
              </div>
            )}

            {/* Media */}
            <Section title="Cover & screenshots" hint="Paste a URL or upload images (max 10 MB each).">
              {mode === 'view' ? (
                <div className="flex gap-3 flex-wrap">
                  {draft.cover && <img src={mediaUrl(draft.cover)} alt="" className="w-32 h-20 rounded-lg object-cover hairline" />}
                  {draft.screenshots?.map((s, i) => (
                    <img key={i} src={mediaUrl(s)} alt="" className="w-32 h-20 rounded-lg object-cover hairline" />
                  ))}
                </div>
              ) : (
                <>
                  <MediaPicker value={draft.cover} onChange={(v) => update('cover', v)} bucket="listings" label="Cover image" />
                  <MediaPickerMulti values={draft.screenshots ?? []} onChange={(v) => update('screenshots', v)} bucket="listings" label="Screenshots" />
                </>
              )}
            </Section>

            {/* Basics */}
            <Section title="Basics">
              <Field label="Name">
                <Input v={draft.name} mode={mode} onChange={(v) => update('name', v)} />
              </Field>
              <Field label="Tagline">
                <Input v={draft.tagline} mode={mode} onChange={(v) => update('tagline', v)} />
              </Field>
              <div className="grid sm:grid-cols-3 gap-4">
                <Field label="Category"><Input v={draft.category} mode={mode} onChange={(v) => update('category', v)} /></Field>
                <Field label="Framework"><Input v={draft.framework} mode={mode} onChange={(v) => update('framework', v)} /></Field>
                <Field label="Price ($)"><Input v={String(draft.price)} mode={mode} onChange={(v) => update('price', Number(v) || 0)} type="number" /></Field>
              </div>
            </Section>

            {/* SDLC */}
            <Section title="Software development lifecycle" hint="AI drafts these; you keep the final word.">
              <Field label="Problem statement"><TextArea v={draft.sdlc.problem} mode={mode} onChange={(v) => updateSdlc('problem', v)} /></Field>
              <Field label="Solution"><TextArea v={draft.sdlc.solution} mode={mode} onChange={(v) => updateSdlc('solution', v)} /></Field>
              <Field label="Methodology"><TextArea v={draft.sdlc.methodology} mode={mode} onChange={(v) => updateSdlc('methodology', v)} /></Field>
              <Field label="Discussions"><TextArea v={draft.sdlc.discussions} mode={mode} onChange={(v) => updateSdlc('discussions', v)} /></Field>
            </Section>

            {/* Business model */}
            <Section title="Business model" hint="What kind of project is this — for-profit, non-profit, sole-purpose, or open source?">
              <Field label="Kind">
                {mode === 'view' ? (
                  <div className="capitalize text-sm">{draft.businessModel.kind.replace('-', ' ')}</div>
                ) : (
                  <select
                    value={draft.businessModel.kind}
                    onChange={(e) => updateBusiness('kind', e.target.value as Listing['businessModel']['kind'])}
                    className="w-full hairline rounded-lg bg-surface-2 px-3 h-10 text-sm"
                  >
                    <option value="for-profit">For-profit</option>
                    <option value="non-profit">Non-profit</option>
                    <option value="sole-purpose">Sole-purpose</option>
                    <option value="open-source">Open-source</option>
                  </select>
                )}
              </Field>
              <Field label="Pitch"><TextArea v={draft.businessModel.pitch} mode={mode} onChange={(v) => updateBusiness('pitch', v)} /></Field>
              <Field label="Revenue streams">
                <TagList
                  items={draft.businessModel.revenueStreams}
                  mode={mode}
                  onChange={(items) => updateBusiness('revenueStreams', items)}
                />
              </Field>
            </Section>

            {/* Tech stack */}
            <Section title="Tech stack" hint="Initial list is AI-drafted from your framework — refine to match reality.">
              <TagList items={draft.techStack} mode={mode} onChange={(items) => update('techStack', items)} />
            </Section>
          </div>
      </div>
      <PromptDialog request={prompt} onClose={() => setPrompt(null)} />
    </Dialog>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent">{title}</div>
        {hint && <p className="text-xs text-text-muted mt-1">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">{label}</div>
      {children}
    </label>
  );
}

function Input({ v, mode, onChange, type = 'text' }: { v: string; mode: Mode; onChange: (v: string) => void; type?: string }) {
  if (mode === 'view') return <div className="text-sm">{v || <span className="text-text-muted italic">—</span>}</div>;
  return (
    <input
      type={type}
      value={v}
      onChange={(e) => onChange(e.target.value)}
      className="w-full hairline rounded-lg bg-surface-2 px-3 h-10 text-sm focus:border-accent outline-none"
    />
  );
}

function TextArea({ v, mode, onChange }: { v: string; mode: Mode; onChange: (v: string) => void }) {
  if (mode === 'view') return <p className="text-sm text-text-soft leading-relaxed whitespace-pre-wrap">{v || <span className="text-text-muted italic">—</span>}</p>;
  return (
    <textarea
      value={v}
      onChange={(e) => onChange(e.target.value)}
      rows={3}
      className="w-full hairline rounded-lg bg-surface-2 px-3 py-2 text-sm focus:border-accent outline-none resize-y"
    />
  );
}

function TagList({ items, mode, onChange }: { items: string[]; mode: Mode; onChange: (items: string[]) => void }) {
  const [val, setVal] = useState('');
  const add = () => {
    const v = val.trim();
    if (!v) return;
    onChange([...items, v]);
    setVal('');
  };
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {items.map((it, i) => (
          <span key={`${it}-${i}`} className="hairline rounded-full pl-3 pr-1 py-1 text-xs font-mono inline-flex items-center gap-1.5">
            {it}
            {mode === 'edit' && (
              <button onClick={() => onChange(items.filter((_, j) => j !== i))} className="w-4 h-4 rounded-full hover:bg-danger/20 grid place-items-center" aria-label="Remove">
                <X size={9} />
              </button>
            )}
          </span>
        ))}
        {items.length === 0 && <span className="text-xs text-text-muted italic">No items yet.</span>}
      </div>
      {mode === 'edit' && (
        <div className="flex gap-2">
          <input
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
            placeholder="Add item and press Enter"
            className="flex-1 hairline rounded-lg bg-surface-2 px-3 h-9 text-sm focus:border-accent outline-none"
          />
          <button onClick={add} className="hairline rounded-lg w-11 h-11 grid place-items-center hover:border-accent" aria-label="Add"><Plus size={13} /></button>
        </div>
      )}
    </div>
  );
}
