import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

// zustand v5 reads getInitialState under SSR, so the catalogue is injected via
// the hook rather than by mutating store state.
const { CATALOG } = vi.hoisted(() => ({ CATALOG: [] as any[] }));
vi.mock('../lib/store', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useCatalogProducts: () => CATALOG,
}));

import { ProductPage } from './ProductPage';

// The exact `/listings/vitrine` payload: a freshly published, user-created
// listing. Empty tiers/ratings/spec and relative `/files/…` media are the
// NORMAL state of a new listing, and used to crash the page outright.
const EMPTY_LISTING: any = {
  id: '272b9df66f004adf9bbc8718f7429c08',
  slug: 'vitrine',
  name: 'vitrine',
  tagline: 'Try the software. Then own it.',
  seller: { name: 'Atelier Foxglove', handle: '@foxglove', verified: true },
  category: 'Web App',
  tags: ['role based auth', 'user management', 'admin panel'],
  price: 89.0,
  tiers: [],
  vitrineScore: 57.0,
  scoreBreakdown: [],
  demoUrl: 'https://vitrine.ahbab.dev/',
  repoUrl: 'https://github.com/MdAhbab/vitrine',
  demoHealth: 'live',
  badges: ['live-demo', 'new'],
  screenshots: [
    '/files/listings/2aaa825c1e9a4147bb1f79b45b598ff7/8dc050de807641ca97cbbac342d82901.png',
    '/files/listings/2aaa825c1e9a4147bb1f79b45b598ff7/562ed6178851405491a181298dee1e8b.png',
  ],
  cover: '/files/listings/2aaa825c1e9a4147bb1f79b45b598ff7/8dc050de807641ca97cbbac342d82901.png',
  ratingDistribution: [],
  rating: 0.0,
  reviewsCount: 0,
  description: 'Built a sophisticated role-based access control system.',
  spec: [],
  framework: 'nodejs',
  license: 'MIT',
  hasLiveDemo: true,
  createdAt: '2026-08-08T02:54:06.342985',
  sdlc: { problem: 'p', solution: 's', methodology: '', discussions: '' },
  businessModel: { kind: 'for-profit', pitch: '', revenueStreams: [] },
  techStack: ['nodejs', 'expressjs', 'sequelize'],
  status: 'live',
  ownerId: '2aaa825c1e9a4147bb1f79b45b598ff7',
};

// The pathological shape: every optional collection missing outright.
const NAKED_LISTING: any = {
  id: 'x', slug: 'naked', name: 'Naked', tagline: '', category: 'Web App',
  price: 12, status: 'live', license: 'MIT', framework: 'x', demoHealth: 'live',
  demoUrl: '', hasLiveDemo: false, description: '', createdAt: 'not-a-date',
  rating: null, reviewsCount: null, vitrineScore: null, cover: '',
};

const noop = () => {};
const render = (slug: string) =>
  renderToStaticMarkup(
    <ProductPage
      slug={slug}
      onOpenProduct={noop}
      onPreview={noop}
      onBargain={noop}
      onRequestFeatures={noop}
      onCheckout={noop}
    />,
  );

describe('ProductPage with empty API collections', () => {
  it('renders a listing whose tiers, ratings and spec are all empty', () => {
    CATALOG.splice(0, CATALOG.length, EMPTY_LISTING);
    const html = render('vitrine');
    // With no tiers the buy path falls back to the listing's own price.
    expect(html).toContain('Buy · $89');
    expect(html).not.toContain('$undefined');
    expect(html).not.toContain('NaN');
    expect(html).not.toContain('undefined%');
    expect(html).toContain('Not yet rated');
    expect(html).toContain('No spec sheet yet');
    // Relative uploads must resolve against the API origin, not Vite's.
    expect(html).toContain('http://127.0.0.1:8000/files/listings/');
  });

  it('survives a listing missing every optional collection', () => {
    CATALOG.splice(0, CATALOG.length, NAKED_LISTING);
    const html = render('naked');
    expect(html).toContain('Buy · $12');
    expect(html).not.toContain('NaN');
    expect(html).not.toContain('undefined');
  });
});
