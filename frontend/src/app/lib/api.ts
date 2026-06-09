// frontend/src/app/lib/api.ts — drop-in integration layer
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'true') === 'true';

const tok = {
  get access() { return localStorage.getItem('vitrine_access'); },
  get refresh() { return localStorage.getItem('vitrine_refresh'); },
  set(a: string, r: string) {
    localStorage.setItem('vitrine_access', a);
    localStorage.setItem('vitrine_refresh', r);
  },
  clear() {
    localStorage.removeItem('vitrine_access');
    localStorage.removeItem('vitrine_refresh');
  },
};

async function req<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401 && retry && tok.refresh) {
    try {
      const refreshRes = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tok.refresh }),
      });
      if (refreshRes.ok) {
        const data = await refreshRes.json();
        tok.set(data.access_token, data.refresh_token);
        return await req<T>(path, init, false);
      } else {
        tok.clear();
      }
    } catch (e) {
      tok.clear();
    }
  }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  // auth
  signup: (b: any) => req<any>('/auth/signup', { method: 'POST', body: JSON.stringify(b) }),
  login: (b: any) => req<any>('/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  adminLogin: (b: any) => req<any>('/auth/admin/login', { method: 'POST', body: JSON.stringify(b) }),
  me: () => req<any>('/users/me'),
  verifyStudent: () => req<any>('/users/verify-student', { method: 'POST' }),
  setTokens: tok.set,
  clearTokens: tok.clear,

  // catalog
  listings: (qs = '') => req<any[]>(`/listings${qs}`),
  listing: (slug: string) => req<any>(`/listings/${slug}`),
  createListing: (b: any) => req<any>('/listings', { method: 'POST', body: JSON.stringify(b) }),
  intake: (id: string, b: any) => req<any>(`/listings/${id}/intake`, { method: 'POST', body: JSON.stringify(b) }),
  updateListing: (id: string, b: any) => req<any>(`/listings/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  deleteListing: (id: string) => req<any>(`/listings/${id}`, { method: 'DELETE' }),

  // commerce
  checkout: (b: any) => req<any>('/checkout', { method: 'POST', body: JSON.stringify(b) }),
  orders: (qs = '') => req<any[]>(`/orders${qs}`),
  deliverOrder: (id: string, b: any) => req<any>(`/orders/${id}/deliver`, { method: 'POST', body: JSON.stringify(b) }),
  subscribe: (tier: string) => req<any>('/subscriptions/subscribe', { method: 'POST', body: JSON.stringify({ tier }) }),
  subscriptionStatus: () => req<any>('/subscriptions/status'),
  payouts: () => req<any[]>('/payouts'),
  requestPayout: (b: any) => req<any>('/payouts/request', { method: 'POST', body: JSON.stringify(b) }),

  // chats / negotiation
  chats: () => req<any[]>('/chats'),
  messages: (id: string) => req<any[]>(`/chats/${id}/messages`),
  send: (id: string, body: string, as_agent = false) =>
    req<any>(`/chats/${id}/messages`, { method: 'POST', body: JSON.stringify({ body, as_agent }) }),
  startNegotiation: (b: any) => req<any>('/chats/negotiate/start', { method: 'POST', body: JSON.stringify(b) }),
  negotiate: (chat_id: string) => req<any>('/ai/negotiate', { method: 'POST', body: JSON.stringify({ chat_id }) }),

  // ai
  pricing: (listing_id: string) => req<any>('/ai/pricing', { method: 'POST', body: JSON.stringify({ listing_id }) }),
  estimateFeature: (b: any) => req<any>('/ai/estimate-feature', { method: 'POST', body: JSON.stringify(b) }),
  featureRequest: (b: any) => req<any>('/feature-requests', { method: 'POST', body: JSON.stringify(b) }),
  quoteFeatureRequest: (id: string, b: any) => req<any>(`/feature-requests/${id}/quote`, { method: 'PATCH', body: JSON.stringify(b) }),
  approveFeatureRequest: (id: string) => req<any>(`/feature-requests/${id}/approve`, { method: 'POST' }),

  // misc
  notifications: () => req<any[]>('/notifications'),
  reviews: (listingId: string) => req<any[]>(`/listings/${listingId}/reviews`),
  addReview: (b: any) => req<any>('/reviews', { method: 'POST', body: JSON.stringify(b) }),
  health: (url: string) => req<any>(`/hosting/health?url=${encodeURIComponent(url)}`),

  // admin
  adminConfig: () => req<any>('/admin/config'),
  patchAdminConfig: (b: any) => req<any>('/admin/config', { method: 'PATCH', body: JSON.stringify(b) }),
  agentRuns: () => req<any>('/admin/agent-runs'),
  adminVerificationQueue: () => req<any[]>('/admin/verification-queue'),
  adminDecision: (id: string, verdict: string) => req<any>(`/admin/listings/${id}/decision`, { method: 'POST', body: JSON.stringify({ verdict }) }),
  adminChats: () => req<any>('/admin/chats'),
};

// Concierge SSE (POST + stream). Use fetch + ReadableStream reader.
export async function conciergeStream(query: string, onChunk: (c: any) => void) {
  const res = await fetch(`${BASE}/ai/concierge`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}),
    },
    body: JSON.stringify({ query, history: [] }),
  });
  if (!res.ok || !res.body) {
    throw new Error(`Failed to initialize stream: ${res.status}`);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n\n');
    for (let i = 0; i < lines.length - 1; i++) {
      const line = lines[i];
      const m = line.match(/^data: (.*)$/m);
      if (m) {
        try {
          onChunk(JSON.parse(m[1]));
        } catch (e) {
          // parse error
        }
      }
    }
    buf = lines[lines.length - 1];
  }
}
