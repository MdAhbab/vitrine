import { useState, useEffect } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Crown, GraduationCap, Plus, TrendingUp, Wallet, Bot, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { api, USE_MOCKS } from '../../lib/api';
import { useStore, PLAN_DETAILS, normalizeListing, type SellerPlan, type Listing } from '../../lib/store';
import { Inbox } from '../../components/Inbox';
import { ListingEditor } from '../../components/ListingEditor';
import { Tabs, Stat, Pill } from './BuyerDashboard';

const mockSeries = Array.from({ length: 14 }, (_, i) => ({
  d: `${i + 1}`,
  views: 80 + Math.round(Math.sin(i / 2) * 30 + i * 12 + Math.random() * 10),
  launches: 20 + Math.round(Math.cos(i / 3) * 8 + i * 3),
}));


export function SellerDashboard({ goToPricing, goToSell }: { goToPricing: () => void; goToSell: () => void }) {
  const { user, listings, transactions, threads, setUserPlan, toggleStudent, upsertListing, loadData } = useStore(
    useShallow((s) => ({
      user: s.user, listings: s.listings, transactions: s.transactions, threads: s.threads,
      setUserPlan: s.setUserPlan, toggleStudent: s.toggleStudent,
      upsertListing: s.upsertListing, loadData: s.loadData,
    })),
  );
  const [payoutBusy, setPayoutBusy] = useState(false);
  const [analytics, setAnalytics] = useState<any>(null);
  const [tab, setTab] = useState<'overview' | 'listings' | 'inbox' | 'payouts' | 'plan'>('overview');
  const [editor, setEditor] = useState<{ listing: Listing; mode: 'view' | 'edit' } | null>(null);
  const [repostingId, setRepostingId] = useState<string | null>(null);

  useEffect(() => {
    if (USE_MOCKS) return;
    api.sellerAnalytics()
      .then(setAnalytics)
      .catch(console.error);
  }, []);

  // Guard AFTER all hooks (Rules of Hooks — the early return previously sat
  // between hook calls and could crash on a mid-commit user flip).
  if (!user) return null;

  const handleRepost = async (id: string) => {
    setRepostingId(id);
    try {
      if (USE_MOCKS) {
        const listing = listings.find((x) => x.id === id);
        if (listing) {
          const nextExpires = new Date();
          nextExpires.setDate(nextExpires.getDate() + 30);
          const updated: Listing = {
            ...listing,
            status: 'live',
            expiresAt: nextExpires.toISOString(),
          };
          await upsertListing(updated);
        }
        toast.success('Listing reposted and optimized with AI!');
      } else {
        await api.repostListing(id);
        await loadData();
        toast.success('Listing reposted and optimized with AI!');
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to repost listing');
    } finally {
      setRepostingId(null);
    }
  };

  const aiDraftNew = async () => {
    if (USE_MOCKS) {
      const draftId = `p_draft_${Math.random().toString(36).slice(2, 8)}`;
      const cover = listings[0]?.cover ?? '';
      const seed: Listing = {
        id: draftId,
        slug: `new-listing-${draftId}`,
        name: 'Untitled piece',
        tagline: '',
        seller: { name: user.name, handle: `@${user.name.toLowerCase().replace(/\s+/g, '')}`, verified: false },
        category: 'Dashboards', tags: [], price: 49,
        tiers: [
          { name: 'Source', price: 49, features: ['Full source code', 'MIT license', 'Email support'] },
          { name: 'Source + Setup', price: 129, features: ['Onboarding call', '30 days of fixes'], recommended: true },
          { name: 'Bespoke', price: 329, features: ['Brand reskin', '90 days of support'] },
        ],
        vitrineScore: 70,
        scoreBreakdown: [
          { label: 'Completeness', value: 60 }, { label: 'UI craft', value: 60 }, { label: 'Demo health', value: 80 },
          { label: 'Reviews', value: 0 }, { label: 'Recency', value: 100 }, { label: 'Engagement', value: 40 },
        ],
        demoUrl: 'https://vercel.com', demoHealth: 'live', badges: ['new'],
        screenshots: [cover], cover, ratingDistribution: [0,0,0,0,0], rating: 0, reviewsCount: 0,
        description: '', spec: [], framework: 'React', license: 'MIT', hasLiveDemo: false,
        createdAt: new Date().toISOString(),
        sdlc: { problem: '', solution: '', methodology: '', discussions: '' },
        businessModel: { kind: 'for-profit', pitch: '', revenueStreams: [] },
        techStack: [], aiDraft: true,
        ownerId: user.id, status: 'draft',
      };
      upsertListing(seed);
      setEditor({ listing: seed, mode: 'edit' });
      return;
    }
    try {
      const created = await api.createListing({ name: 'Untitled piece', category: 'Dashboards', tagline: '', price: 49 });
      await api.updateListing(created.id, { ai_draft: true });
      await loadData();
      const fresh = useStore.getState().listings.find((l) => l.id === created.id) ?? normalizeListing(created);
      setEditor({ listing: { ...fresh, aiDraft: true }, mode: 'edit' });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not create draft');
    }
  };

  const plan: SellerPlan = user.plan ?? 'free';
  const planMeta = PLAN_DETAILS[plan];
  const mine = listings.filter((l) => l.ownerId === user.id);
  const myThreads = threads.filter((t) => t.sellerId === user.id || t.sellerName === user.name);
  const repThreads = myThreads.filter((t) => t.isAgent);
  const myTxns = transactions.filter((t) => t.sellerName === user.name || t.sellerId === user.id);
  const grossEarnings = myTxns.reduce((s, t) => s + (t.amount - t.commission), 0);
  // Never invent money: real mode falls back to the order-derived figure (0
  // for a new seller) while analytics load; the demo dressing is mock-only.
  const displayEarnings = analytics ? analytics.earnings_all_time : grossEarnings;

  const viewsVal = analytics ? analytics.views_14d.toLocaleString() : (USE_MOCKS ? '14,328' : '—');
  const launchesVal = analytics ? analytics.launches_14d.toLocaleString() : (USE_MOCKS ? '1,204' : '—');
  const conversionVal = analytics ? `${analytics.conversion_rate}%` : (USE_MOCKS ? '3.4%' : '—');
  const chartData = analytics ? analytics.history : (USE_MOCKS ? mockSeries : []);
  
  const paidAwaitingDelivery = myTxns.filter((t) => t.status === 'paid' && !(t as { delivered?: boolean }).delivered);
  const discount = user.isStudent ? 0.75 : 1;

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-12 pb-24">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Studio</div>
          <h1 className="font-serif mt-3">Studio · {user.name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider hairline border-accent/40 text-accent rounded-full px-2 py-1 inline-flex items-center gap-1">
              <Crown size={11} /> {planMeta.name} plan
            </span>
            {user.isStudent && <span className="font-mono text-[10px] uppercase tracking-wider hairline rounded-full px-2 py-1 inline-flex items-center gap-1"><GraduationCap size={11} /> student · 25% off</span>}
            <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{planMeta.commission}% commission · {planMeta.posts === 'unlimited' ? '∞' : planMeta.posts} posts</span>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={aiDraftNew} className="group bg-text text-bg rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2 hover:opacity-90">
            <Bot size={13} className="text-accent" /> AI-draft a listing
          </button>
          <button onClick={goToSell} className="hairline rounded-xl px-4 h-10 text-sm hover:border-accent transition-colors inline-flex items-center gap-2"><Plus size={13} /> Manual</button>
          <button onClick={goToPricing} className="hairline rounded-xl px-4 h-10 text-sm hover:border-accent transition-colors">Manage plan</button>
        </div>
      </div>

      <Tabs
        tab={tab} onChange={setTab}
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'listings', label: `Listings · ${mine.length}` },
          { id: 'inbox', label: `Inbox · ${myThreads.length}` },
          { id: 'payouts', label: 'Payouts' },
          { id: 'plan', label: 'Plan & limits' },
        ]}
      />

      <div className="mt-10">
        {tab === 'overview' && (
          <>
            <div className="grid md:grid-cols-4 gap-4">
              <Stat k="Views · 14d" v={viewsVal} icon={<TrendingUp size={14} />} />
              <Stat k="Launches" v={launchesVal} icon={<Sparkles size={14} />} />
              <Stat k="Conversion" v={conversionVal} icon={<TrendingUp size={14} />} />
              <Stat k="Earnings · all time" v={`$${displayEarnings.toLocaleString()}`} icon={<Wallet size={14} />} />
            </div>
            <section className="hairline rounded-2xl bg-surface p-6 mt-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Activity · 14 days</div>
              <h2 className="font-serif text-xl mt-1">Views vs. launches</h2>
              <div className="h-64 mt-5 -mx-2">
                <ResponsiveContainer>
                  <AreaChart data={chartData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="sg1" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="d" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border-c)', borderRadius: 12, fontSize: 12 }} />
                    <Area type="monotone" dataKey="views" stroke="var(--accent)" strokeWidth={2} fill="url(#sg1)" />
                    <Area type="monotone" dataKey="launches" stroke="var(--text)" strokeWidth={1.5} fill="none" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            {repThreads.length > 0 && (
              <section className="hairline rounded-2xl bg-surface p-6 mt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Active negotiations</div>
                    <h2 className="font-serif text-xl mt-1">Buyer reps in your inbox</h2>
                  </div>
                  <button onClick={() => setTab('inbox')} className="text-sm border-b border-text">Open inbox →</button>
                </div>
                <div className="grid md:grid-cols-2 gap-3 mt-5">
                  {repThreads.map((t) => (
                    <div key={t.id} className="hairline rounded-xl p-4 bg-surface-2/40 flex items-center gap-3">
                      <img src={t.productCover} alt="" className="w-10 h-10 rounded-lg object-cover" />
                      <div className="flex-1 min-w-0">
                        <div className="font-serif text-sm truncate">{t.productName}</div>
                        <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{t.buyerName} · budget ${t.agentBudget}</div>
                      </div>
                      <Bot size={14} className="text-accent" />
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {tab === 'listings' && (
          <div className="space-y-3">
            {mine.map((l, i) => {
              const isExpired = l.expiresAt ? new Date(l.expiresAt) < new Date() : false;
              return (
                <article key={l.id} className="group hairline rounded-2xl bg-surface p-4 flex items-center gap-4 hover:border-accent/60 transition-colors">
                  <img src={l.cover} alt="" className="w-16 h-16 rounded-lg object-cover" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="font-serif text-lg">{l.name}</div>
                      {l.aiDraft && <span className="font-mono text-[10px] uppercase tracking-wider text-accent inline-flex items-center gap-1"><Bot size={10} /> draft</span>}
                    </div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-1">
                      {l.category} · {l.framework} · ${l.price.toLocaleString()}
                      {l.expiresAt && ` · Expires: ${new Date(l.expiresAt).toLocaleDateString()}`}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 items-center">
                      <Pill kind={isExpired ? 'bad' : l.status === 'live' ? 'good' : l.status === 'in-review' ? 'wait' : l.status === 'rejected' ? 'bad' : 'wait'}>
                        {isExpired ? 'expired' : l.status}
                      </Pill>
                      <span className="text-xs text-text-muted">Score · <span className="font-mono tabular text-text">{l.vitrineScore}</span></span>
                      <span className="text-xs text-text-muted">Sales · <span className="font-mono tabular text-text">{Math.max(0, 42 - i * 5)}</span></span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {isExpired && (
                      <button
                        onClick={() => handleRepost(l.id)}
                        disabled={repostingId === l.id}
                        className="bg-accent text-[var(--accent-ink)] rounded-lg px-3 h-9 text-sm font-medium hover:opacity-90 inline-flex items-center gap-1.5 transition-opacity disabled:opacity-50"
                      >
                        <Bot size={13} /> {repostingId === l.id ? 'Reposting...' : 'Repost with AI'}
                      </button>
                    )}
                    <button onClick={() => setEditor({ listing: l, mode: 'view' })} className="hairline rounded-lg px-3 h-9 text-sm hover:border-accent">View</button>
                    <button onClick={() => setEditor({ listing: l, mode: 'edit' })} className="hairline rounded-lg px-3 h-9 text-sm hover:border-accent">Edit</button>
                  </div>
                </article>
              );
            })}
            {mine.length === 0 && (
              <div className="hairline rounded-2xl p-10 text-center">
                <Bot size={20} className="text-accent mx-auto" />
                <div className="font-serif text-xl mt-3">No listings yet</div>
                <p className="text-sm text-text-muted mt-2">Let our AI draft your first one — you'll edit it before it goes live.</p>
                <button onClick={aiDraftNew} className="mt-5 bg-text text-bg rounded-xl px-4 h-10 text-sm inline-flex items-center gap-2"><Bot size={13} className="text-accent" /> AI-draft a listing</button>
              </div>
            )}
          </div>
        )}

        {tab === 'inbox' && <Inbox role="seller" viewer={{ id: user.id, name: user.name }} />}

        {tab === 'payouts' && (
          <div className="grid lg:grid-cols-[1fr_360px] gap-6">
            <div className="hairline rounded-2xl bg-surface overflow-hidden">
             <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[640px]">
                <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  <tr><th className="text-left p-4">Order</th><th className="p-4">Buyer</th><th className="p-4">Status</th><th className="p-4">Escrow</th><th className="p-4 text-right">Gross</th><th className="p-4 text-right">Commission</th><th className="p-4 text-right pr-6">Net</th></tr>
                </thead>
                <tbody>
                  {myTxns.map((t) => (
                    <tr key={t.id} className="border-t">
                      <td className="p-4 font-serif">{t.productName}</td>
                      <td className="p-4 text-xs text-text-muted">{t.buyerName}</td>
                      <td className="p-4">
                        {t.status === 'paid' && !(t as { delivered?: boolean }).delivered ? (
                          <button
                            onClick={async () => {
                              try {
                                await api.deliverOrder(t.id, {});
                                toast.success('Order marked delivered');
                                await loadData();
                              } catch (e) {
                                toast.error(e instanceof Error ? e.message : 'Delivery failed');
                              }
                            }}
                            className="hairline rounded-lg px-2 py-1 text-[10px] uppercase tracking-wider hover:border-accent"
                          >
                            Mark delivered
                          </button>
                        ) : (
                          <Pill kind={t.status === 'paid' || (t as { delivered?: boolean }).delivered ? 'good' : 'wait'}>{(t as { delivered?: boolean }).delivered ? 'delivered' : t.status}</Pill>
                        )}
                      </td>
                      <td className="p-4">
                        {t.escrow_status ? <Pill kind={t.escrow_status === 'released' ? 'good' : t.escrow_status === 'holding' ? 'wait' : 'bad'}>{t.escrow_status}</Pill> : <span className="text-text-muted text-xs">—</span>}
                      </td>
                      <td className="p-4 text-right font-mono tabular">${t.amount.toLocaleString()}</td>
                      <td className="p-4 text-right font-mono tabular text-danger">−${t.commission.toLocaleString()}</td>
                      <td className="p-4 pr-6 text-right font-mono tabular">${(t.amount - t.commission).toLocaleString()}</td>
                    </tr>
                  ))}
                  {myTxns.length === 0 && (
                    <tr><td colSpan={6} className="p-8 text-center text-sm text-text-muted">No orders yet.</td></tr>
                  )}
                </tbody>
              </table>
             </div>
            </div>
            <aside className="hairline rounded-2xl bg-surface p-6 h-fit">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Balance</div>
              <div className="font-serif text-4xl tabular mt-2">${displayEarnings.toLocaleString()}</div>
              {paidAwaitingDelivery.length > 0 && (
                <p className="text-xs text-accent mt-2">{paidAwaitingDelivery.length} order(s) awaiting delivery before payout.</p>
              )}
              <button
                disabled={payoutBusy || displayEarnings <= 0}
                onClick={async () => {
                  setPayoutBusy(true);
                  try {
                    await api.requestPayout({ amount: displayEarnings, payout_method: 'bank', details: {} });
                    toast.success('Payout requested');
                    await loadData();
                  } catch (e) {
                    toast.error(e instanceof Error ? e.message : 'Payout request failed');
                  } finally {
                    setPayoutBusy(false);
                  }
                }}
                className="w-full bg-accent text-[var(--accent-ink)] rounded-xl h-11 font-medium mt-5 disabled:opacity-40"
              >
                {payoutBusy ? 'Requesting…' : 'Request payout'}
              </button>
              <p className="text-xs text-text-muted mt-3">Payouts are reviewed and settle to your bank on file.</p>
            </aside>
          </div>
        )}

        {tab === 'plan' && (
          <div className="grid lg:grid-cols-[1fr_360px] gap-6">
            <div className="space-y-4">
              {(['free', 'studio', 'atelier', 'maison'] as SellerPlan[]).map((p) => {
                const m = PLAN_DETAILS[p];
                const final = Math.round(m.price * discount);
                const current = plan === p;
                return (
                  <button key={p} onClick={() => setUserPlan(p)} className={`w-full text-left hairline rounded-2xl bg-surface p-5 transition-colors ${current ? 'border-accent' : 'hover:border-accent/60'}`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-serif text-xl">{m.name}</div>
                        <div className="text-xs text-text-muted">{m.posts === 'unlimited' ? 'Unlimited listings' : `${m.posts} active listings`} · {m.commission}% commission</div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-2xl tabular">${final}<span className="text-text-muted text-sm">/mo</span></div>
                        {discount < 1 && m.price > 0 && <div className="text-[10px] text-accent font-mono uppercase tracking-wider">student price</div>}
                      </div>
                    </div>
                    <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-text-muted">
                      {m.perks.map((perk) => <li key={perk}>· {perk}</li>)}
                    </ul>
                    {current && <div className="font-mono text-[10px] uppercase tracking-wider text-accent mt-3">Current plan</div>}
                  </button>
                );
              })}
            </div>
            <aside className="hairline rounded-2xl bg-surface p-6 h-fit space-y-4">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Eligibility</div>
                <label className="mt-3 flex items-center gap-2 cursor-pointer text-sm">
                  <input type="checkbox" checked={!!user.isStudent} onChange={toggleStudent} className="accent-[var(--accent)]" />
                  <GraduationCap size={14} className="text-accent" /> I'm a student
                </label>
                <p className="text-xs text-text-muted mt-2">25% off any paid plan, billed monthly. Re-verified annually with your .edu email.</p>
              </div>
              <div className="border-t pt-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">House cut</div>
                <p className="text-xs mt-2 text-text-soft">Free tier sellers pay <span className="text-text">12% commission</span>. Subscribed sellers pay 3–8% depending on plan.</p>
              </div>
            </aside>
          </div>
        )}
      </div>

      {editor && (
        <ListingEditor listing={editor.listing} mode={editor.mode} onClose={() => setEditor(null)} />
      )}
    </main>
  );
}
