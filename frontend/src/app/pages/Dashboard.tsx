import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { PRODUCTS } from '../lib/mockData';

const series = Array.from({ length: 14 }, (_, i) => ({
  d: `${i + 1}`,
  views: 80 + Math.round(Math.sin(i / 2) * 30 + i * 12 + Math.random() * 10),
  launches: 20 + Math.round(Math.cos(i / 3) * 8 + i * 3),
}));

export function Dashboard() {
  const mine = PRODUCTS.slice(0, 4);
  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-12 pb-24">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Seller</div>
      <h1 className="font-serif mt-3">Studio dashboard</h1>

      <div className="grid sm:grid-cols-4 gap-4 mt-10">
        {[
          { k: 'Views · 14d', v: '14,328', d: '+12%' },
          { k: 'Launches', v: '1,204', d: '+18%' },
          { k: 'Conversion', v: '3.4%', d: '+0.6pt' },
          { k: 'Payouts', v: '$8,140', d: 'pending $1,200' },
        ].map((s) => (
          <div key={s.k} className="hairline rounded-2xl p-5 bg-surface">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{s.k}</div>
            <div className="font-serif text-3xl mt-2 tabular">{s.v}</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-accent mt-1">{s.d}</div>
          </div>
        ))}
      </div>

      <section className="hairline rounded-2xl bg-surface p-6 mt-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Activity</div>
            <h2 className="font-serif text-2xl mt-1">Views vs. launches</h2>
          </div>
        </div>
        <div className="h-72 mt-6 -mx-2">
          <ResponsiveContainer>
            <AreaChart data={series} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="d" stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={10} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border-c)', borderRadius: 12, fontSize: 12 }}
              />
              <Area type="monotone" dataKey="views" stroke="var(--accent)" strokeWidth={2} fill="url(#g1)" />
              <Area type="monotone" dataKey="launches" stroke="var(--text)" strokeWidth={1.5} fill="none" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="font-serif text-2xl mb-5">Your listings</h2>
        <div className="hairline rounded-2xl bg-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2/60 font-mono text-[10px] uppercase tracking-wider text-text-muted">
              <tr>
                <th className="text-left p-4">Piece</th>
                <th className="text-left p-4">Status</th>
                <th className="text-right p-4">Score</th>
                <th className="text-right p-4">Views</th>
                <th className="text-right p-4">Sales</th>
                <th className="text-right p-4 pr-6">Payout</th>
              </tr>
            </thead>
            <tbody>
              {mine.map((p, i) => (
                <tr key={p.id} className="border-t hover:bg-surface-2/40 transition-colors">
                  <td className="p-4 flex items-center gap-3">
                    <img src={p.cover} alt="" className="w-12 h-12 rounded-lg object-cover" />
                    <div>
                      <div className="font-serif text-base">{p.name}</div>
                      <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{p.category}</div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`font-mono text-[10px] uppercase tracking-wider px-2 py-1 rounded-full hairline ${i === 0 ? 'text-accent border-accent/40' : 'text-text-muted'}`}>
                      {i === 0 ? 'Featured' : i === 1 ? 'In review' : 'Live'}
                    </span>
                  </td>
                  <td className="p-4 text-right font-mono tabular">{p.vitrineScore}</td>
                  <td className="p-4 text-right font-mono tabular">{(1248 - i * 200).toLocaleString()}</td>
                  <td className="p-4 text-right font-mono tabular">{42 - i * 5}</td>
                  <td className="p-4 pr-6 text-right font-mono tabular">${(p.price * (42 - i * 5)).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
