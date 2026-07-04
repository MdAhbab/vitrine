import { Bot, KeyRound, MessageSquare, ShoppingBag, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { useStore, activeRepsForBuyer, type Listing, type Transaction } from '../../lib/store';
import { Inbox } from '../../components/Inbox';
import { OrderDetail } from '../../components/OrderDetail';
import { PreviewFrame } from '../../components/PreviewFrame';

export function BuyerDashboard() {
  const { user, transactions, threads, deactivateRep, listings } = useStore(
    useShallow((s) => ({
      user: s.user, transactions: s.transactions, threads: s.threads,
      deactivateRep: s.deactivateRep, listings: s.listings,
    })),
  );
  const [tab, setTab] = useState<'overview' | 'library' | 'orders' | 'reps' | 'messages'>('overview');
  const [openOrder, setOpenOrder] = useState<Transaction | null>(null);
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);
  // Guard AFTER all hooks — an early return above them violates the Rules of
  // Hooks and crashes if `user` flips mid-commit.
  if (!user) return null;

  const mine = transactions.filter((t) => t.buyerId === user.id);
  const reps = activeRepsForBuyer(user.id, threads);
  const myOrders = mine;
  const libraryProducts = myOrders
    .map((o) => listings.find((l) => l.id === o.productId))
    .filter((p): p is Listing => Boolean(p))
    .filter((p, i, arr) => arr.findIndex((q) => q.id === p.id) === i);

  const goToProduct = (slug: string) => { window.location.hash = `/p/${slug}`; };

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-12 pb-24">
      <Header name={user.name} subtitle="Welcome back to your library" />
      <Tabs
        tab={tab}
        onChange={setTab}
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'library', label: 'Library' },
          { id: 'orders', label: 'Orders' },
          { id: 'reps', label: `AI reps · ${reps.length}/2` },
          { id: 'messages', label: 'Messages' },
        ]}
      />

      <div className="mt-10">
        {tab === 'overview' && (
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat k="Pieces owned" v={String(mine.length)} icon={<ShoppingBag size={14} />} />
            <Stat k="Active AI reps" v={`${reps.length} / 2`} icon={<Bot size={14} />} />
            <Stat k="Open threads" v={String(threads.filter((t) => t.buyerId === user.id).length)} icon={<MessageSquare size={14} />} />
            <Stat k="Spent · all time" v={`$${mine.reduce((s, t) => s + t.amount, 0).toLocaleString()}`} icon={<KeyRound size={14} />} />
          </div>
        )}

        {tab === 'library' && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {libraryProducts.map((p) => {
              const order = myOrders.find((o) => o.productId === p.id);
              return (
                <article key={p.id} className="group hairline rounded-2xl bg-surface overflow-hidden hover:border-accent/60 transition-colors cursor-pointer" onClick={() => order && setOpenOrder(order)}>
                  <div className="relative">
                    <img src={p.cover} alt="" className="aspect-[16/10] object-cover w-full group-hover:scale-[1.02] transition-transform duration-500" />
                    <div className="absolute top-3 left-3 font-mono text-[10px] uppercase tracking-wider text-white/90 bg-black/40 backdrop-blur rounded-full px-2 py-1 inline-flex items-center gap-1"><KeyRound size={10} /> owned</div>
                  </div>
                  <div className="p-5">
                    <div className="font-serif text-lg">{p.name}</div>
                    <div className="text-xs text-text-muted mt-1">{p.license} · {order?.tier ?? 'Source'} · delivered</div>
                    <div className="mt-4 flex gap-2">
                      <button onClick={(e) => { e.stopPropagation(); setPreview({ url: p.demoUrl, name: p.name }); }} className="flex-1 hairline rounded-lg h-11 text-sm inline-flex items-center justify-center gap-1.5 hover:border-accent transition-colors"><ChevronRight size={13} /> Open demo</button>
                    </div>
                  </div>
                </article>
              );
            })}
            {libraryProducts.length === 0 && (
              <div className="hairline rounded-2xl p-10 text-center col-span-full">
                <ShoppingBag size={20} className="text-accent mx-auto" />
                <div className="font-serif text-xl mt-3">No pieces yet</div>
                <p className="text-sm text-text-muted mt-2">Browse the gallery and your purchases will live here.</p>
              </div>
            )}
          </div>
        )}

        {tab === 'orders' && (
          <div className="hairline rounded-2xl bg-surface overflow-hidden">
           <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
                <tr><th className="text-left p-4">Piece</th><th className="text-left p-4">Tier</th><th className="text-left p-4">Status</th><th className="text-right p-4">Amount</th><th className="text-right p-4 pr-6">Date</th></tr>
              </thead>
              <tbody>
                {myOrders.map((t) => (
                  <tr key={t.id} className="border-t hover:bg-surface-2/40 cursor-pointer transition-colors" onClick={() => setOpenOrder(t)}>
                    <td className="p-4 font-serif">{t.productName}</td>
                    <td className="p-4 font-mono text-xs text-text-muted">{t.tier}</td>
                    <td className="p-4"><Pill kind={t.status === 'paid' ? 'good' : 'wait'}>{t.status}</Pill></td>
                    <td className="p-4 text-right font-mono tabular">${t.amount.toLocaleString()}</td>
                    <td className="p-4 pr-6 text-right text-xs text-text-muted inline-flex items-center gap-1 justify-end">{new Date(t.ts).toLocaleDateString()} <ChevronRight size={11} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
           </div>
          </div>
        )}

        {tab === 'reps' && (
          <div className="space-y-4">
            <p className="text-sm text-text-soft max-w-2xl">Your AI reps negotiate with sellers on your behalf — under your budget, in your tone. You can have <span className="text-accent">two active reps</span> at any time.</p>
            <div className="grid md:grid-cols-2 gap-4">
              {reps.map((r) => (
                <div key={r.id} className="hairline rounded-2xl bg-surface p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <img src={r.productCover} alt="" className="w-12 h-12 rounded-lg object-cover" />
                      <div>
                        <div className="font-serif text-base">{r.productName}</div>
                        <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">with {r.sellerName}</div>
                      </div>
                    </div>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-accent inline-flex items-center gap-1"><Bot size={11} /> active</span>
                  </div>
                  <div className="mt-4 flex justify-between items-center text-sm">
                    <div>
                      <span className="text-text-muted">Authorized budget</span>
                      <span className="font-mono tabular ml-1.5">${r.agentBudget}</span>
                    </div>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (confirm(`Are you sure you want to deactivate the AI representative for ${r.productName}?`)) {
                          await deactivateRep(r.id);
                        }
                      }}
                      className="hairline rounded-lg px-3 py-1.5 text-xs text-text-soft hover:border-danger hover:text-danger hover:bg-danger/5 transition-all cursor-pointer"
                    >
                      Deactivate rep
                    </button>
                  </div>
                </div>
              ))}
              {reps.length === 0 && (
                <div className="hairline rounded-2xl p-10 text-center col-span-full">
                  <Bot size={20} className="text-accent mx-auto" />
                  <div className="font-serif text-xl mt-3">No active reps</div>
                  <p className="text-sm text-text-muted mt-2">Click "AI Bargain" on any product to dispatch one.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'messages' && <Inbox role="buyer" viewer={{ id: user.id, name: user.name }} />}
      </div>

      {openOrder && (
        <OrderDetail
          order={openOrder}
          onClose={() => setOpenOrder(null)}
          onOpenProduct={(slug) => { setOpenOrder(null); goToProduct(slug); }}
          onPreview={(url, name) => setPreview({ url, name })}
        />
      )}
      <PreviewFrame
        open={!!preview}
        url={preview?.url ?? ''}
        productName={preview?.name ?? ''}
        onClose={() => setPreview(null)}
      />
    </main>
  );
}

function Header({ name, subtitle }: { name: string; subtitle: string }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Account</div>
      <h1 className="font-serif mt-3">Hello, {name.split(' ')[0]}.</h1>
      <p className="text-text-soft mt-2">{subtitle}</p>
    </div>
  );
}

export function Tabs<T extends string>({ tab, onChange, items }: { tab: T; onChange: (t: T) => void; items: { id: T; label: string }[] }) {
  return (
    <div className="mt-8 hairline rounded-full p-1 inline-flex flex-wrap">
      {items.map((it) => (
        <button key={it.id} onClick={() => onChange(it.id)}
          className={`px-4 h-9 rounded-full font-mono text-[11px] uppercase tracking-wider transition-colors ${tab === it.id ? 'bg-text text-bg' : 'text-text-muted hover:text-text'}`}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function Stat({ k, v, icon }: { k: string; v: string; icon: React.ReactNode }) {
  return (
    <div className="hairline rounded-2xl bg-surface p-5">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{k}</div>
        <span className="text-accent">{icon}</span>
      </div>
      <div className="font-serif text-3xl mt-3 tabular">{v}</div>
    </div>
  );
}

export function Pill({ children, kind = 'good' }: { children: React.ReactNode; kind?: 'good' | 'wait' | 'bad' }) {
  const c = kind === 'good' ? 'text-success border-success/40' : kind === 'wait' ? 'text-accent border-accent/40' : 'text-danger border-danger/40';
  return <span className={`font-mono text-[10px] uppercase tracking-wider px-2 py-1 rounded-full hairline ${c}`}>{children}</span>;
}
