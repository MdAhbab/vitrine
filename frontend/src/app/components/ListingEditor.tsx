import { useEffect, useState } from 'react';
import { X, Bot, Sparkles, Trash2, Save, Loader2, Plus, Star, SlidersHorizontal, Check } from 'lucide-react';
import { toast } from 'sonner';
import { api, mediaUrl, USE_MOCKS } from '../lib/api';
import { Dialog } from './Dialog';
import { PromptDialog, type PromptRequest } from './PromptDialog';
import { useStore, type Listing } from '../lib/store';
import { MediaPicker, MediaPickerMulti } from './MediaPicker';
import { Typewriter } from './Typewriter';

type Mode = 'view' | 'edit';

/** One row of the pricing ladder, exactly as `PATCH /listings/{id}` stores it. */
type Tier = NonNullable<Listing['tiers']>[number];

/** How the seller is setting their ladder on this visit. */
type PricingPath = 'ai' | 'manual';

/** Coerce an agent payload into tiers we are willing to show and store. */
function normalizeTiers(raw: unknown): Tier[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((t): t is Record<string, unknown> => Boolean(t) && typeof t === 'object')
    .map((t) => ({
      name: String(t.name ?? '').trim(),
      price: Math.max(0, Math.round(Number(t.price) || 0)),
      features: Array.isArray(t.features) ? t.features.map((f) => String(f).trim()).filter(Boolean) : [],
      recommended: Boolean(t.recommended),
    }))
    .filter((t) => t.name.length > 0);
}

export function ListingEditor({
  listing, mode: initialMode, onClose, resolveId,
}: {
  listing: Listing;
  mode: Mode;
  onClose: () => void;
  /**
   * Set when the parent opened this editor over a listing it is still creating
   * server-side, so the form can appear instantly instead of after a round
   * trip. Resolves to the real listing id; every write awaits it first.
   */
  resolveId?: Promise<string>;
}) {
  const upsertListing = useStore((s) => s.upsertListing);
  const deleteListing = useStore((s) => s.deleteListing);
  const loadData = useStore((s) => s.loadData);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [draft, setDraft] = useState<Listing>(listing);
  const [drafting, setDrafting] = useState(false);
  const [draftStage, setDraftStage] = useState('');
  const [prompt, setPrompt] = useState<PromptRequest | null>(null);
  const [creating, setCreating] = useState(Boolean(resolveId));
  // Pricing is a choice, not a default: a listing that already has a ladder
  // opens on the manual editor, an empty one offers the agent first.
  const [pricingPath, setPricingPath] = useState<PricingPath>(listing.tiers?.length ? 'manual' : 'ai');
  // The agent's proposal lives OUTSIDE `draft` on purpose — AGENTS.md §4 makes
  // the Pricing agent advisory, so nothing it returns reaches the listing until
  // the seller presses "Use these tiers".
  const [proposal, setProposal] = useState<Tier[] | null>(null);
  const [compsAvg, setCompsAvg] = useState<number | null>(null);
  const [pricingBusy, setPricingBusy] = useState(false);

  useEffect(() => {
    setDraft(listing);
    setMode(initialMode);
    setProposal(null);
    setCompsAvg(null);
    setPricingPath(listing.tiers?.length ? 'manual' : 'ai');
  }, [listing, initialMode]);

  useEffect(() => {
    if (!resolveId) { setCreating(false); return; }
    let live = true;
    setCreating(true);
    resolveId
      .then((id) => { if (live) setDraft((d) => ({ ...d, id })); })
      .catch(() => { /* the parent surfaces the failure */ })
      .finally(() => { if (live) setCreating(false); });
    return () => { live = false; };
  }, [resolveId]);

  /** The server-side id, waiting for the background create if one is in flight. */
  const listingId = async () => (resolveId ? await resolveId : draft.id);

  const update = <K extends keyof Listing>(k: K, v: Listing[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const updateSdlc = (k: keyof Listing['sdlc'], v: string) => setDraft((d) => ({ ...d, sdlc: { ...d.sdlc, [k]: v } }));
  const updateBusiness = (k: keyof Listing['businessModel'], v: any) => setDraft((d) => ({ ...d, businessModel: { ...d.businessModel, [k]: v } }));

  // The drafting button drives two different agents depending on what the
  // seller has given us:
  //
  //   repo URL present -> Repo-Intake reads the repository and fills the whole
  //                       form sheet (stack, spec, description, tags). This is
  //                       the path AGENTS.md §1 describes and the one sellers
  //                       expect from "AI-draft"; it was unreachable from this
  //                       editor because there was no field to put a repo in.
  //   no repo URL      -> Pricing & Pitch drafts copy from the name/category
  //                       alone, which is all it can honestly do.
  const aiRedraft = async () => {
    if (USE_MOCKS) return;
    if (!draft.name?.trim()) {
      toast.error('Give the piece a name first — the agent drafts from it.');
      return;
    }
    const repo = draft.repoUrl?.trim();
    setDrafting(true);
    try {
      const id = await listingId();
      // Persist what the seller typed so the agents reason over it, not over
      // the placeholder row.
      setDraftStage('Saving your inputs…');
      await api.updateListing(id, {
        name: draft.name, category: draft.category,
        framework: draft.framework, price: draft.price,
        repo_url: repo || null, demo_url: draft.demoUrl?.trim() || null,
      });

      if (repo) {
        setDraftStage('Reading the repository…');
        const res = await api.aiIntake(id, {
          repo_url: repo.startsWith('http') ? repo : `https://${repo}`,
        });
        if (res?.stub) {
          toast.error('The intake agent is unavailable right now. Try again shortly.');
          return;
        }
        if (!res?.enriched) {
          toast.error("The agent couldn't read that repository. Check the URL is public, or clear it to draft from the name alone.");
          return;
        }
        // Intake writes straight to the row, so re-read rather than guess.
        setDraftStage('Loading the drafted sheet…');
        await loadData();
        const fresh = useStore.getState().listings.find((l) => l.id === id);
        if (fresh) setDraft({ ...fresh, aiDraft: true });
        toast.success(`Repo-Intake filled ${res.fields_written} field(s) from your repository`);
        return;
      }

      setDraftStage('Drafting copy…');
      const res = await api.pricing(id);
      if (res?.stub) {
        toast.error('The drafting agent is unavailable right now. Try again shortly.');
        return;
      }
      setDraft((d) => ({
        ...d,
        id,
        tagline: d.tagline || res.tagline || d.tagline,
        description: d.description || res.long_description || res.short_description || d.description,
        businessModel: {
          ...d.businessModel,
          pitch: d.businessModel.pitch || res.short_description || '',
        },
        aiDraft: true,
      }));
      // The same call already priced the piece. Park the ladder as a proposal
      // rather than applying it — copy is a draft the seller edits in place,
      // pricing is a decision they have to make.
      const suggested = normalizeTiers(res?.suggested_tiers ?? res?.tiers);
      if (suggested.length) {
        setProposal(suggested);
        setCompsAvg(typeof res?.comps?.average_market_price === 'number' ? res.comps.average_market_price : null);
        setPricingPath('ai');
      }
      toast.success(
        suggested.length
          ? 'Draft updated. The agent also proposed a pricing ladder — review it under Pricing tiers.'
          : 'Draft updated by the Pricing & Pitch agent. Add a repository URL for a full spec sheet.',
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Drafting failed');
    } finally {
      setDrafting(false);
      setDraftStage('');
    }
  };

  const tiers: Tier[] = draft.tiers ?? [];
  const setTiers = (next: Tier[]) => update('tiers', next);

  /** Ask the Pricing & Pitch agent for a ladder. Nothing is applied here. */
  const askPricing = async () => {
    if (USE_MOCKS) return;
    setPricingBusy(true);
    try {
      const id = await listingId();
      // Price against what the seller has actually typed, not the placeholder
      // row the draft was created with.
      await api.updateListing(id, {
        name: draft.name, category: draft.category,
        tagline: draft.tagline, price: draft.price,
      });
      const res = await api.pricing(id);
      // AGENTS.md §7: a stub carries no usable model output. Never dress it up
      // as a proposal — say so plainly and leave the manual path open.
      if (res?.stub) {
        toast.error('The pricing agent is unavailable right now. Set your tiers manually instead.');
        return;
      }
      const suggested = normalizeTiers(res?.suggested_tiers ?? res?.tiers);
      if (!suggested.length) {
        toast.error("The pricing agent didn't return a usable ladder. Try again, or set your tiers manually.");
        return;
      }
      setProposal(suggested);
      setCompsAvg(typeof res?.comps?.average_market_price === 'number' ? res.comps.average_market_price : null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'The pricing agent could not be reached.');
    } finally {
      setPricingBusy(false);
    }
  };

  const acceptProposal = () => {
    if (!proposal?.length) return;
    setTiers(proposal);
    setProposal(null);
    // Once accepted the ladder is the seller's, so hand them the editable view.
    setPricingPath('manual');
    toast.success('Tiers accepted — adjust anything you like, then Save.');
  };

  const save = async () => {
    // The API refuses a nameless tier, and upsertListing swallows the error —
    // so catch it here rather than letting the editor close on a save that
    // silently did nothing.
    if (tiers.some((t) => !t.name.trim())) {
      toast.error('Every tier needs a name — fill it in, or remove the tier.');
      setPricingPath('manual');
      return;
    }
    try {
      const id = await listingId();
      await upsertListing({ ...draft, id, aiDraft: false });
      setDraft((d) => ({ ...d, id, aiDraft: false }));
      setMode('view');
    } catch {
      // Reachable only when the background create failed. Stay in edit mode so
      // the seller's typing survives rather than switching to a view of a row
      // that was never persisted.
      toast.error('This draft never reached the server. Close and start it again.');
    }
  };
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
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted inline-flex items-center gap-1.5">
                  {mode === 'view' ? 'Listing' : 'Editing'}
                  {creating && <><Loader2 size={9} className="animate-spin" /> saving draft…</>}
                </div>
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
                  <button onClick={aiRedraft} disabled={drafting} className="group hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:border-accent hover:text-accent disabled:opacity-60">
                    {drafting ? <Loader2 size={13} className="animate-spin" /> : <Bot size={13} className="text-accent" />}
                    {drafting
                      ? <span className="font-mono text-[11px] uppercase tracking-wider">{draftStage || 'Drafting…'}</span>
                      : <Typewriter words={['AI redraft', 'Draft from repo', 'Fill in the gaps']} className="font-mono text-[11px] uppercase tracking-wider" />}
                  </button>
                  <button onClick={save} disabled={drafting} className="bg-text text-bg rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 disabled:opacity-60"><Save size={13} /> Save</button>
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

            {/* Pricing tiers */}
            <Section
              title="Pricing tiers"
              hint="The packages a buyer chooses between. Let the Pricing & Pitch agent propose a ladder from comparable live listings, or set one yourself — the agent only ever suggests."
            >
              {mode === 'view' ? (
                <TierSummary tiers={tiers} />
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2">
                    <PathButton
                      active={pricingPath === 'ai'}
                      onClick={() => setPricingPath('ai')}
                      icon={<Bot size={13} />}
                      label="Use the AI's suggestion"
                    />
                    <PathButton
                      active={pricingPath === 'manual'}
                      onClick={() => setPricingPath('manual')}
                      icon={<SlidersHorizontal size={13} />}
                      label="Set pricing manually"
                    />
                  </div>

                  {pricingPath === 'ai' ? (
                    proposal ? (
                      <div className="hairline border-accent/40 bg-accent/5 rounded-xl p-4 space-y-4">
                        <div className="flex items-start gap-3">
                          <Sparkles size={14} className="text-accent shrink-0 mt-0.5" />
                          <div>
                            <div className="font-mono text-[10px] uppercase tracking-wider text-accent">Proposed · not applied yet</div>
                            <p className="text-text-soft text-xs mt-1">
                              {compsAvg
                                ? `Anchored against comparable live listings (avg $${Math.round(compsAvg).toLocaleString()}). `
                                : ''}
                              Edit anything below, then accept — nothing is saved to your listing until you do.
                            </p>
                          </div>
                        </div>
                        <TierRows tiers={proposal} onChange={setProposal} />
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={acceptProposal}
                            className="bg-text text-bg rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:opacity-90"
                          >
                            <Check size={13} /> Use these tiers
                          </button>
                          <button
                            onClick={() => { setProposal(null); setCompsAvg(null); }}
                            className="hairline rounded-lg px-3 h-9 text-sm hover:border-danger hover:text-danger"
                          >
                            Discard
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="hairline rounded-xl bg-surface-2 p-4 space-y-3">
                        <p className="text-xs text-text-soft leading-relaxed">
                          The agent reads live comparables in your category and proposes three packages
                          anchored to them. You review and edit before anything is applied.
                        </p>
                        <button
                          onClick={askPricing}
                          disabled={pricingBusy || drafting}
                          className="hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:border-accent hover:text-accent disabled:opacity-60"
                        >
                          {pricingBusy ? <Loader2 size={13} className="animate-spin" /> : <Bot size={13} className="text-accent" />}
                          <span className="font-mono text-[11px] uppercase tracking-wider">
                            {pricingBusy ? 'Reading comparables…' : 'Ask the pricing agent'}
                          </span>
                        </button>
                        <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                          {tiers.length
                            ? `On this listing now · ${tiers.length} tier${tiers.length === 1 ? '' : 's'}`
                            : 'No tiers on this listing yet'}
                        </div>
                      </div>
                    )
                  ) : (
                    <div className="space-y-3">
                      <TierRows tiers={tiers} onChange={setTiers} />
                      <button
                        onClick={() => setTiers([...tiers, { name: '', price: draft.price || 0, features: [], recommended: false }])}
                        className="hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 hover:border-accent"
                      >
                        <Plus size={13} /> Add a tier
                      </button>
                    </div>
                  )}
                </div>
              )}
            </Section>

            {/* Links */}
            <Section
              title="Links"
              hint="Paste a public repository URL and the AI redraft button reads it — stack, spec sheet, description, and tags come back filled. Without one, the agent can only draft copy from your title."
            >
              <Field label="Repository URL">
                <Input v={draft.repoUrl ?? ''} mode={mode} onChange={(v) => update('repoUrl', v)} placeholder="https://github.com/you/your-project" />
              </Field>
              <Field label="Demo URL">
                <Input v={draft.demoUrl ?? ''} mode={mode} onChange={(v) => update('demoUrl', v)} placeholder="https://your-project.vercel.app" />
              </Field>
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

function Input({ v, mode, onChange, type = 'text', placeholder }: { v: string; mode: Mode; onChange: (v: string) => void; type?: string; placeholder?: string }) {
  if (mode === 'view') return <div className="text-sm">{v || <span className="text-text-muted italic">—</span>}</div>;
  return (
    <input
      type={type}
      value={v}
      placeholder={placeholder}
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

function PathButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`hairline rounded-lg px-3 h-9 text-sm inline-flex items-center gap-2 transition-colors ${
        active ? 'border-accent text-accent bg-accent/5' : 'text-text-soft hover:border-accent'
      }`}
    >
      {icon}
      <span className="font-mono text-[11px] uppercase tracking-wider">{label}</span>
    </button>
  );
}

/** Read-only ladder, for `view` mode and the product page's own ordering. */
function TierSummary({ tiers }: { tiers: Tier[] }) {
  if (!tiers.length) return <p className="text-sm text-text-muted italic">No tiers yet — buyers see the base price only.</p>;
  return (
    <div className="grid sm:grid-cols-3 gap-3">
      {tiers.map((t, i) => (
        <div key={`${t.name}-${i}`} className={`hairline rounded-xl p-4 ${t.recommended ? 'border-accent/40 bg-accent/5' : 'bg-surface-2'}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted truncate">{t.name}</div>
            {t.recommended && <Star size={11} className="text-accent shrink-0" fill="currentColor" />}
          </div>
          <div className="font-serif text-xl mt-1">${t.price.toLocaleString()}</div>
          <ul className="mt-2 space-y-1">
            {t.features.map((f, j) => (
              <li key={`${f}-${j}`} className="text-xs text-text-soft flex items-start gap-1.5">
                <Check size={11} className="text-accent shrink-0 mt-0.5" /> {f}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/**
 * Editable ladder. Shared by the manual path and the AI proposal card so a
 * suggestion can be tweaked before it is accepted.
 */
function TierRows({ tiers, onChange }: { tiers: Tier[]; onChange: (tiers: Tier[]) => void }) {
  const patch = (i: number, fields: Partial<Tier>) =>
    onChange(tiers.map((t, j) => (j === i ? { ...t, ...fields } : t)));
  // "Recommended" is the one tier the product page highlights, so it behaves
  // like a radio: promoting one demotes the rest.
  const promote = (i: number) =>
    onChange(tiers.map((t, j) => ({ ...t, recommended: j === i ? !t.recommended : false })));

  if (!tiers.length) {
    return <p className="text-sm text-text-muted italic">No tiers yet. Add one below, or ask the pricing agent.</p>;
  }
  return (
    <div className="space-y-3">
      {tiers.map((t, i) => (
        <div key={i} className="hairline rounded-xl bg-surface-2 p-4 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[10rem]">
              <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">Tier name</div>
              <input
                value={t.name}
                placeholder="Source"
                onChange={(e) => patch(i, { name: e.target.value })}
                className="w-full hairline rounded-lg bg-bg px-3 h-10 text-sm focus:border-accent outline-none"
              />
            </div>
            <div className="w-28">
              <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">Price ($)</div>
              <input
                type="number"
                min={0}
                value={String(t.price)}
                onChange={(e) => patch(i, { price: Math.max(0, Number(e.target.value) || 0) })}
                className="w-full hairline rounded-lg bg-bg px-3 h-10 text-sm focus:border-accent outline-none"
              />
            </div>
            <button
              onClick={() => promote(i)}
              aria-pressed={Boolean(t.recommended)}
              title="Mark as the recommended tier"
              className={`hairline rounded-lg px-3 h-10 text-xs inline-flex items-center gap-1.5 transition-colors ${
                t.recommended ? 'border-accent text-accent bg-accent/5' : 'text-text-muted hover:border-accent'
              }`}
            >
              <Star size={12} fill={t.recommended ? 'currentColor' : 'none'} />
              <span className="font-mono uppercase tracking-wider text-[10px]">Recommended</span>
            </button>
            <button
              onClick={() => onChange(tiers.filter((_, j) => j !== i))}
              className="hairline rounded-lg w-10 h-10 grid place-items-center hover:border-danger hover:text-danger"
              aria-label={`Remove tier ${t.name || i + 1}`}
            >
              <Trash2 size={13} />
            </button>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mb-1.5">What's included</div>
            <TagList items={t.features} mode="edit" onChange={(features) => patch(i, { features })} />
          </div>
        </div>
      ))}
    </div>
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
