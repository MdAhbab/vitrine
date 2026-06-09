import { useState, useEffect } from 'react';
import { Shield, MessageSquare, Receipt, Users, Sparkles, Check, X, Eye } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useStore } from '../../lib/store';
import { Inbox } from '../../components/Inbox';
import { CuratorConsole } from '../../components/CuratorConsole';
import { Tabs, Stat, Pill } from './BuyerDashboard';
import { api, USE_MOCKS } from '../../lib/api';

const series = Array.from({ length: 14 }, (_, i) => ({
  d: `${i + 1}`,
  txns: 8 + Math.round(Math.sin(i / 2.3) * 4 + i * 1.2 + Math.random() * 3),
  agent: 1.4 + Math.sin(i / 1.8) * 0.6 + i * 0.08,
}));

export function AdminDashboard() {
  const { user, listings, transactions, threads } = useStore();
  if (!user) return null;
  const [tab, setTab] = useState<'overview' | 'queue' | 'transactions' | 'chats' | 'users' | 'agents' | 'console'>('overview');

  const [queue, setQueue] = useState<any[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(false);

  const loadQueue = async () => {
    if (USE_MOCKS) {
      setQueue(listings.slice(0, 4).map((l, i) => ({
        id: l.id,
        name: l.name,
        cover: l.cover,
        category: l.category,
        price: l.price,
        framework: l.framework,
        status: i === 0 ? 'review' : 'live',
        seller: { name: l.seller.name }
      })));
      return;
    }
    setLoadingQueue(true);
    try {
      const q = await api.adminVerificationQueue();
      setQueue(q);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingQueue(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [listings]);

  const handleDecision = async (id: string, verdict: 'approve' | 'reject') => {
    if (USE_MOCKS) {
      setQueue((prev) => prev.filter((item) => item.id !== id));
      return;
    }
    try {
      await api.adminDecision(id, verdict);
      await loadQueue();
    } catch (e) {
      console.error(e);
      alert("Failed to submit verdict");
    }
  };

  const grossVolume = transactions.reduce((s, t) => s + t.amount, 0);
  const houseTake = transactions.reduce((s, t) => s + t.commission, 0);

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-12 pb-24">
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-full grid place-items-center bg-text text-bg"><Shield size={14} /></span>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Curator</div>
          <h1 className="font-serif mt-1">Back of house</h1>
        </div>
      </div>

      <Tabs
        tab={tab} onChange={setTab}
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'queue', label: 'Verification queue' },
          { id: 'transactions', label: `Transactions · ${transactions.length}` },
          { id: 'chats', label: `Chats · ${threads.length}` },
          { id: 'users', label: 'Users' },
          { id: 'agents', label: 'Agents' },
          { id: 'console', label: 'Curator console' },
        ]}
      />

      <div className="mt-10">
        {tab === 'overview' && (
          <>
            <div className="grid md:grid-cols-4 gap-4">
              <Stat k="GMV · all time" v={`$${grossVolume.toLocaleString()}`} icon={<Receipt size={14} />} />
              <Stat k="House take" v={`$${houseTake.toLocaleString()}`} icon={<Sparkles size={14} />} />
              <Stat k="Open chats" v={String(threads.length)} icon={<MessageSquare size={14} />} />
              <Stat k="Verified makers" v={String(new Set(listings.map((l) => l.ownerId)).size)} icon={<Users size={14} />} />
            </div>
            <section className="hairline rounded-2xl bg-surface p-6 mt-6">
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Trend · 14 days</div>
              <h2 className="font-serif text-xl mt-1">Transactions vs. agent cost ($k)</h2>
              <div className="h-64 mt-5 -mx-2">
                <ResponsiveContainer>
                  <AreaChart data={series} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="d" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border-c)', borderRadius: 12, fontSize: 12 }} />
                    <Area type="monotone" dataKey="txns" stroke="var(--accent)" strokeWidth={2} fill="url(#ag)" />
                    <Area type="monotone" dataKey="agent" stroke="var(--text)" strokeWidth={1.5} fill="none" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
          </>
        )}

        {tab === 'queue' && (
          <div className="space-y-3">
            {loadingQueue && <div className="text-sm text-text-muted">Loading queue...</div>}
            {!loadingQueue && queue.length === 0 && <div className="text-sm text-text-muted">No pending listings in the queue.</div>}
            {queue.map((l) => (
              <article key={l.id} className="hairline rounded-2xl bg-surface p-5 flex items-center gap-5">
                <img src={l.cover} alt="" className="w-16 h-16 rounded-lg object-cover" />
                <div className="flex-1 min-w-0">
                  <div className="font-serif text-lg">{l.name}</div>
                  <div className="text-xs text-text-muted">by {l.seller?.name} · {l.category} · ${l.price.toLocaleString()}</div>
                  <div className="mt-2 flex gap-2 flex-wrap">
                    <Pill kind={l.status === 'review' || l.status === 'flagged' || l.status === 'enriching' ? 'wait' : 'good'}>{l.status}</Pill>
                    <Pill kind="good">{l.framework}</Pill>
                    <Pill kind="good">demo healthy</Pill>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleDecision(l.id, 'approve')} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-success hover:text-success" aria-label="Approve"><Check size={14} /></button>
                  <button onClick={() => handleDecision(l.id, 'reject')} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-danger hover:text-danger" aria-label="Reject"><X size={14} /></button>
                  <button className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-accent" aria-label="View"><Eye size={14} /></button>
                </div>
              </article>
            ))}
          </div>
        )}

        {tab === 'transactions' && (
          <div className="hairline rounded-2xl bg-surface overflow-hidden">
           <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <tr><th className="text-left p-4">When</th><th className="text-left p-4">Piece</th><th className="text-left p-4">Buyer</th><th className="text-left p-4">Seller</th><th className="p-4">Status</th><th className="p-4 text-right">Gross</th><th className="p-4 text-right pr-6">House</th></tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id} className="border-t">
                    <td className="p-4 text-xs text-text-muted">{new Date(t.ts).toLocaleDateString()}</td>
                    <td className="p-4 font-serif">{t.productName}</td>
                    <td className="p-4 text-xs">{t.buyerName}</td>
                    <td className="p-4 text-xs">{t.sellerName}</td>
                    <td className="p-4"><Pill kind={t.status === 'paid' ? 'good' : t.status === 'refunded' ? 'bad' : 'wait'}>{t.status}</Pill></td>
                    <td className="p-4 text-right font-mono tabular">${t.amount.toLocaleString()}</td>
                    <td className="p-4 pr-6 text-right font-mono tabular text-accent">${t.commission.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
           </div>
          </div>
        )}

        {tab === 'chats' && <Inbox role="admin" viewer={{ id: user.id, name: user.name }} />}

        {tab === 'users' && (
          <div className="hairline rounded-2xl bg-surface overflow-hidden">
           <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <tr><th className="text-left p-4">Name</th><th className="text-left p-4">Role</th><th className="text-left p-4">Plan</th><th className="p-4 text-right">Joined</th><th className="p-4 text-right pr-6">Activity</th></tr>
              </thead>
              <tbody>
                {[
                  { n: 'June Park', r: 'buyer', p: '—', d: '3 weeks ago', a: '4 orders' },
                  { n: 'Atelier Foxglove', r: 'seller', p: 'Atelier', d: '6 months ago', a: '12 listings' },
                  { n: 'Studio Korr', r: 'seller', p: 'Studio', d: '4 months ago', a: '6 listings' },
                  { n: 'Marco Rivers', r: 'buyer', p: '—', d: 'last week', a: '1 order' },
                  { n: 'North&Type', r: 'seller', p: 'Maison', d: '1 year ago', a: '34 listings' },
                ].map((u) => (
                  <tr key={u.n} className="border-t">
                    <td className="p-4 font-serif">{u.n}</td>
                    <td className="p-4"><Pill kind={u.r === 'buyer' ? 'good' : 'wait'}>{u.r}</Pill></td>
                    <td className="p-4 text-xs font-mono">{u.p}</td>
                    <td className="p-4 text-right text-xs text-text-muted">{u.d}</td>
                    <td className="p-4 pr-6 text-right text-xs">{u.a}</td>
                  </tr>
                ))}
              </tbody>
            </table>
           </div>
          </div>
        )}

        {tab === 'agents' && (
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { n: 'Concierge', d: 'Search & curation', runs: 1849, cost: 412 },
              { n: 'Buyer Rep', d: 'Negotiation', runs: 612, cost: 287 },
              { n: 'Pricing & Pitch', d: 'Listing assist', runs: 248, cost: 96 },
              { n: 'Spec Extractor', d: 'Repo intake', runs: 187, cost: 134 },
              { n: 'Health Monitor', d: 'Demo uptime', runs: 9244, cost: 24 },
              { n: 'Verification', d: 'Listing review', runs: 92, cost: 71 },
            ].map((a) => (
              <div key={a.n} className="hairline rounded-2xl bg-surface p-5">
                <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Agent</div>
                <div className="font-serif text-xl mt-2">{a.n}</div>
                <div className="text-xs text-text-muted">{a.d}</div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Runs · 30d</div>
                    <div className="font-mono tabular text-lg">{a.runs}</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Cost</div>
                    <div className="font-mono tabular text-lg">${a.cost}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === 'console' && <CuratorConsole />}
      </div>
    </main>
  );
}
