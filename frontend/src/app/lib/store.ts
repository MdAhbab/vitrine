import { create } from 'zustand';
import { useMemo } from 'react';
import { PRODUCTS, type Product } from './mockData';
import { api, USE_MOCKS } from './api';

export type Role = 'buyer' | 'seller' | 'admin';
export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  avatar?: string;
  isStudent?: boolean;
  plan?: SellerPlan;
  bio?: string;
  location?: string;
  themeDefault?: string;
  minimalProfile?: boolean;
  aiPoints?: number;
};

export type SellerPlan = 'free' | 'studio' | 'atelier' | 'maison';

export type MessageAttachment = {
  url: string;
  name: string;
  mime: string;
  kind: string;
  size?: number;
};

export type Message = {
  id: string;
  threadId: string;
  authorId: string;
  authorName: string;
  isAgent?: boolean;
  body: string;
  attachments?: MessageAttachment[];
  ts: number;
};

export type Thread = {
  id: string;
  productId: string;
  productName: string;
  productCover: string;
  buyerId: string;
  buyerName: string;
  sellerId: string;
  sellerName: string;
  isAgent: boolean;        // true if buyer is using AI rep
  agentBudget?: number;    // max the buyer authorized agent to spend
  status: 'open' | 'closed' | 'settled';
  unreadFor: Role[];
  createdAt: number;
};

export type Transaction = {
  id: string;
  productId: string;
  productName: string;
  buyerId: string;
  buyerName: string;
  sellerId: string;
  sellerName: string;
  tier: string;
  amount: number;          // gross
  commission: number;      // platform cut
  status: 'pending' | 'paid' | 'refunded' | 'delivered';
  escrow_status?: 'pending' | 'holding' | 'released' | 'refunded';
  ts: number;
};

export type Order = Transaction & {
  delivered?: boolean;
  licenseKey?: string;
};

export type Listing = Product & {
  ownerId: string;
  status: 'live' | 'in-review' | 'draft' | 'rejected';
};

export type AdminApiKey = {
  id: string;
  provider: 'openai' | 'anthropic' | 'gemini' | 'grok' | 'nvidia' | 'stripe' | 'custom';
  label: string;
  key: string;
  enabled: boolean;
  createdAt: number;
};

export type FeatureFlags = {
  aiBargain: boolean;
  conciergeSearch: boolean;
  enterpriseTier: boolean;
  studentDiscount: boolean;
  newSignupsOpen: boolean;
};

export type AdminConfig = {
  systemPrompts: {
    concierge: string;
    buyerRep: string;
    pricingAgent: string;
    verification: string;
  };
  apiKeys: AdminApiKey[];
  flags: FeatureFlags;
  fees: { commissionFree: number; commissionStudio: number; commissionAtelier: number; commissionMaison: number; enterprise: number; processing: number };
  escrow: { holdHours: number; refundWindow: number; autoRelease: boolean };
  branding: { headline: string; tagline: string; supportEmail: string };
  notes: string;
  featuredIds: string[];
  categories?: string[];
  frameworks?: string[];
  sections?: string[];
  forms?: any[];
};

const STATUS_MAP: Record<string, Listing['status']> = {
  review: 'in-review',
  enriching: 'in-review',
  flagged: 'in-review',
  draft: 'draft',
  live: 'live',
  rejected: 'rejected',
  paused: 'draft',
  archived: 'draft',
};

export function normalizeListing(raw: Record<string, unknown>): Listing {
  const status = STATUS_MAP[String(raw.status ?? 'draft')] ?? (raw.status as Listing['status']) ?? 'draft';
  return { ...(raw as Listing), status };
}

const DEFAULT_ADMIN_CONFIG: AdminConfig = {
  systemPrompts: {
    concierge: `You are Vitrine's Concierge. Help buyers find the right software piece. Match against the catalog by category, framework, tone, and budget. Default to two suggestions unless asked for more. Never invent products that aren't in the catalog.`,
    buyerRep: `You are a buyer's negotiating rep on Vitrine. You are warm but firm. You never exceed the authorized budget without explicit approval. You reference the buyer's brief (README, must-haves, timeline) in every message to demonstrate that you understand their context.`,
    pricingAgent: `You are Vitrine's Pricing & Pitch agent. Auto-quote custom-feature requests based on comparable work in similar categories. Be transparent about ranges — pricing is a starting point for the seller, not a final invoice.`,
    verification: `You are Vitrine's Verification agent. Reject any listing whose live demo is down, whose claimed framework doesn't match the repo, or whose screenshots look AI-generated. Flag, do not auto-approve, anything priced above $5,000.`,
  },
  apiKeys: [
    { id: 'k_default_oai', provider: 'openai', label: 'Concierge — primary', key: 'sk-••••••••••••••••QF7', enabled: true, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 90 },
    { id: 'k_default_ant', provider: 'anthropic', label: 'Buyer Rep — primary', key: 'sk-ant-••••••••••••XQ9', enabled: true, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 41 },
    { id: 'k_default_strp', provider: 'stripe', label: 'Payments (live)', key: 'sk_live_••••••••H3z', enabled: true, createdAt: Date.now() - 1000 * 60 * 60 * 24 * 180 },
  ],
  flags: { aiBargain: true, conciergeSearch: true, enterpriseTier: true, studentDiscount: true, newSignupsOpen: true },
  fees: { commissionFree: 12, commissionStudio: 8, commissionAtelier: 5, commissionMaison: 3, enterprise: 2, processing: 2.5 },
  escrow: { holdHours: 48, refundWindow: 7, autoRelease: true },
  branding: { headline: 'Software, but make it editorial.', tagline: 'A boutique marketplace for live, runnable software.', supportEmail: 'curator@vitrine.io' },
  notes: '',
  featuredIds: [],
  categories: ['Dashboards','Analytics','E-commerce','AI','Finance','CRM','CMS','Productivity','Auth','Enterprise','Healthcare'],
  frameworks: ['Next.js', 'React', 'Vue', 'Svelte', 'Remix', 'Astro', 'Go'],
  sections: ["Planning", "Design", "Development", "Architecture", "Data", "Testing", "Security", "Deployment"],
  forms: [],
};

type State = {
  user: User | null;
  threads: Thread[];
  messages: Message[];
  transactions: Transaction[];
  listings: Listing[];
  activeReps: string[];       // thread ids that are agent reps for current buyer
  signIn: (u: User) => void;
  signOut: () => void;
  updateUser: (fields: Partial<User>) => void;
  startThread: (input: Omit<Thread, 'id' | 'createdAt' | 'status' | 'unreadFor'>) => string;
  sendMessage: (threadId: string, body: string, by: { id: string; name: string; isAgent?: boolean }, attachments?: MessageAttachment[]) => Promise<void>;
  agentReply: (threadId: string) => Promise<void>;
  deactivateRep: (threadId: string) => Promise<void>;
  recordTransaction: (t: Omit<Transaction, 'id' | 'ts'>) => void;
  setUserPlan: (p: SellerPlan) => Promise<void>;
  toggleStudent: () => Promise<void>;
  upsertListing: (l: Listing) => Promise<void>;
  deleteListing: (id: string) => Promise<void>;
  adminConfig: AdminConfig;
  updateAdminConfig: (patch: Partial<AdminConfig>) => Promise<void>;
  addApiKey: (k: Omit<AdminApiKey, 'id' | 'createdAt'>) => Promise<void>;
  toggleApiKey: (id: string) => Promise<void>;
  removeApiKey: (id: string) => Promise<void>;
  loadSession: () => Promise<void>;
  loadData: () => Promise<void>;
  loadMessages: (threadId: string) => Promise<void>;
  categories: string[];
  frameworks: string[];
  sections: string[];
  forms: any[];
  loadPublicConfig: () => Promise<void>;
};

export const MOCK_USER_IDS = {
  buyer: 'demo_buyer',
  seller: 'demo_seller',
  admin: 'demo_admin',
} as const;

const SELLER_USERS: Record<string, { id: string; name: string }> = {};
PRODUCTS.forEach((p, i) => {
  const name = p.seller?.name;
  if (name) SELLER_USERS[name] = { id: `seller_${i}`, name };
});

function sellerFor(product: Partial<Product> | undefined, fallbackIndex = 0): { id: string; name: string } {
  const name = product?.seller?.name ?? 'Unknown Seller';
  return SELLER_USERS[name] ?? { id: `seller_${Math.max(fallbackIndex, 0)}`, name };
}

export function sellerIdFor(product: Product): string {
  const idx = PRODUCTS.findIndex((p) => p.id === product.id);
  return sellerFor(product, idx).id;
}

// Seed: a few demo threads and transactions so admin/seller dashboards never feel empty.
const SEED_BUYER = { id: MOCK_USER_IDS.buyer, name: 'June Park' };
const seedThreads: Thread[] = (() => {
  const p0 = PRODUCTS[0];
  const p3 = PRODUCTS[3];
  const threads: Thread[] = [];
  if (p0?.id && p0.name) {
    const seller = sellerFor(p0, 0);
    threads.push({
      id: 't_seed_1', productId: p0.id, productName: p0.name, productCover: p0.cover ?? '',
      buyerId: SEED_BUYER.id, buyerName: SEED_BUYER.name,
      sellerId: seller.id, sellerName: seller.name,
      isAgent: true, agentBudget: 79, status: 'open', unreadFor: ['seller'],
      createdAt: Date.now() - 1000 * 60 * 60 * 4,
    });
  }
  if (p3?.id && p3.name) {
    const seller = sellerFor(p3, 3);
    threads.push({
      id: 't_seed_2', productId: p3.id, productName: p3.name, productCover: p3.cover ?? '',
      buyerId: 'demo_buyer_2', buyerName: 'Marco Rivers',
      sellerId: seller.id, sellerName: seller.name,
      isAgent: false, status: 'open', unreadFor: ['seller'],
      createdAt: Date.now() - 1000 * 60 * 60 * 28,
    });
  }
  return threads;
})();

const seedMessages: Message[] = (() => {
  const p0 = PRODUCTS[0];
  const p3 = PRODUCTS[3];
  const messages: Message[] = [];
  if (p0?.name) {
    const seller = sellerFor(p0, 0);
    messages.push(
      { id: 'm1', threadId: 't_seed_1', authorId: 'agent', authorName: 'June\'s AI Rep', isAgent: true, body: `Hi — I represent June Park. She loves ${p0.name} and is ready to buy the Source tier today. Could you do $79 for a same-day commit? She'd also leave a review.`, ts: Date.now() - 1000 * 60 * 60 * 4 },
      { id: 'm2', threadId: 't_seed_1', authorId: 'seller', authorName: seller.name, body: 'Appreciate the directness. $79 works if she takes Source + Setup at the listed price next month.', ts: Date.now() - 1000 * 60 * 60 * 3 },
    );
  }
  if (p3?.name) {
    messages.push({ id: 'm3', threadId: 't_seed_2', authorId: 'demo_buyer_2', authorName: 'Marco Rivers', body: `Hey — does ${p3.name} support custom tools out of the box, or is that something I'd have to wire up myself?`, ts: Date.now() - 1000 * 60 * 60 * 28 });
  }
  return messages;
})();

const seedTxns: Transaction[] = [PRODUCTS[1], PRODUCTS[4], PRODUCTS[2]].flatMap((p, i) => {
  if (!p?.id || !p.name) return [];
  const seller = sellerFor(p, i);
  const buyers = [
    { id: SEED_BUYER.id, name: SEED_BUYER.name, tier: 'Source + Setup', amount: 209, commission: 21, status: 'paid' as const, ageDays: 3 },
    { id: 'demo_buyer_3', name: 'Hana Cole', tier: 'Bespoke', amount: 479, commission: 48, status: 'paid' as const, ageDays: 5 },
    { id: 'demo_buyer_4', name: 'Sam Ortiz', tier: 'Source', amount: 149, commission: 15, status: 'pending' as const, ageDays: 1 / 3 },
  ];
  const b = buyers[i];
  return [{
    id: `tx_${i + 1}`, productId: p.id, productName: p.name, buyerId: b.id, buyerName: b.name,
    sellerId: seller.id, sellerName: seller.name, tier: b.tier, amount: b.amount,
    commission: b.commission, status: b.status, ts: Date.now() - 1000 * 60 * 60 * 24 * b.ageDays,
  }];
});

export const useStore = create<State>((set, get) => ({
  user: null,
  threads: seedThreads,
  messages: seedMessages,
  transactions: seedTxns,
  listings: PRODUCTS.map((p, i) => ({ ...p, ownerId: sellerFor(p, i).id, status: 'live' as const })),
  activeReps: [],
  categories: ['Dashboards','Analytics','E-commerce','AI','Finance','CRM','CMS','Productivity','Auth','Enterprise','Healthcare'],
  frameworks: ['Next.js', 'React', 'Vue', 'Svelte', 'Remix', 'Astro', 'Go'],
  sections: ["Planning", "Design", "Development", "Architecture", "Data", "Testing", "Security", "Deployment"],
  forms: [],

  signIn: (u) => {
    set({ user: u });
    get().loadData().catch(console.error);
  },
  signOut: () => {
    if (!USE_MOCKS) api.clearTokens();
    set({ user: null, threads: [], messages: [], transactions: [] });
  },
  updateUser: (fields) => {
    set((s) => ({ user: s.user ? { ...s.user, ...fields } : null }));
  },

  startThread: (input) => {
    const id = `t_${Math.random().toString(36).slice(2, 9)}`;
    const thread: Thread = { ...input, id, createdAt: Date.now(), status: 'open', unreadFor: ['seller'] };
    set((s) => ({
      threads: [thread, ...s.threads],
      activeReps: input.isAgent ? [...s.activeReps, id] : s.activeReps,
    }));
    return id;
  },

  sendMessage: async (threadId, body, by, attachments = []) => {
    if (USE_MOCKS) {
      const msg: Message = { id: `m_${Math.random().toString(36).slice(2, 9)}`, threadId, authorId: by.id, authorName: by.name, isAgent: by.isAgent, body, attachments, ts: Date.now() };
      set((s) => ({
        messages: [...s.messages, msg],
        threads: s.threads.map((t) => t.id === threadId ? { ...t, unreadFor: by.isAgent || by.id !== t.sellerId ? ['seller'] : ['buyer'] } : t),
      }));
      return;
    }
    try {
      await api.send(threadId, body, by.isAgent, attachments);
      await get().loadMessages(threadId);
    } catch (e) {
      console.error(e);
      throw e;
    }
  },

  agentReply: async (threadId) => {
    const thread = get().threads.find((t) => t.id === threadId);
    if (!thread || !thread.isAgent) return;
    const last = [...get().messages].reverse().find((m) => m.threadId === threadId);
    if (!last || last.isAgent) return;

    if (USE_MOCKS) {
      const priorOrders = get().transactions.filter((t) => t.buyerId === thread.buyerId && t.status === 'paid');
      const spend = priorOrders.reduce((s, t) => s + t.amount, 0);
      const isRepeat = priorOrders.length > 0;

      const lines = [
        `Understood. On behalf of ${thread.buyerName}, I can authorize up to $${thread.agentBudget ?? 0}.`,
        isRepeat
          ? `Worth noting — ${thread.buyerName} has placed ${priorOrders.length} order${priorOrders.length === 1 ? '' : 's'} on Vitrine ($${spend.toLocaleString()} lifetime). Repeat buyers deserve a small concession.`
          : `${thread.buyerName} would be a first-time buyer on Vitrine — a smooth close means a strong inaugural review.`,
        'If you bundle a brand reskin and a 30-day support window, my client will close today.',
        'I have a counter — would you take 10% off in exchange for a public review and a case study?',
      ];
      await new Promise((r) => setTimeout(r, 700));
      const text = lines[Math.floor(Math.random() * lines.length)];
      get().sendMessage(threadId, text, { id: 'agent', name: `${thread.buyerName}'s AI Rep`, isAgent: true });
    } else {
      try {
        await api.negotiate(threadId);
        await get().loadMessages(threadId);
      } catch (e) {
        console.error("Agent negotiation failed", e);
      }
    }
  },

  deactivateRep: async (threadId) => {
    if (USE_MOCKS) {
      set((s) => ({
        threads: s.threads.map((t) => t.id === threadId ? { ...t, isAgent: false, agentBudget: undefined } : t),
        activeReps: s.activeReps.filter((id) => id !== threadId),
      }));
      return;
    }
    try {
      await api.deactivateRep(threadId);
      await get().loadData();
    } catch (e) {
      console.error(e);
    }
  },

  recordTransaction: (t) => {
    set((s) => ({
      transactions: [{ ...t, id: `tx_${Math.random().toString(36).slice(2, 9)}`, ts: Date.now() } as Transaction, ...s.transactions],
    }));
    if (!USE_MOCKS) {
      get().loadData().catch(console.error);
    }
  },

  setUserPlan: async (p) => {
    if (USE_MOCKS) {
      set((s) => ({ user: s.user ? { ...s.user, plan: p } : s.user }));
      return;
    }
    try {
      await api.subscribe(p);
      const me = await api.me();
      set({ user: me });
    } catch (e) {
      console.error(e);
    }
  },

  toggleStudent: async () => {
    if (USE_MOCKS) {
      set((s) => ({ user: s.user ? { ...s.user, isStudent: !s.user.isStudent } : s.user }));
      return;
    }
    try {
      await api.verifyStudent();
      const me = await api.me();
      set({ user: me });
    } catch (e) {
      console.error(e);
    }
  },

  upsertListing: async (l) => {
    if (USE_MOCKS) {
      const exists = get().listings.some((x) => x.id === l.id);
      set((s) => ({ listings: exists ? s.listings.map((x) => x.id === l.id ? l : x) : [l, ...s.listings] }));
      return;
    }
    try {
      const patch = {
        name: l.name,
        tagline: l.tagline,
        category: l.category,
        framework: l.framework,
        price: l.price,
        description: l.description,
        cover: l.cover,
        screenshots: l.screenshots,
        tags: l.tags,
        sdlc: l.sdlc,
        business_model: l.businessModel,
        tech_stack: l.techStack,
        ai_draft: l.aiDraft
      };
      await api.updateListing(l.id, patch);
      await get().loadData();
    } catch (e) {
      console.error(e);
    }
  },

  deleteListing: async (id) => {
    if (USE_MOCKS) {
      set((s) => ({ listings: s.listings.filter((l) => l.id !== id) }));
      return;
    }
    try {
      await api.deleteListing(id);
      await get().loadData();
    } catch (e) {
      console.error(e);
    }
  },

  adminConfig: DEFAULT_ADMIN_CONFIG,
  updateAdminConfig: async (patch) => {
    if (USE_MOCKS) {
      set((s) => ({
        adminConfig: { ...s.adminConfig, ...patch },
        categories: patch.categories ?? s.categories,
        frameworks: patch.frameworks ?? s.frameworks,
        sections: patch.sections ?? s.sections,
        forms: patch.forms ?? s.forms,
      }));
      return;
    }
    try {
      await api.patchAdminConfig(patch);
      const conf = await api.adminConfig();
      set({ adminConfig: conf });
      await get().loadPublicConfig();
    } catch (e) {
      console.error(e);
    }
  },

  addApiKey: async (k) => {
    const newKey = { ...k, id: `k_${Math.random().toString(36).slice(2, 9)}`, createdAt: Date.now() };
    const apiKeys = [...get().adminConfig.apiKeys, newKey];
    if (USE_MOCKS) {
      set((s) => ({ adminConfig: { ...s.adminConfig, apiKeys } }));
      return;
    }
    await get().updateAdminConfig({ apiKeys });
  },

  toggleApiKey: async (id) => {
    const apiKeys = get().adminConfig.apiKeys.map((k) => k.id === id ? { ...k, enabled: !k.enabled } : k);
    if (USE_MOCKS) {
      set((s) => ({ adminConfig: { ...s.adminConfig, apiKeys } }));
      return;
    }
    await get().updateAdminConfig({ apiKeys });
  },

  removeApiKey: async (id) => {
    const apiKeys = get().adminConfig.apiKeys.filter((k) => k.id !== id);
    if (USE_MOCKS) {
      set((s) => ({ adminConfig: { ...s.adminConfig, apiKeys } }));
      return;
    }
    await get().updateAdminConfig({ apiKeys });
  },

  loadPublicConfig: async () => {
    if (USE_MOCKS) return;
    try {
      const cfg = await api.publicConfig();
      if (cfg) {
        set({
          categories: cfg.categories || [],
          frameworks: cfg.frameworks || [],
          sections: cfg.sections || [],
          forms: cfg.forms || []
        });
      }
    } catch (e) {
      console.error("Failed to load public config", e);
    }
  },

  loadSession: async () => {
    if (USE_MOCKS) return;
    try {
      await get().loadPublicConfig();
      const access = localStorage.getItem('vitrine_access');
      if (access) {
        const user = await api.me();
        set({ user });
        await get().loadData();
      } else {
        const listings = (await api.listings()).map((l) => normalizeListing(l));
        set({ listings });
      }
    } catch (e) {
      api.clearTokens();
      try {
        const listings = (await api.listings()).map((l) => normalizeListing(l));
        set({ user: null, listings });
      } catch {
        // ignore
      }
    }
  },

  loadData: async () => {
    if (USE_MOCKS) return;
    try {
      await get().loadPublicConfig();
      const user = get().user;
      let listings = (await api.listings()).map((l) => normalizeListing(l));
      if (user && (user.role === 'seller' || user.role === 'admin')) {
        try {
          const mine = (await api.listings('?owner=me')).map((l) => normalizeListing(l));
          const byId = new Map<string, Listing>();
          for (const l of [...listings, ...mine]) byId.set(l.id, l);
          listings = Array.from(byId.values());
        } catch { /* non-fatal */ }
      }
      set({ listings });
      if (user) {
        const [threads, txns] = await Promise.all([
          api.chats(),
          api.orders()
        ]);
        set({ threads, transactions: txns });
        if (user.role === 'admin') {
          const conf = await api.adminConfig();
          set({ adminConfig: conf });
        }
      }
    } catch (e) {
      console.error("Failed to load data", e);
    }
  },

  loadMessages: async (threadId: string) => {
    if (USE_MOCKS) return;
    try {
      const msgs = await api.messages(threadId);
      set((s) => {
        const others = s.messages.filter((m) => m.threadId !== threadId);
        return { messages: [...others, ...msgs] };
      });
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  },
}));

/** Public gallery products — mock data in dev, API listings when live. */
export function catalogProducts(listings: Listing[]): Product[] {
  if (USE_MOCKS) return PRODUCTS;
  return listings.filter((l) => l.status === 'live');
}

export function useCatalogProducts(): Product[] {
  const listings = useStore((s) => s.listings);
  return useMemo(() => catalogProducts(listings), [listings]);
}

export function activeRepsForBuyer(buyerId: string, threads: Thread[]) {
  return threads.filter((t) => t.buyerId === buyerId && t.isAgent && t.status === 'open');
}

export const PLAN_DETAILS: Record<SellerPlan, { name: string; price: number; posts: number | 'unlimited'; commission: number; perks: string[] }> = {
  free:    { name: 'Free',    price: 0,   posts: 2,           commission: 12, perks: ['2 active listings', 'Standard placement', '12% platform commission'] },
  studio:  { name: 'Studio',  price: 19,  posts: 10,          commission: 8,  perks: ['10 active listings', 'Verified badge', '8% commission', 'Basic analytics'] },
  atelier: { name: 'Atelier', price: 49,  posts: 40,          commission: 5,  perks: ['40 active listings', 'Editorial pitch slots', '5% commission', 'Priority Concierge ranking'] },
  maison:  { name: 'Maison',  price: 129, posts: 'unlimited', commission: 3,  perks: ['Unlimited listings', 'Featured cover rotation', '3% commission', 'Dedicated curator', 'White-glove enterprise listings'] },
};
