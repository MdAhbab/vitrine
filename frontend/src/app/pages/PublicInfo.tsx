import { motion } from 'motion/react';
import { ArrowRight, Bot, CheckCircle2, Newspaper, Sparkles, Store, Wrench } from 'lucide-react';

type InfoKind = 'whats-new' | 'services' | 'about';

const PAGE: Record<InfoKind, {
  eyebrow: string;
  title: string;
  summary: string;
  items: { icon: 'news' | 'sparkles' | 'store' | 'tools' | 'bot' | 'check'; title: string; text: string }[];
}> = {
  'whats-new': {
    eyebrow: 'Release Notes',
    title: "What's new",
    summary: 'Recent improvements across the gallery, seller tooling, and AI-assisted discovery.',
    items: [
      { icon: 'sparkles', title: 'Live Concierge search', text: 'Natural-language search now reads the live catalog, applies hard constraints like budget and demo availability, and returns grounded matches.' },
      { icon: 'store', title: 'Expanded catalog', text: 'The gallery includes more product categories, richer seller profiles, and database-backed live listings for browsing and dashboards.' },
      { icon: 'check', title: 'Production deploy path', text: 'Native VM deployment now includes domain-aware robots, sitemap, ads.txt, TLS proxying, and non-conflicting internal ports.' },
    ],
  },
  services: {
    eyebrow: 'Services',
    title: 'Services',
    summary: 'Vitrine helps buyers inspect software and helps verified sellers present, price, and deliver it.',
    items: [
      { icon: 'store', title: 'Live software gallery', text: 'Browse production-ready apps with live previews, technical specs, pricing tiers, reviews, and Vitrine Score context.' },
      { icon: 'bot', title: 'AI buying support', text: 'Use Concierge to discover matching products and buyer representatives to negotiate within your stated budget.' },
      { icon: 'tools', title: 'Seller operations', text: 'Sellers get listing intake, pricing assistance, verification workflow, dashboards, order handling, and payout views.' },
    ],
  },
  about: {
    eyebrow: 'About Us',
    title: 'About Vitrine',
    summary: 'Page currently developing beautifully.',
    items: [
      { icon: 'sparkles', title: 'In development', text: 'Page currently developing beautifully.' },
    ],
  },
};

const ICONS = {
  news: Newspaper,
  sparkles: Sparkles,
  store: Store,
  tools: Wrench,
  bot: Bot,
  check: CheckCircle2,
};

export function PublicInfo({ kind, onBrowse }: { kind: InfoKind; onBrowse: () => void }) {
  const page = PAGE[kind];
  return (
    <main className="max-w-[1120px] mx-auto px-6 lg:px-10 pt-16 pb-24">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted">{page.eyebrow}</div>
        <h1 className="font-serif mt-4 max-w-3xl">{page.title}</h1>
        <p className="mt-5 max-w-2xl text-text-soft leading-relaxed">{page.summary}</p>
        <button
          onClick={onBrowse}
          className="mt-8 h-11 px-5 rounded-full bg-text text-bg text-sm inline-flex items-center gap-2 hover:opacity-90 transition-opacity"
        >
          Browse the gallery <ArrowRight size={14} />
        </button>
      </motion.div>

      <section className="mt-14 grid md:grid-cols-3 gap-4">
        {page.items.map((item) => {
          const Icon = ICONS[item.icon];
          return (
            <article key={item.title} className="hairline rounded-lg bg-surface p-5">
              <div className="w-9 h-9 rounded-full grid place-items-center gold-gradient text-[var(--accent-ink)]">
                <Icon size={15} />
              </div>
              <h2 className="font-serif text-xl mt-5">{item.title}</h2>
              <p className="text-sm text-text-soft leading-relaxed mt-3">{item.text}</p>
            </article>
          );
        })}
      </section>
    </main>
  );
}
