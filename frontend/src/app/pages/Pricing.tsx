import { useState } from 'react';
import { Check, Crown, GraduationCap } from 'lucide-react';
import { PLAN_DETAILS, type SellerPlan, useStore } from '../lib/store';
import { useShallow } from 'zustand/react/shallow';

export function Pricing({ onAuth }: { onAuth: () => void }) {
  const { user, setUserPlan, toggleStudent } = useStore(
    useShallow((s) => ({ user: s.user, setUserPlan: s.setUserPlan, toggleStudent: s.toggleStudent })),
  );
  const [annual, setAnnual] = useState(false);
  const isStudent = !!user?.isStudent;
  const discount = isStudent ? 0.75 : 1;
  const billing = annual ? 0.83 : 1; // 17% off annual

  const order: SellerPlan[] = ['free', 'studio', 'atelier', 'maison'];

  return (
    <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 pt-16 pb-24">
      <div className="text-center max-w-2xl mx-auto">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted">For makers</div>
        <h1 className="font-serif mt-4">Sell software like it deserves to be sold.</h1>
        <p className="text-text-soft mt-5 leading-relaxed">
          Vitrine plans are designed for the long arc — from your first piece on the floor to a full studio with enterprise listings up to $50,000. Pick a tier, ship a piece, grow into the next one.
        </p>

        <div className="mt-8 inline-flex items-center gap-3 hairline rounded-full p-1">
          <button onClick={() => setAnnual(false)} className={`px-4 h-9 rounded-full text-sm transition-colors ${!annual ? 'bg-text text-bg' : 'text-text-muted'}`}>Monthly</button>
          <button onClick={() => setAnnual(true)} className={`px-4 h-9 rounded-full text-sm transition-colors ${annual ? 'bg-text text-bg' : 'text-text-muted'}`}>Annual <span className="text-accent ml-1">−17%</span></button>
        </div>

        <label className="mt-4 inline-flex items-center gap-2 text-sm hairline rounded-full px-4 h-9 cursor-pointer hover:border-accent transition-colors">
          <input type="checkbox" checked={isStudent} onChange={toggleStudent} className="accent-[var(--accent)]" />
          <GraduationCap size={13} className="text-accent" />
          I'm a student — apply 25% off
        </label>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5 mt-14 items-stretch">
        {order.map((p, i) => {
          const m = PLAN_DETAILS[p];
          const monthly = Math.round(m.price * discount * billing);
          const featured = i === 2;
          const current = user?.role === 'seller' && (user.plan ?? 'free') === p;
          return (
            <article
              key={p}
              className={`relative rounded-2xl p-6 flex flex-col bg-surface transition-transform hover:-translate-y-1 ${featured ? 'border-2 border-accent shadow-2xl' : 'hairline'}`}
            >
              {featured && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 font-mono text-[10px] uppercase tracking-[0.2em] bg-accent text-[var(--accent-ink)] rounded-full px-3 py-1 inline-flex items-center gap-1">
                  <Crown size={11} /> Most picked
                </div>
              )}
              <div className="font-serif text-2xl">{m.name}</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mt-1">{m.posts === 'unlimited' ? 'Unlimited listings' : `${m.posts} active listings`}</div>
              <div className="mt-5 flex items-baseline gap-1">
                <span className="font-serif text-5xl tabular">${monthly}</span>
                <span className="text-text-muted text-sm">/mo</span>
              </div>
              {discount < 1 && m.price > 0 && <div className="font-mono text-[10px] uppercase tracking-wider text-accent mt-1">student · save 25%</div>}
              {annual && m.price > 0 && <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-1">billed annually</div>}
              <ul className="mt-6 space-y-2 text-sm flex-1">
                {m.perks.map((perk) => (
                  <li key={perk} className="flex items-start gap-2">
                    <Check size={14} className="text-accent shrink-0 mt-0.5" /> <span>{perk}</span>
                  </li>
                ))}
              </ul>
              <button
                onClick={() => user ? setUserPlan(p) : onAuth()}
                className={`mt-6 rounded-xl h-11 font-medium inline-flex items-center justify-center transition-colors ${
                  featured ? 'bg-accent text-[var(--accent-ink)] hover:opacity-90' : current ? 'bg-text text-bg' : 'hairline hover:border-accent'
                }`}
              >
                {current ? 'Current plan' : p === 'free' ? 'Start free' : `Choose ${m.name}`}
              </button>
            </article>
          );
        })}
      </div>

      <section className="mt-24 grid lg:grid-cols-2 gap-10 items-start">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">House cut</div>
          <h2 className="font-serif mt-3">A commission that gets out of your way.</h2>
        </div>
        <div className="space-y-4">
          <Row k="Free tier" v="12% per sale" note="Only on the 2 free posts." />
          <Row k="Studio" v="8% per sale" />
          <Row k="Atelier" v="5% per sale" />
          <Row k="Maison" v="3% per sale" note="Lowest in the gallery." />
          <Row k="Enterprise listings ($10k+)" v="2% flat" note="Including bespoke builds and full-app sales." />
        </div>
      </section>

      <section className="mt-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-text-muted">Questions</div>
        <h2 className="font-serif mt-3 mb-10">For the careful</h2>
        <div className="grid md:grid-cols-2 gap-x-12 gap-y-6">
          {[
            ['Can I list a full app for $15,000+?', 'Yes — Atelier and Maison plans support enterprise listings up to $50k. White-glove enterprise sales drop to a flat 2% commission.'],
            ['What counts as student?', 'Anyone with a valid .edu (or equivalent) email. Verification is one click; the discount renews annually.'],
            ['Does Vitrine take a cut on free-tier listings?', 'Yes — 12% per sale on the two free slots. Once you subscribe, commission drops to 3–8%.'],
            ['Can buyers commission custom features?', 'Yes — the Request Features flow auto-quotes scope with our pricing agent, and you approve before any work starts.'],
            ['What if I want to cancel?', 'Cancel anytime. Your listings stay live until end of period; you keep your earnings.'],
            ['Do AI agents cost extra?', 'No — buyers and sellers use them at no cost. We absorb the inference bill as part of the platform.'],
          ].map(([q, a]) => (
            <div key={q}>
              <h3 className="font-serif text-lg">{q}</h3>
              <p className="text-sm text-text-soft mt-2 leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function Row({ k, v, note }: { k: string; v: string; note?: string }) {
  return (
    <div className="hairline rounded-xl bg-surface p-4 flex items-center justify-between gap-4">
      <div>
        <div className="font-serif text-base">{k}</div>
        {note && <div className="text-xs text-text-muted mt-0.5">{note}</div>}
      </div>
      <div className="font-mono tabular text-lg text-accent">{v}</div>
    </div>
  );
}
