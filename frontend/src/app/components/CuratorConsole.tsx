import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Key, Sparkles, Shield, ToggleLeft, ToggleRight, Plus, Trash2, Eye, EyeOff, Sliders, Mail, Save, Bot, Receipt, ScrollText, Settings2 } from 'lucide-react';
import { useStore, type AdminApiKey } from '../lib/store';
import { toast } from 'sonner';
import { useShallow } from 'zustand/react/shallow';

export function CuratorConsole() {
  const { adminConfig, updateAdminConfig, addApiKey, toggleApiKey, removeApiKey, listings, categories, frameworks, forms } = useStore(
    useShallow((s) => ({
      adminConfig: s.adminConfig, updateAdminConfig: s.updateAdminConfig,
      addApiKey: s.addApiKey, toggleApiKey: s.toggleApiKey, removeApiKey: s.removeApiKey,
      listings: s.listings, categories: s.categories, frameworks: s.frameworks, forms: s.forms,
    })),
  );
  const [section, setSection] = useState<'instructions' | 'keys' | 'flags' | 'fees' | 'escrow' | 'branding' | 'categories' | 'frameworks' | 'forms' | 'notes'>('instructions');
  const [saved, setSaved] = useState(false);

  const [newCategory, setNewCategory] = useState('');
  const [newFramework, setNewFramework] = useState('');
  const [formSchemaText, setFormSchemaText] = useState('');

  useEffect(() => {
    setFormSchemaText(JSON.stringify(forms, null, 2));
  }, [forms]);

  const sections = [
    { id: 'instructions' as const, label: 'AI instructions', icon: <Bot size={13} /> },
    { id: 'keys' as const, label: `API keys · ${adminConfig.apiKeys.length}`, icon: <Key size={13} /> },
    { id: 'flags' as const, label: 'Feature flags', icon: <ToggleRight size={13} /> },
    { id: 'fees' as const, label: 'Fees & commissions', icon: <Receipt size={13} /> },
    { id: 'escrow' as const, label: 'Escrow', icon: <Shield size={13} /> },
    { id: 'branding' as const, label: 'Branding', icon: <Sparkles size={13} /> },
    { id: 'categories' as const, label: 'Categories', icon: <Sliders size={13} /> },
    { id: 'frameworks' as const, label: 'Frameworks', icon: <Sliders size={13} /> },
    { id: 'forms' as const, label: 'Intake Forms', icon: <ScrollText size={13} /> },
    { id: 'notes' as const, label: 'Curator notes', icon: <ScrollText size={13} /> },
  ];

  const flash = () => { setSaved(true); setTimeout(() => setSaved(false), 1400); };

  return (
    <div className="grid lg:grid-cols-[260px_1fr] gap-6">
      {/* Sidebar */}
      <aside className="hairline rounded-2xl bg-surface p-2 h-fit lg:sticky lg:top-24">
        <div className="px-3 pt-3 pb-2 flex items-center gap-2 text-accent">
          <Settings2 size={13} />
          <span className="font-mono text-[10px] uppercase tracking-[0.18em]">Curator console</span>
        </div>
        <nav className="flex lg:flex-col gap-1 overflow-x-auto lg:overflow-visible scroll-rail p-1">
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={`shrink-0 lg:shrink text-left px-3 h-10 rounded-lg text-sm inline-flex items-center gap-2 transition-colors whitespace-nowrap ${section === s.id ? 'bg-surface-2 text-text' : 'text-text-soft md:hover:bg-surface-2/60 active:bg-surface-2/60'}`}
            >
              {s.icon} {s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Body */}
      <div className="space-y-6 min-w-0">
        {saved && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="hairline border-accent/40 bg-accent/5 rounded-xl px-4 py-2 text-sm inline-flex items-center gap-2">
            <Save size={13} className="text-accent" /> Saved.
          </motion.div>
        )}

        {section === 'instructions' && (
          <Card title="AI agent instructions" hint="System prompts injected into every agent run. Edit to taste — changes apply to new threads, not in-flight ones.">
            {(['concierge', 'buyerRep', 'pricingAgent', 'verification'] as const).map((k) => (
              <Field key={k} label={agentLabel(k)} icon={agentIcon(k)}>
                <textarea
                  value={adminConfig.systemPrompts[k]}
                  onChange={(e) => updateAdminConfig({ systemPrompts: { ...adminConfig.systemPrompts, [k]: e.target.value } })}
                  onBlur={flash}
                  rows={5}
                  className="w-full hairline rounded-xl bg-bg p-3 text-sm font-mono leading-relaxed outline-none focus:border-accent resize-y"
                />
                <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-muted">{adminConfig.systemPrompts[k].length} chars</div>
              </Field>
            ))}
          </Card>
        )}

        {section === 'keys' && (
          <Card title="API keys" hint="Keys are masked. Add additional providers — they appear in the agent's provider rotation.">
            <KeyAdder onAdd={(k) => { addApiKey(k); flash(); }} />
            <div className="space-y-2">
              {adminConfig.apiKeys.map((k) => (
                <KeyRow key={k.id} k={k} onToggle={() => { toggleApiKey(k.id); flash(); }} onRemove={() => { if (confirm(`Remove ${k.label}?`)) { removeApiKey(k.id); flash(); } }} />
              ))}
              {adminConfig.apiKeys.length === 0 && (
                <div className="hairline rounded-xl p-6 text-center text-sm text-text-muted">No API keys configured. Add one above.</div>
              )}
            </div>
          </Card>
        )}

        {section === 'flags' && (
          <Card title="Feature flags" hint="Toggle platform-wide capabilities. Changes apply on next page load.">
            <div className="space-y-2">
              {(Object.keys(adminConfig.flags) as Array<keyof typeof adminConfig.flags>).map((flag) => (
                <FlagRow
                  key={flag}
                  label={flagLabel(flag)}
                  on={adminConfig.flags[flag]}
                  onToggle={() => { updateAdminConfig({ flags: { ...adminConfig.flags, [flag]: !adminConfig.flags[flag] } }); flash(); }}
                />
              ))}
            </div>
          </Card>
        )}

        {section === 'fees' && (
          <Card title="Fees & commissions" hint="Percentages charged by Vitrine on transactions. Enterprise applies to listings ≥ $15,000.">
            <div className="grid sm:grid-cols-2 gap-4">
              {(Object.keys(adminConfig.fees) as Array<keyof typeof adminConfig.fees>).map((k) => (
                <Field key={k} label={feeLabel(k)}>
                  <div className="hairline rounded-xl bg-bg flex items-center pl-3 pr-2 h-11">
                    <input
                      type="number"
                      step={0.1}
                      value={adminConfig.fees[k]}
                      onChange={(e) => updateAdminConfig({ fees: { ...adminConfig.fees, [k]: Number(e.target.value) || 0 } })}
                      onBlur={flash}
                      className="flex-1 bg-transparent outline-none font-mono tabular text-sm"
                    />
                    <span className="font-mono text-xs text-text-muted">%</span>
                  </div>
                </Field>
              ))}
            </div>
          </Card>
        )}

        {section === 'escrow' && (
          <Card title="Escrow policy" hint="How Vitrine holds payments before releasing to sellers.">
            <div className="grid sm:grid-cols-2 gap-4">
              <Field label="Hold period (hours)">
                <NumInput v={adminConfig.escrow.holdHours} onChange={(v) => { updateAdminConfig({ escrow: { ...adminConfig.escrow, holdHours: v } }); flash(); }} />
              </Field>
              <Field label="Refund window (days)">
                <NumInput v={adminConfig.escrow.refundWindow} onChange={(v) => { updateAdminConfig({ escrow: { ...adminConfig.escrow, refundWindow: v } }); flash(); }} />
              </Field>
            </div>
            <FlagRow label="Auto-release on delivery" on={adminConfig.escrow.autoRelease} onToggle={() => { updateAdminConfig({ escrow: { ...adminConfig.escrow, autoRelease: !adminConfig.escrow.autoRelease } }); flash(); }} />
          </Card>
        )}

        {section === 'branding' && (
          <Card title="Public branding" hint="What buyers see on the home page and in support emails.">
            <Field label="Headline">
              <input value={adminConfig.branding.headline} onChange={(e) => updateAdminConfig({ branding: { ...adminConfig.branding, headline: e.target.value } })} onBlur={flash}
                className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent" />
            </Field>
            <Field label="Tagline">
              <input value={adminConfig.branding.tagline} onChange={(e) => updateAdminConfig({ branding: { ...adminConfig.branding, tagline: e.target.value } })} onBlur={flash}
                className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent" />
            </Field>
            <Field label="Support email" icon={<Mail size={12} />}>
              <input value={adminConfig.branding.supportEmail} onChange={(e) => updateAdminConfig({ branding: { ...adminConfig.branding, supportEmail: e.target.value } })} onBlur={flash}
                className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm font-mono outline-none focus:border-accent" />
            </Field>
            <Field label="Featured pieces (Hero Showcase)">
              <div className="mt-2 space-y-2 max-h-60 overflow-y-auto pr-2 scroll-rail">
                {listings.filter((l) => l.status === 'live').map((l) => {
                  const isFeatured = (adminConfig.featuredIds || []).includes(l.id);
                  return (
                    <label key={l.id} className="flex items-center gap-3 p-2.5 rounded-xl bg-bg/50 hairline hover:border-accent/40 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={isFeatured}
                        onChange={() => {
                          const current = adminConfig.featuredIds || [];
                          const next = isFeatured
                            ? current.filter((id) => id !== l.id)
                            : [...current, l.id];
                          updateAdminConfig({ featuredIds: next });
                          flash();
                        }}
                        className="rounded border-border-c text-accent focus:ring-accent"
                      />
                      <img src={l.cover} alt="" className="w-8 h-8 rounded object-cover" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{l.name}</div>
                        <div className="text-xs text-text-muted truncate">{l.category} · ${l.price.toLocaleString()}</div>
                      </div>
                    </label>
                  );
                })}
                {listings.filter((l) => l.status === 'live').length === 0 && (
                  <div className="text-xs text-text-muted py-4 text-center">No live pieces available to feature.</div>
                )}
              </div>
            </Field>
          </Card>
        )}

        {section === 'categories' && (
          <Card title="Categories" hint="Manage software categories shown on Browse and Home pages.">
            <div className="flex gap-2">
              <input
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                placeholder="New category name (e.g. Security)"
                className="flex-1 hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent"
              />
              <button
                onClick={async () => {
                  if (!newCategory.trim()) return;
                  if (categories.includes(newCategory.trim())) {
                    toast.error('Category already exists');
                    return;
                  }
                  await updateAdminConfig({ categories: [...categories, newCategory.trim()] });
                  setNewCategory('');
                  flash();
                }}
                disabled={!newCategory.trim()}
                className="bg-text text-bg rounded-xl px-4 h-11 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40"
              >
                <Plus size={13} /> Add
              </button>
            </div>
            <div className="space-y-2 mt-4 max-h-[400px] overflow-y-auto pr-2 scroll-rail">
              {categories.map((c) => (
                <div key={c} className="hairline rounded-xl p-3 flex items-center justify-between bg-surface">
                  <span className="text-sm font-medium">{c}</span>
                  <button
                    onClick={async () => {
                      if (confirm(`Are you sure you want to delete the category "${c}"?`)) {
                        await updateAdminConfig({ categories: categories.filter((x) => x !== c) });
                        flash();
                      }
                    }}
                    className="hairline rounded-lg w-8 h-8 grid place-items-center md:hover:border-danger md:hover:text-danger active:border-danger active:text-danger"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {categories.length === 0 && (
                <div className="text-xs text-text-muted py-4 text-center">No categories configured.</div>
              )}
            </div>
          </Card>
        )}

        {section === 'frameworks' && (
          <Card title="Frameworks" hint="Manage framework filters shown on Browse and Sell pages.">
            <div className="flex gap-2">
              <input
                value={newFramework}
                onChange={(e) => setNewFramework(e.target.value)}
                placeholder="New framework name (e.g. SvelteKit)"
                className="flex-1 hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent"
              />
              <button
                onClick={async () => {
                  if (!newFramework.trim()) return;
                  if (frameworks.includes(newFramework.trim())) {
                    toast.error('Framework already exists');
                    return;
                  }
                  await updateAdminConfig({ frameworks: [...frameworks, newFramework.trim()] });
                  setNewFramework('');
                  flash();
                }}
                disabled={!newFramework.trim()}
                className="bg-text text-bg rounded-xl px-4 h-11 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40"
              >
                <Plus size={13} /> Add
              </button>
            </div>
            <div className="space-y-2 mt-4 max-h-[400px] overflow-y-auto pr-2 scroll-rail">
              {frameworks.map((f) => (
                <div key={f} className="hairline rounded-xl p-3 flex items-center justify-between bg-surface">
                  <span className="text-sm font-medium">{f}</span>
                  <button
                    onClick={async () => {
                      if (confirm(`Are you sure you want to delete the framework "${f}"?`)) {
                        await updateAdminConfig({ frameworks: frameworks.filter((x) => x !== f) });
                        flash();
                      }
                    }}
                    className="hairline rounded-lg w-8 h-8 grid place-items-center md:hover:border-danger md:hover:text-danger active:border-danger active:text-danger"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
              {frameworks.length === 0 && (
                <div className="text-xs text-text-muted py-4 text-center">No frameworks configured.</div>
              )}
            </div>
          </Card>
        )}

        {section === 'forms' && (
          <Card title="Intake Forms Schema" hint="Edit the YAML/JSON schema structure for intake form fields and sections.">
            <textarea
              value={formSchemaText}
              onChange={(e) => setFormSchemaText(e.target.value)}
              rows={15}
              placeholder="Paste FORM_SCHEMA JSON here..."
              className="w-full hairline rounded-xl bg-bg p-4 text-sm font-mono leading-relaxed outline-none focus:border-accent resize-y"
            />
            <button
              onClick={async () => {
                try {
                  const parsed = JSON.parse(formSchemaText);
                  if (!Array.isArray(parsed)) {
                    toast.error('Schema must be an array of sections');
                    return;
                  }
                  await updateAdminConfig({ forms: parsed });
                  toast.success('Form schema updated successfully');
                  flash();
                } catch (e) {
                  toast.error(`Invalid JSON: ${e instanceof Error ? e.message : String(e)}`);
                }
              }}
              className="bg-text text-bg rounded-xl px-4 h-11 text-sm font-medium inline-flex items-center gap-2"
            >
              <Save size={13} /> Save Form Schema
            </button>
          </Card>
        )}

        {section === 'notes' && (
          <Card title="Internal curator notes" hint="A scratchpad for the back-of-house team. Not visible to buyers or sellers.">
            <textarea
              value={adminConfig.notes}
              onChange={(e) => updateAdminConfig({ notes: e.target.value })}
              onBlur={flash}
              rows={10}
              placeholder="e.g. New verification policy as of 2026-06-09: enterprise listings require demo video + provenance doc."
              className="w-full hairline rounded-xl bg-bg p-4 text-sm leading-relaxed outline-none focus:border-accent resize-y"
            />
          </Card>
        )}
      </div>
    </div>
  );
}

function Card({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="hairline rounded-2xl bg-surface p-5 sm:p-6 space-y-5">
      <header>
        <h2 className="font-serif text-2xl">{title}</h2>
        {hint && <p className="text-sm text-text-muted mt-1.5">{hint}</p>}
      </header>
      {children}
    </section>
  );
}

function Field({ label, icon, children }: { label: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-2 inline-flex items-center gap-1.5">
        {icon}{label}
      </div>
      {children}
    </label>
  );
}

function FlagRow({ label, on, onToggle }: { label: string; on: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle} className="w-full hairline rounded-xl p-4 flex items-center justify-between md:hover:border-accent/60 active:border-accent/60 transition-colors">
      <span className="text-sm">{label}</span>
      <span className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider ${on ? 'text-accent' : 'text-text-muted'}`}>
        {on ? <ToggleRight size={20} /> : <ToggleLeft size={20} />} {on ? 'on' : 'off'}
      </span>
    </button>
  );
}

function NumInput({ v, onChange }: { v: number; onChange: (v: number) => void }) {
  return (
    <input type="number" value={v} onChange={(e) => onChange(Number(e.target.value) || 0)}
      className="w-full hairline rounded-xl bg-bg px-3 h-11 text-sm font-mono tabular outline-none focus:border-accent" />
  );
}

function KeyAdder({ onAdd }: { onAdd: (k: Omit<AdminApiKey, 'id' | 'createdAt'>) => void }) {
  const [provider, setProvider] = useState<AdminApiKey['provider']>('openai');
  const [label, setLabel] = useState('');
  const [key, setKey] = useState('');

  const submit = () => {
    if (!label.trim() || !key.trim()) return;
    onAdd({ provider, label: label.trim(), key: maskKey(key.trim()), enabled: true });
    setLabel(''); setKey('');
  };

  return (
    <div className="hairline rounded-xl p-4 bg-surface-2/40 space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted inline-flex items-center gap-1.5">
        <Plus size={11} /> Add key
      </div>
      <div className="grid sm:grid-cols-[160px_1fr] gap-2">
        <select value={provider} onChange={(e) => setProvider(e.target.value as AdminApiKey['provider'])}
          className="hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent">
          <option value="openai">OpenAI (ChatGPT)</option>
          <option value="anthropic">Anthropic</option>
          <option value="gemini">Google Gemini</option>
          <option value="grok">xAI Grok</option>
          <option value="nvidia">Nvidia Nemotron</option>
          <option value="stripe">Stripe</option>
          <option value="custom">Custom (OpenAI-compat)</option>
        </select>
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label (e.g. Concierge — backup)"
          className="hairline rounded-xl bg-bg px-3 h-11 text-sm outline-none focus:border-accent" />
      </div>
      <div className="flex gap-2">
        <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Paste key — stored masked"
          className="flex-1 hairline rounded-xl bg-bg px-3 h-11 text-sm font-mono outline-none focus:border-accent" />
        <button onClick={submit} disabled={!label.trim() || !key.trim()} className="bg-text text-bg rounded-xl px-4 h-11 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40">
          <Plus size={13} /> Add
        </button>
      </div>
    </div>
  );
}

function KeyRow({ k, onToggle, onRemove }: { k: AdminApiKey; onToggle: () => void; onRemove: () => void }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <article className="hairline rounded-xl p-4 flex items-center gap-3 sm:gap-4 bg-surface">
      <span className="w-9 h-9 grid place-items-center rounded-full hairline shrink-0">
        <Key size={13} className="text-accent" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-serif text-base truncate">{k.label}</span>
          <span className="font-mono text-[10px] uppercase tracking-wider hairline rounded-full px-2 py-0.5 text-text-muted">{k.provider}</span>
          {!k.enabled && <span className="font-mono text-[10px] uppercase tracking-wider text-danger">disabled</span>}
        </div>
        <div className="font-mono text-xs text-text-muted truncate mt-1">{revealed ? k.key : maskKey(k.key)}</div>
      </div>
      <button onClick={() => setRevealed((s) => !s)} className="hairline rounded-lg w-11 h-11 grid place-items-center md:hover:border-accent active:border-accent shrink-0" aria-label="Reveal">
        {revealed ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
      <button onClick={onToggle} className="hairline rounded-lg w-11 h-11 grid place-items-center md:hover:border-accent active:border-accent shrink-0" aria-label="Toggle">
        {k.enabled ? <ToggleRight size={15} className="text-accent" /> : <ToggleLeft size={15} className="text-text-muted" />}
      </button>
      <button onClick={onRemove} className="hairline rounded-lg w-11 h-11 grid place-items-center md:hover:border-danger md:hover:text-danger active:border-danger active:text-danger shrink-0" aria-label="Remove">
        <Trash2 size={13} />
      </button>
    </article>
  );
}

function maskKey(k: string) {
  if (k.length <= 8) return k;
  const head = k.slice(0, 6);
  const tail = k.slice(-4);
  return `${head}${'•'.repeat(Math.max(8, k.length - 10))}${tail}`;
}

function agentLabel(k: 'concierge' | 'buyerRep' | 'pricingAgent' | 'verification') {
  return ({ concierge: 'Concierge — search & curation', buyerRep: 'Buyer Rep — negotiation', pricingAgent: 'Pricing & Pitch — listing assist', verification: 'Verification — listing review' })[k];
}
function agentIcon(k: 'concierge' | 'buyerRep' | 'pricingAgent' | 'verification') {
  return ({ concierge: <Sparkles size={11} />, buyerRep: <Bot size={11} />, pricingAgent: <Sliders size={11} />, verification: <Shield size={11} /> })[k];
}
function flagLabel(k: string) {
  return ({
    aiBargain: 'AI Bargain (buyer reps)',
    conciergeSearch: 'Concierge AI search',
    enterpriseTier: 'Enterprise listings ($15k+)',
    studentDiscount: 'Student 25% discount',
    newSignupsOpen: 'New signups open',
  } as Record<string, string>)[k] ?? k;
}
function feeLabel(k: string) {
  return ({
    commissionFree: 'Free-plan commission',
    commissionStudio: 'Studio-plan commission',
    commissionAtelier: 'Atelier-plan commission',
    commissionMaison: 'Maison-plan commission',
    enterprise: 'Enterprise commission',
    processing: 'Processing fee',
  } as Record<string, string>)[k] ?? k;
}
