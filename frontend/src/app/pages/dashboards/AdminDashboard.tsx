import { useState, useEffect } from 'react';
import { Shield, MessageSquare, Receipt, Users, Sparkles, Check, X, Eye, Pencil } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useStore } from '../../lib/store';
import { toast } from 'sonner';
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
  const { user, listings, transactions, threads, categories, frameworks } = useStore();
  if (!user) return null;
  const [tab, setTab] = useState<'overview' | 'queue' | 'transactions' | 'chats' | 'users' | 'agents' | 'console' | 'escrow' | 'reports'>('overview');

  const [queue, setQueue] = useState<any[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(false);

  const [usersList, setUsersList] = useState<any[]>([]);
  const [reportsList, setReportsList] = useState<any[]>([]);
  const [escrowList, setEscrowList] = useState<any[]>([]);
  const [adminAnalytics, setAdminAnalytics] = useState<any>(null);
  const [editingListing, setEditingListing] = useState<any>(null);

  const loadData = async () => {
    if (USE_MOCKS) return;
    try {
      if (tab === 'overview') {
        setAdminAnalytics(await api.adminAnalytics());
      } else if (tab === 'users') {
        setUsersList(await api.adminUsers());
      } else if (tab === 'reports') {
        setReportsList(await api.adminReports());
      } else if (tab === 'escrow') {
        setEscrowList(await api.adminEscrowOrders());
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, [tab]);

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

  const handleDeleteListing = async (id: string) => {
    if (confirm("Are you sure you want to delete this listing?")) {
      try {
        await api.adminDeleteListing(id);
        await loadQueue();
      } catch (e) {
        alert("Failed to delete");
      }
    }
  };

  const handleUserAction = async (id: string, action: 'ban' | 'unban' | 'delete' | 'reset') => {
    try {
      if (action === 'ban') {
        const duration = prompt("Enter ban duration (months) or 'infinite':", "1");
        if (duration) await api.adminBanUser(id, duration === 'infinite' ? 'infinite' : Number(duration));
      } else if (action === 'unban') {
        await api.adminBanUser(id, null);
      } else if (action === 'delete') {
        if (confirm("Permanently delete this user?")) await api.adminRemoveUser(id);
      } else if (action === 'reset') {
        const pwd = prompt("Enter new password for this user:");
        if (pwd) await api.adminResetUserPass(id, pwd);
      }
      loadData();
    } catch (e) {
      alert("Action failed");
    }
  };

  const handleEscrowAction = async (id: string, action: 'release' | 'refund') => {
    try {
      if (action === 'release') await api.adminEscrowRelease(id);
      if (action === 'refund') await api.adminEscrowRefund(id);
      loadData();
    } catch (e) {
      alert("Action failed");
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
          { id: 'escrow', label: 'Escrow' },
          { id: 'reports', label: 'Reports' },
          { id: 'agents', label: 'Agents' },
          { id: 'console', label: 'Curator console' },
        ]}
      />

      <div className="mt-10">
        {tab === 'overview' && (
          <>
            <div className="grid md:grid-cols-5 gap-4">
              <Stat k="GMV · all time" v={`$${grossVolume.toLocaleString()}`} icon={<Receipt size={14} />} />
              <Stat k="House take" v={`$${houseTake.toLocaleString()}`} icon={<Sparkles size={14} />} />
              <Stat k="Open chats" v={String(threads.length)} icon={<MessageSquare size={14} />} />
              <Stat k="Verified makers" v={String(new Set(listings.map((l) => l.ownerId)).size)} icon={<Users size={14} />} />
              <Stat k="Site views · 14d" v={adminAnalytics ? adminAnalytics.views_14d.toLocaleString() : "14,328"} icon={<Eye size={14} />} />
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
            {queue.map((l) => {
              const isExpired = l.expiresAt ? new Date(l.expiresAt) < new Date() : false;
              return (
                <article key={l.id} className="hairline rounded-2xl bg-surface p-5 flex items-center gap-5">
                  <img src={l.cover} alt="" className="w-16 h-16 rounded-lg object-cover" />
                  <div className="flex-1 min-w-0">
                    <div className="font-serif text-lg">{l.name}</div>
                    <div className="text-xs text-text-muted">
                      by {l.seller?.name} · {l.category} · ${l.price.toLocaleString()}
                      {l.expiresAt && ` · Expires: ${new Date(l.expiresAt).toLocaleDateString()}`}
                    </div>
                    <div className="mt-2 flex gap-2 flex-wrap">
                      <Pill kind={isExpired ? 'bad' : l.status === 'live' ? 'good' : l.status === 'review' || l.status === 'flagged' || l.status === 'enriching' || l.status === 'draft' ? 'wait' : 'good'}>
                        {isExpired ? 'expired' : l.status}
                      </Pill>
                      <Pill kind="good">{l.framework}</Pill>
                      <Pill kind="good">demo healthy</Pill>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => setEditingListing(l)} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-accent" aria-label="Edit"><Pencil size={13} /></button>
                    <button onClick={() => handleDecision(l.id, 'approve')} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-success hover:text-success" aria-label="Approve"><Check size={14} /></button>
                    <button onClick={() => handleDecision(l.id, 'reject')} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-danger hover:text-danger" aria-label="Reject"><X size={14} /></button>
                    <button onClick={() => handleDeleteListing(l.id)} className="hairline rounded-lg w-9 h-9 grid place-items-center hover:border-danger hover:text-danger" aria-label="Delete"><X size={14} /></button>
                  </div>
                </article>
              );
            })}
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
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <tr><th className="text-left p-4">Name</th><th className="text-left p-4">Email</th><th className="text-left p-4">Role</th><th className="p-4 text-left">Status</th><th className="p-4 text-right pr-6">Actions</th></tr>
              </thead>
              <tbody>
                {usersList.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-text-muted">Loading users...</td></tr>}
                {usersList.map((u) => (
                  <tr key={u.id} className="border-t">
                    <td className="p-4 font-serif">{u.name || 'Unnamed'}</td>
                    <td className="p-4 text-xs text-text-muted">{u.email}</td>
                    <td className="p-4"><Pill kind={u.role === 'admin' ? 'good' : u.role === 'buyer' ? 'wait' : 'good'}>{u.role}</Pill></td>
                    <td className="p-4">
                      {u.banned_until ? <span className="text-danger text-xs">Banned</span> : <span className="text-success text-xs">Active</span>}
                    </td>
                    <td className="p-4 pr-6 text-right flex justify-end gap-2">
                      <button onClick={() => handleUserAction(u.id, u.banned_until ? 'unban' : 'ban')} className="text-xs hover:text-accent">{u.banned_until ? 'Unban' : 'Ban'}</button>
                      <button onClick={() => handleUserAction(u.id, 'reset')} className="text-xs hover:text-accent">Reset Pass</button>
                      {u.id !== user.id && <button onClick={() => handleUserAction(u.id, 'delete')} className="text-xs text-danger hover:underline">Remove</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
           </div>
          </div>
        )}

        {tab === 'reports' && (
          <div className="space-y-3">
            {reportsList.length === 0 && <div className="text-sm text-text-muted">No reports found.</div>}
            {reportsList.map((r) => (
              <article key={r.id} className="hairline rounded-2xl bg-surface p-5">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-serif">Report against {r.target_type}: {r.target_id}</div>
                    <div className="text-xs text-text-muted mt-1">Status: {r.status} · Date: {new Date(r.created_at).toLocaleDateString()}</div>
                  </div>
                  <Pill kind={r.status === 'open' ? 'bad' : 'good'}>{r.status}</Pill>
                </div>
                <div className="mt-4 p-3 bg-bg rounded-xl text-sm whitespace-pre-wrap">{r.reason}</div>
              </article>
            ))}
          </div>
        )}

        {tab === 'escrow' && (
          <div className="hairline rounded-2xl bg-surface overflow-hidden">
           <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <tr><th className="text-left p-4">Order ID</th><th className="text-left p-4">Listing</th><th className="text-left p-4">Amount</th><th className="text-left p-4">Escrow Status</th><th className="p-4 text-right pr-6">Actions</th></tr>
              </thead>
              <tbody>
                {escrowList.length === 0 && <tr><td colSpan={5} className="p-4 text-center text-text-muted">No escrow funds found.</td></tr>}
                {escrowList.map((o) => (
                  <tr key={o.id} className="border-t">
                    <td className="p-4 font-mono text-xs">{o.id}</td>
                    <td className="p-4 text-xs">{o.listing_id}</td>
                    <td className="p-4 text-xs font-mono">${o.amount.toLocaleString()}</td>
                    <td className="p-4"><Pill kind={o.escrow_status === 'holding' ? 'wait' : o.escrow_status === 'released' ? 'good' : 'bad'}>{o.escrow_status}</Pill></td>
                    <td className="p-4 pr-6 text-right flex justify-end gap-2">
                      {o.escrow_status === 'holding' && (
                        <>
                          <button onClick={() => handleEscrowAction(o.id, 'release')} className="text-xs text-success hover:underline">Release Funds</button>
                          <button onClick={() => handleEscrowAction(o.id, 'refund')} className="text-xs text-danger hover:underline">Refund Buyer</button>
                        </>
                      )}
                    </td>
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
      {editingListing && (
        <EditListingModal
          listing={editingListing}
          categories={categories}
          frameworks={frameworks}
          onClose={() => setEditingListing(null)}
          onSave={async (patch) => {
            try {
              if (USE_MOCKS) {
                const updated = {
                  ...editingListing,
                  ...patch,
                };
                setQueue((q) => q.map((x) => x.id === editingListing.id ? updated : x));
                setEditingListing(null);
                toast.success('Listing updated successfully!');
              } else {
                await api.adminEditListing(editingListing.id, patch);
                setEditingListing(null);
                await loadQueue();
                toast.success('Listing updated successfully!');
              }
            } catch (e) {
              toast.error(e instanceof Error ? e.message : 'Failed to update listing');
            }
          }}
        />
      )}
    </main>
  );
}

interface EditListingModalProps {
  listing: any;
  categories: string[];
  frameworks: string[];
  onClose: () => void;
  onSave: (patch: any) => Promise<void>;
}

function EditListingModal({ listing, categories, frameworks, onClose, onSave }: EditListingModalProps) {
  const [name, setName] = useState(listing.name || '');
  const [tagline, setTagline] = useState(listing.tagline || '');
  const [category, setCategory] = useState(listing.category || '');
  const [framework, setFramework] = useState(listing.framework || '');
  const [price, setPrice] = useState(listing.price || 0);
  const [status, setStatus] = useState(listing.status || 'draft');
  const [description, setDescription] = useState(listing.description || '');
  const [demoUrl, setDemoUrl] = useState(listing.demoUrl || listing.demo_url || '');
  
  const getInitialDate = () => {
    if (listing.expiresAt) {
      return new Date(listing.expiresAt).toISOString().split('T')[0];
    }
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split('T')[0];
  };
  
  const [expiryDate, setExpiryDate] = useState(getInitialDate());
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return alert("Name is required");
    if (!expiryDate) return alert("Expiry date is required");
    
    setSaving(true);
    try {
      const parsedExpiresAt = new Date(expiryDate).toISOString();
      await onSave({
        name,
        tagline,
        category,
        framework,
        price,
        status,
        description,
        demo_url: demoUrl,
        expires_at: parsedExpiresAt
      });
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm overflow-y-auto flex items-center justify-center p-4">
      <div className="bg-bg border border-border-c rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl text-text animate-in fade-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center pb-2 border-b border-border-c">
          <h3 className="font-serif text-2xl">Edit Listing · {listing.name}</h3>
          <button onClick={onClose} className="hairline rounded-lg w-8 h-8 grid place-items-center hover:border-accent"><X size={14} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Name</div>
              <input value={name} onChange={(e) => setName(e.target.value)} required className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none font-mono text-sm focus:border-accent" />
            </label>
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Status</div>
              <select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none text-sm focus:border-accent">
                <option value="draft">Draft</option>
                <option value="in-review">In Review</option>
                <option value="live">Live</option>
                <option value="rejected">Rejected</option>
              </select>
            </label>
          </div>
          <label className="block">
            <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Tagline</div>
            <input value={tagline} onChange={(e) => setTagline(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none text-sm focus:border-accent" />
          </label>
          <div className="grid sm:grid-cols-3 gap-4">
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Category</div>
              <select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none text-sm focus:border-accent">
                {categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Framework</div>
              <select value={framework} onChange={(e) => setFramework(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none text-sm focus:border-accent">
                {frameworks.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Price ($)</div>
              <input type="number" min={0} value={price} onChange={(e) => setPrice(Number(e.target.value) || 0)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none font-mono text-sm focus:border-accent" />
            </label>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Live Demo URL</div>
              <input value={demoUrl} onChange={(e) => setDemoUrl(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none font-mono text-sm focus:border-accent" />
            </label>
            <label className="block">
              <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Expiry Date</div>
              <input type="date" required value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} className="w-full hairline rounded-xl bg-bg px-3 h-10 outline-none font-mono text-sm focus:border-accent" />
            </label>
          </div>
          <label className="block">
            <div className="text-xs text-text-muted mb-1 font-mono uppercase tracking-wider">Description</div>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} className="w-full hairline rounded-xl bg-bg p-3 outline-none text-sm focus:border-accent resize-y" />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="hairline rounded-xl px-4 h-10 text-sm hover:border-accent">Cancel</button>
            <button type="submit" disabled={saving} className="bg-text text-bg rounded-xl px-4 h-10 text-sm font-medium disabled:opacity-50">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
