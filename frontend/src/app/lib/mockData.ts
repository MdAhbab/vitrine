export type Product = {
  id: string;
  slug: string;
  name: string;
  tagline: string;
  seller: { name: string; handle: string; verified: boolean };
  category: string;
  subcategory?: string;
  tags: string[];
  price: number;
  tiers?: { name: string; price: number; features: string[]; recommended?: boolean }[];
  vitrineScore: number;
  scoreBreakdown: { label: string; value: number }[];
  demoUrl: string;
  demoHealth: 'live' | 'degraded' | 'down';
  badges: ('verified' | 'best-ui' | 'new' | 'live-demo')[];
  screenshots: string[];
  cover: string;
  ratingDistribution: number[]; // 1..5
  rating: number;
  reviewsCount: number;
  description: string;
  spec: SpecSection[];
  framework: string;
  license: 'MIT' | 'Commercial' | 'Apache-2.0' | 'Proprietary';
  hasLiveDemo: boolean;
  createdAt: string;
  sdlc: {
    problem: string;
    solution: string;
    methodology: string;
    discussions: string;
  };
  businessModel: {
    kind: 'for-profit' | 'non-profit' | 'sole-purpose' | 'open-source';
    pitch: string;
    revenueStreams: string[];
  };
  techStack: string[];
  aiDraft?: boolean;
};

export type SpecSection = {
  title: string;
  fields: { label: string; value: string; auto?: boolean; confidence?: 'high' | 'med' | 'low' }[];
};

const COVERS: Record<string, string> = {
  dashboard:
    'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80',
  analytics:
    'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1600&q=80',
  ecommerce:
    'https://images.unsplash.com/photo-1481437156560-3205f6a55735?auto=format&fit=crop&w=1600&q=80',
  ai: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1600&q=80',
  finance:
    'https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=1600&q=80',
  crm: 'https://images.unsplash.com/photo-1556761175-5973dc0f32e7?auto=format&fit=crop&w=1600&q=80',
  cms: 'https://images.unsplash.com/photo-1481487196290-c152efe083f5?auto=format&fit=crop&w=1600&q=80',
  productivity:
    'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1600&q=80',
};

const spec = (overrides: Partial<Record<string, string>> = {}): SpecSection[] => [
  {
    title: 'Planning',
    fields: [
      { label: 'Problem', value: overrides.problem ?? 'Founders need a clean, fast operations cockpit without 12 SaaS subscriptions.', auto: true, confidence: 'high' },
      { label: 'Target user', value: 'Early-stage operators, indie hackers', auto: true, confidence: 'high' },
      { label: 'Outcome', value: 'Replace 3–5 dashboards with one cohesive surface.' },
    ],
  },
  {
    title: 'Design',
    fields: [
      { label: 'Design system', value: 'Custom tokens · Radix primitives', auto: true, confidence: 'high' },
      { label: 'Theming', value: 'Light + Dark, system-aware' },
      { label: 'Accessibility', value: 'WCAG AA, full keyboard nav' },
    ],
  },
  {
    title: 'Development',
    fields: [
      { label: 'Stack', value: overrides.stack ?? 'React 18 · TS · Tailwind · TanStack Query', auto: true, confidence: 'high' },
      { label: 'State', value: 'Zustand + URL state' },
      { label: 'Build', value: 'Vite · pnpm' },
    ],
  },
  {
    title: 'Architecture',
    fields: [
      { label: 'Pattern', value: 'Modular routes · feature folders', auto: true, confidence: 'med' },
      { label: 'API', value: 'REST + SSE for streams' },
    ],
  },
  {
    title: 'Data',
    fields: [
      { label: 'Database', value: 'Postgres · Drizzle ORM', auto: true, confidence: 'high' },
      { label: 'Cache', value: 'Redis (optional)' },
    ],
  },
  {
    title: 'Testing',
    fields: [
      { label: 'Unit', value: 'Vitest · Testing Library', auto: true, confidence: 'med' },
      { label: 'E2E', value: 'Playwright on PR' },
    ],
  },
  {
    title: 'Security',
    fields: [
      { label: 'Auth', value: 'Email + OAuth · JWT refresh', auto: true, confidence: 'med' },
      { label: 'Secrets', value: '.env · KMS in prod' },
    ],
  },
  {
    title: 'Deployment',
    fields: [
      { label: 'Hosting', value: 'Vercel · Fly.io', auto: true, confidence: 'high' },
      { label: 'CI', value: 'GitHub Actions' },
    ],
  },
];

const baseScreens = [
  'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1600&q=80',
  'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1600&q=80',
  'https://images.unsplash.com/photo-1581090700227-1e37b190418e?auto=format&fit=crop&w=1600&q=80',
  'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=80',
];

const make = (
  i: number,
  name: string,
  tagline: string,
  category: string,
  cover: keyof typeof COVERS,
  price: number,
  score: number,
  framework = 'React',
  tags: string[] = [],
  demoUrl = 'https://vercel.com',
  badges: Product['badges'] = ['verified', 'live-demo'],
): Product => ({
  id: `p_${i}`,
  slug: name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
  name,
  tagline,
  seller: { name: ['Atelier Foxglove','North&Type','Studio Korr','Inkwell Labs','Verge Co.','Mira & Sons'][i % 6], handle: `@studio${i}`, verified: true },
  category,
  tags,
  price,
  tiers: [
    { name: 'Source', price, features: ['Full source code', 'MIT-style license', 'Email support'] },
    { name: 'Source + Setup', price: price + 80, features: ['Everything in Source', '1-hr onboarding call', '30 days of fixes'], recommended: true },
    { name: 'Bespoke', price: price + 280, features: ['Brand reskin', 'Custom domain setup', '90 days of support'] },
  ],
  vitrineScore: score,
  scoreBreakdown: [
    { label: 'Completeness', value: 92 },
    { label: 'UI craft', value: score - 2 },
    { label: 'Demo health', value: 96 },
    { label: 'Reviews', value: 88 },
    { label: 'Recency', value: 80 },
    { label: 'Engagement', value: 74 },
  ],
  demoUrl,
  demoHealth: 'live',
  badges,
  screenshots: baseScreens,
  cover: COVERS[cover],
  ratingDistribution: [2, 3, 8, 24, 63],
  rating: 4.7,
  reviewsCount: 128 + i * 7,
  description:
    'A meticulously crafted production-ready application. Every interaction has been considered. Built by makers who care about the seams.',
  spec: spec(),
  framework,
  license: ['MIT', 'Commercial', 'MIT', 'Apache-2.0'][i % 4] as Product['license'],
  hasLiveDemo: true,
  createdAt: new Date(Date.now() - i * 86400000 * 3).toISOString(),
  sdlc: {
    problem: `Teams shipping ${category.toLowerCase()} work are stitching together five tools, three dashboards, and a brittle spreadsheet — and none of them quite fit. ${name} answers the gap with a single, considered surface.`,
    solution: `A focused codebase that ships the 80% of the ${category.toLowerCase()} workflow you actually use, with the seams left clean for the 20% you'll bend to your own house. Comes with seed data, themed light + dark, and a documented architecture.`,
    methodology: `Designed in the open from interviews with ${6 + (i % 4)} operators in adjacent roles. Built iteratively in two-week cycles, with usability tests against each milestone. Every component has a single, named responsibility; no surprise globals.`,
    discussions: `Open questions the buyer should consider: how opinionated should the data layer remain? Is there appetite to bundle a managed-hosting variant? Community has weighed in on threading vs. tabs for cross-entity views.`,
  },
  businessModel: {
    kind: (['for-profit', 'sole-purpose', 'open-source', 'non-profit'] as const)[i % 4],
    pitch: i % 4 === 3
      ? `Distributed as a non-profit civic tool — buyers contribute to ongoing maintenance.`
      : i % 4 === 2
      ? `MIT-licensed source, sold as a polished, supported package — community welcome.`
      : i % 4 === 1
      ? `Sold as a sole-purpose codebase for a single internal workflow — not for resale.`
      : `A commercial codebase you can rebrand, deploy, and bill against — your margin, your customers.`,
    revenueStreams: ['Source license sales', 'Bespoke commissions', 'Support retainers'],
  },
  techStack: [framework, 'TypeScript', 'Tailwind CSS', 'PostgreSQL', 'TanStack Query', 'Vite'],
});

export const PRODUCTS: Product[] = [
  make(1, 'Halcyon', 'A quiet operations cockpit', 'Dashboards', 'dashboard', 89, 96, 'Next.js', ['saas','admin','charts'], 'https://vercel.com', ['verified','live-demo','best-ui']),
  make(2, 'Foxglove Analytics', 'Editorial analytics for serious teams', 'Analytics', 'analytics', 129, 94, 'React', ['analytics','charts','b2b'], 'https://nextjs.org'),
  make(3, 'Lumen Commerce', 'Headless storefront with taste', 'E-commerce', 'ecommerce', 149, 92, 'Next.js', ['commerce','stripe','headless']),
  make(4, 'Atrium AI', 'A chat surface that respects you', 'AI', 'ai', 79, 95, 'React', ['ai','chat','sse'], 'https://react.dev', ['verified','live-demo','new']),
  make(5, 'Ledger Field', 'Finance dashboards, restrained', 'Finance', 'finance', 199, 91, 'React', ['finance','charts']),
  make(6, 'Korr CRM', 'A CRM you actually open on Mondays', 'CRM', 'crm', 99, 90, 'Remix', ['crm','pipeline']),
  make(7, 'Margins', 'A writing-first CMS', 'CMS', 'cms', 59, 89, 'Astro', ['cms','markdown','mdx']),
  make(8, 'Quiet Hours', 'Personal productivity, distilled', 'Productivity', 'productivity', 39, 88, 'React', ['productivity','pwa']),
  make(9, 'Cantata Dash', 'Charts as composition', 'Dashboards', 'dashboard', 119, 93, 'Vue', ['dashboard','vue']),
  make(10, 'Vellum Notes', 'Notes with margins worth keeping', 'Productivity', 'productivity', 29, 87, 'Svelte', ['notes','svelte']),
  make(11, 'Foundry Auth', 'Auth that disappears', 'Auth', 'dashboard', 69, 86, 'Next.js', ['auth','oauth']),
  make(12, 'North Inbox', 'A team inbox in monochrome', 'Productivity', 'productivity', 89, 90, 'React', ['inbox','team']),
  make(13, 'Maison ERP', 'A full enterprise resource platform — sold as a complete codebase', 'Enterprise', 'dashboard', 18500, 97, 'Next.js', ['enterprise','erp','full-app'], 'https://vercel.com', ['verified','live-demo','best-ui']),
  make(14, 'Compass Trading Desk', 'Production-grade trading desk · full app · brand reskinned to your firm', 'Finance', 'finance', 24900, 96, 'React', ['finance','trading','full-app','enterprise'], 'https://nextjs.org', ['verified','live-demo']),
  make(15, 'Vitrine Telehealth', 'HIPAA-aware telehealth platform · full source + 90-day rollout', 'Healthcare', 'analytics', 32000, 95, 'Next.js', ['healthcare','enterprise','full-app'], 'https://react.dev', ['verified','live-demo','new']),
];

export const CATEGORIES = ['Dashboards','Analytics','E-commerce','AI','Finance','CRM','CMS','Productivity','Auth','Enterprise','Healthcare'];
