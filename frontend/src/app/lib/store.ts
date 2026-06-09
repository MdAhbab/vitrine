import { create } from 'zustand';
import { PRODUCTS, type Product } from './mockData';

export type Role = 'buyer' | 'seller' | 'admin';
export type User = {
  id: string;
  name: string;
  email: string;
  role: Role;
  avatar?: string;
  isStudent?: boolean;
  plan?: SellerPlan;
};

export type SellerPlan = 'free' | 'studio' | 'atelier' | 'maison';

export type Message = {
  id: string;
  threadId: string;
  authorId: string;
  authorName: string;
  isAgent?: boolean;
  body: string;
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
  status: 'pending' | 'paid' | 'refunded';
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
  provider: 'openai' | 'anthropic' | 'gemini' | 'mistral' | 'cohere' | 'stripe' | 'custom';
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
};

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
  startThread: (input: Omit<Thread, 'id' | 'createdAt' | 'status' | 'unreadFor'>) => string;
  sendMessage: (threadId: string, body: string, by: { id: string; name: string; isAgent?: boolean }) => void;
  agentReply: (threadId: string) => Promise<void>;
  recordTransaction: (t: Omit<Transaction, 'id' | 'ts'>) => void;
  setUserPlan: (p: SellerPlan) => void;
  toggleStudent: () => void;
  upsertListing: (l: Listing) => void;
  deleteListing: (id: string) => void;
  adminConfig: AdminConfig;
  updateAdminConfig: (patch: Partial<AdminConfig>) => void;
  addApiKey: (k: Omit<AdminApiKey, 'id' | 'createdAt'>) => void;
  toggleApiKey: (id: string) => void;
  removeApiKey: (id: string) => void;
};

const SELLER_USERS: Record<string, { id: string; name: string }> = {};
PRODUCTS.forEach((p, i) => { SELLER_USERS[p.seller.name] = { id: `seller_${i}`, name: p.seller.name }; });

// Seed: a few demo threads and transactions so admin/seller dashboards never feel empty.
const SEED_BUYER = { id: 'demo_buyer', name: 'June Park' };
const seedThreads: Thread[] = [
  {
    id: 't_seed_1', productId: PRODUCTS[0].id, productName: PRODUCTS[0].name, productCover: PRODUCTS[0].cover,
    buyerId: SEED_BUYER.id, buyerName: SEED_BUYER.name,
    sellerId: SELLER_USERS[PRODUCTS[0].seller.name].id, sellerName: PRODUCTS[0].seller.name,
    isAgent: true, agentBudget: 79, status: 'open', unreadFor: ['seller'],
    createdAt: Date.now() - 1000 * 60 * 60 * 4,
  },
  {
    id: 't_seed_2', productId: PRODUCTS[3].id, productName: PRODUCTS[3].name, productCover: PRODUCTS[3].cover,
    buyerId: 'demo_buyer_2', buyerName: 'Marco Rivers',
    sellerId: SELLER_USERS[PRODUCTS[3].seller.name].id, sellerName: PRODUCTS[3].seller.name,
    isAgent: false, status: 'open', unreadFor: ['seller'],
    createdAt: Date.now() - 1000 * 60 * 60 * 28,
  },
];
const seedMessages: Message[] = [
  { id: 'm1', threadId: 't_seed_1', authorId: 'agent', authorName: 'June\'s AI Rep', isAgent: true, body: 'Hi — I represent June Park. She loves Halcyon and is ready to buy the Source tier today. Could you do $79 instead of $89 for a same-day commit? She\'d also leave a review.', ts: Date.now() - 1000 * 60 * 60 * 4 },
  { id: 'm2', threadId: 't_seed_1', authorId: 'seller', authorName: PRODUCTS[0].seller.name, body: 'Appreciate the directness. $79 works if she takes Source + Setup at the listed price next month.', ts: Date.now() - 1000 * 60 * 60 * 3 },
  { id: 'm3', threadId: 't_seed_2', authorId: 'demo_buyer_2', authorName: 'Marco Rivers', body: 'Hey — does Atrium AI support custom tools out of the box, or is that something I\'d have to wire up myself?', ts: Date.now() - 1000 * 60 * 60 * 28 },
];

const seedTxns: Transaction[] = [
  { id: 'tx_1', productId: PRODUCTS[1].id, productName: PRODUCTS[1].name, buyerId: SEED_BUYER.id, buyerName: SEED_BUYER.name, sellerId: SELLER_USERS[PRODUCTS[1].seller.name].id, sellerName: PRODUCTS[1].seller.name, tier: 'Source + Setup', amount: 209, commission: 21, status: 'paid', ts: Date.now() - 1000 * 60 * 60 * 24 * 3 },
  { id: 'tx_2', productId: PRODUCTS[4].id, productName: PRODUCTS[4].name, buyerId: 'demo_buyer_3', buyerName: 'Hana Cole', sellerId: SELLER_USERS[PRODUCTS[4].seller.name].id, sellerName: PRODUCTS[4].seller.name, tier: 'Bespoke', amount: 479, commission: 48, status: 'paid', ts: Date.now() - 1000 * 60 * 60 * 24 * 5 },
  { id: 'tx_3', productId: PRODUCTS[2].id, productName: PRODUCTS[2].name, buyerId: 'demo_buyer_4', buyerName: 'Sam Ortiz', sellerId: SELLER_USERS[PRODUCTS[2].seller.name].id, sellerName: PRODUCTS[2].seller.name, tier: 'Source', amount: 149, commission: 15, status: 'pending', ts: Date.now() - 1000 * 60 * 60 * 8 },
];

export const useStore = create<State>((set, get) => ({
  user: null,
  threads: seedThreads,
  messages: seedMessages,
  transactions: seedTxns,
  listings: PRODUCTS.map((p, i) => ({ ...p, ownerId: SELLER_USERS[p.seller.name].id, status: 'live' as const })),
  activeReps: [],

  signIn: (u) => set({ user: u }),
  signOut: () => set({ user: null }),

  startThread: (input) => {
    const id = `t_${Math.random().toString(36).slice(2, 9)}`;
    const thread: Thread = { ...input, id, createdAt: Date.now(), status: 'open', unreadFor: ['seller'] };
    set((s) => ({
      threads: [thread, ...s.threads],
      activeReps: input.isAgent ? [...s.activeReps, id] : s.activeReps,
    }));
    return id;
  },

  sendMessage: (threadId, body, by) => {
    const msg: Message = { id: `m_${Math.random().toString(36).slice(2, 9)}`, threadId, authorId: by.id, authorName: by.name, isAgent: by.isAgent, body, ts: Date.now() };
    set((s) => ({
      messages: [...s.messages, msg],
      threads: s.threads.map((t) => t.id === threadId ? { ...t, unreadFor: by.isAgent || by.id !== t.sellerId ? ['seller'] : ['buyer'] } : t),
    }));
  },

  agentReply: async (threadId) => {
    const thread = get().threads.find((t) => t.id === threadId);
    if (!thread || !thread.isAgent) return;
    const last = [...get().messages].reverse().find((m) => m.threadId === threadId);
    if (!last || last.isAgent) return;

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
    const body = lines[Math.floor(Math.random() * lines.length)];
    get().sendMessage(threadId, body, { id: 'agent', name: `${thread.buyerName}'s AI Rep`, isAgent: true });
  },

  recordTransaction: (t) => set((s) => ({
    transactions: [{ ...t, id: `tx_${Math.random().toString(36).slice(2, 9)}`, ts: Date.now() }, ...s.transactions],
  })),

  setUserPlan: (p) => set((s) => ({ user: s.user ? { ...s.user, plan: p } : s.user })),
  toggleStudent: () => set((s) => ({ user: s.user ? { ...s.user, isStudent: !s.user.isStudent } : s.user })),

  upsertListing: (l) => set((s) => {
    const exists = s.listings.some((x) => x.id === l.id);
    return { listings: exists ? s.listings.map((x) => x.id === l.id ? l : x) : [l, ...s.listings] };
  }),
  deleteListing: (id) => set((s) => ({ listings: s.listings.filter((l) => l.id !== id) })),

  adminConfig: DEFAULT_ADMIN_CONFIG,
  updateAdminConfig: (patch) => set((s) => ({ adminConfig: { ...s.adminConfig, ...patch } })),
  addApiKey: (k) => set((s) => ({
    adminConfig: {
      ...s.adminConfig,
      apiKeys: [{ ...k, id: `k_${Math.random().toString(36).slice(2, 9)}`, createdAt: Date.now() }, ...s.adminConfig.apiKeys],
    },
  })),
  toggleApiKey: (id) => set((s) => ({
    adminConfig: { ...s.adminConfig, apiKeys: s.adminConfig.apiKeys.map((k) => k.id === id ? { ...k, enabled: !k.enabled } : k) },
  })),
  removeApiKey: (id) => set((s) => ({
    adminConfig: { ...s.adminConfig, apiKeys: s.adminConfig.apiKeys.filter((k) => k.id !== id) },
  })),
}));

export function activeRepsForBuyer(buyerId: string, threads: Thread[]) {
  return threads.filter((t) => t.buyerId === buyerId && t.isAgent && t.status === 'open');
}

export const PLAN_DETAILS: Record<SellerPlan, { name: string; price: number; posts: number | 'unlimited'; commission: number; perks: string[] }> = {
  free:    { name: 'Free',    price: 0,   posts: 2,           commission: 12, perks: ['2 active listings', 'Standard placement', '12% platform commission'] },
  studio:  { name: 'Studio',  price: 19,  posts: 10,          commission: 8,  perks: ['10 active listings', 'Verified badge', '8% commission', 'Basic analytics'] },
  atelier: { name: 'Atelier', price: 49,  posts: 40,          commission: 5,  perks: ['40 active listings', 'Editorial pitch slots', '5% commission', 'Priority Concierge ranking'] },
  maison:  { name: 'Maison',  price: 129, posts: 'unlimited', commission: 3,  perks: ['Unlimited listings', 'Featured cover rotation', '3% commission', 'Dedicated curator', 'White-glove enterprise listings'] },
};
