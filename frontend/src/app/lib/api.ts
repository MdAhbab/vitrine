// frontend/src/app/lib/api.ts — drop-in integration layer
const CONFIGURED_BASE = import.meta.env.VITE_API_BASE ?? '/api';
const DEV_DIRECT_BASE = import.meta.env.VITE_DIRECT_API_BASE ?? 'http://127.0.0.1:8000';
const BASES = Array.from(new Set([
  CONFIGURED_BASE,
  ...(import.meta.env.DEV ? ['/api', DEV_DIRECT_BASE] : []),
].filter(Boolean)));
export const USE_MOCKS = (import.meta.env.VITE_USE_MOCKS ?? 'false') === 'true';

const MEDIA_BASE = import.meta.env.VITE_MEDIA_BASE ?? (import.meta.env.DEV ? DEV_DIRECT_BASE : '');

/** Resolve relative `/files/…` paths to the API origin for img src. */
export function mediaUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) return path;
  const base = MEDIA_BASE || BASES[0] || '';
  return `${base.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

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

function apiUrl(base: string, path: string) {
  return `${base.replace(/\/$/, '')}${path}`;
}

function canTryNextBase(error: unknown) {
  if (error instanceof TypeError) return true;
  if (!(error instanceof Error)) return false;
  return error.message.startsWith('404 ') || error.message.includes('Failed to fetch');
}

async function reqFromBase<T>(base: string, path: string, init: RequestInit, retry: boolean): Promise<T> {
  const res = await fetch(apiUrl(base, path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401 && retry && tok.refresh) {
    try {
      const refreshRes = await fetch(apiUrl(base, '/auth/refresh'), {
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

async function uploadReq<T>(path: string, form: FormData, retry = true): Promise<T> {
  let lastError: unknown;
  for (const base of BASES) {
    try {
      const res = await fetch(apiUrl(base, path), {
        method: 'POST',
        headers: tok.access ? { Authorization: `Bearer ${tok.access}` } : {},
        body: form,
      });
      if (res.status === 401 && retry && tok.refresh) {
        const refreshRes = await fetch(apiUrl(base, '/auth/refresh'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: tok.refresh }),
        });
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          tok.set(data.access_token, data.refresh_token);
          return uploadReq<T>(path, form, false);
        }
        tok.clear();
      }
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      return res.json();
    } catch (e) {
      lastError = e;
      if (!canTryNextBase(e)) break;
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Upload failed');
}

async function req<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  let lastError: unknown;
  for (const base of BASES) {
    try {
      return await reqFromBase<T>(base, path, init, retry);
    } catch (e) {
      lastError = e;
      if (!canTryNextBase(e)) break;
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Request failed');
}

export const api = {
  // auth
  signup: (b: any) => req<any>('/auth/signup', { method: 'POST', body: JSON.stringify(b) }),
  login: (b: any) => req<any>('/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  adminLogin: (b: any) => req<any>('/auth/admin/login', { method: 'POST', body: JSON.stringify(b) }),
  me: () => req<any>('/users/me'),
  verifyStudent: () => req<any>('/users/verify-student', { method: 'POST' }),
  getProfile: (userId: string) => req<any>(`/users/${userId}/profile`),
  updateProfile: (b: any) => req<any>('/users/me/profile', { method: 'PUT', body: JSON.stringify(b) }),
  changePassword: (b: any) => req<any>('/users/me/change-password', { method: 'POST', body: JSON.stringify(b) }),
  getBilling: () => req<any>('/users/me/billing'),
  setTokens: tok.set,
  clearTokens: tok.clear,

  // catalog
  listings: (qs = '') => req<any[]>(`/listings${qs}`),
  listing: (slug: string) => req<any>(`/listings/${slug}`),
  createListing: (b: any) => req<any>('/listings', { method: 'POST', body: JSON.stringify(b) }),
  intake: (id: string, b: any) => req<any>(`/listings/${id}/intake`, { method: 'POST', body: JSON.stringify(b) }),
  aiIntake: (id: string, b: any) => req<any>(`/ai/intake?listing_id=${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify(b) }),
  submitListing: (id: string) => req<any>(`/listings/${id}/submit`, { method: 'POST' }),
  updateListing: (id: string, b: any) => req<any>(`/listings/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  deleteListing: (id: string) => req<any>(`/listings/${id}`, { method: 'DELETE' }),

  uploadFile: (file: File, bucket = 'listings') => {
    const fd = new FormData();
    fd.append('file', file);
    return uploadReq<{ url: string; name: string; mime: string; kind: string; size: number }>(
      `/media/upload?bucket=${encodeURIComponent(bucket)}`, fd,
    );
  },
  uploadChatAttachment: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return uploadReq<{ url: string; name: string; mime: string; kind: string; size: number }>(
      '/media/upload/chat', fd,
    );
  },

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
  send: (id: string, body: string, as_agent = false, attachments: { url: string; name: string; mime: string; kind: string; size?: number }[] = []) =>
    req<any>(`/chats/${id}/messages`, { method: 'POST', body: JSON.stringify({ body, as_agent, attachments }) }),
  startNegotiation: (b: any) => req<any>('/chats/negotiate/start', { method: 'POST', body: JSON.stringify(b) }),
  deactivateRep: (chat_id: string) => req<any>(`/chats/${chat_id}/deactivate-rep`, { method: 'POST' }),
  negotiate: (chat_id: string) => req<any>('/ai/negotiate', { method: 'POST', body: JSON.stringify({ chat_id }) }),

  // ai
  pricing: (listing_id: string) => req<any>('/ai/pricing', { method: 'POST', body: JSON.stringify({ listing_id }) }),
  estimateFeature: (b: any) => req<any>('/ai/estimate-feature', { method: 'POST', body: JSON.stringify(b) }),
  featureRequest: (b: any) => req<any>('/feature-requests', { method: 'POST', body: JSON.stringify(b) }),
  getFeatureRequest: (id: string) => req<any>(`/feature-requests/${id}`),
  quoteFeatureRequest: (id: string, b: any) => req<any>(`/feature-requests/${id}/quote`, { method: 'PATCH', body: JSON.stringify(b) }),
  approveFeatureRequest: (id: string) => req<any>(`/feature-requests/${id}/approve`, { method: 'POST' }),

  // misc
  notifications: () => req<any[]>('/notifications'),
  reviews: (listingId: string) => req<any[]>(`/listings/${listingId}/reviews`),
  addReview: (b: any) => req<any>('/reviews', { method: 'POST', body: JSON.stringify(b) }),
  health: (url: string) => req<any>(`/hosting/health?url=${encodeURIComponent(url)}`),

  publicConfig: () => req<any>('/public-config'),
  repostListing: (id: string) => req<any>(`/listings/${id}/repost`, { method: 'POST' }),

  // admin
  adminConfig: () => req<any>('/admin/config'),
  patchAdminConfig: (b: any) => req<any>('/admin/config', { method: 'PATCH', body: JSON.stringify(b) }),
  agentRuns: () => req<any>('/admin/agent-runs'),
  adminVerificationQueue: () => req<any[]>('/admin/verification-queue'),
  adminDecision: (id: string, verdict: string) => req<any>(`/admin/listings/${id}/decision`, { method: 'POST', body: JSON.stringify({ verdict }) }),
  adminChats: () => req<any>('/admin/chats'),
  adminUsers: () => req<any[]>('/admin/users'),
  adminBanUser: (id: string, months: number | 'infinite' | null) => req<any>(`/admin/users/${id}/ban`, { method: 'POST', body: JSON.stringify({ months }) }),
  adminRemoveUser: (id: string) => req<any>(`/admin/users/${id}`, { method: 'DELETE' }),
  adminResetUserPass: (id: string, password: string) => req<any>(`/admin/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ password }) }),
  adminResetOwnPass: (password: string) => req<any>('/admin/reset-password', { method: 'POST', body: JSON.stringify({ password }) }),
  adminReports: () => req<any[]>('/admin/reports'),
  submitReport: (b: { target_type: string, target_id: string, reason: string }) => req<any>('/reports', { method: 'POST', body: JSON.stringify(b) }),
  adminDeleteListing: (id: string) => req<any>(`/admin/listings/${id}`, { method: 'DELETE' }),
  adminEditListing: (id: string, b: any) => req<any>(`/admin/listings/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
  adminEscrowOrders: () => req<any[]>('/admin/escrow'),
  adminEscrowRelease: (id: string) => req<any>(`/admin/escrow/${id}/release`, { method: 'POST' }),
  adminEscrowRefund: (id: string) => req<any>(`/admin/escrow/${id}/refund`, { method: 'POST' }),
  sellerAnalytics: () => req<any>('/seller/analytics'),
  adminAnalytics: () => req<any>('/admin/analytics'),
  recordEvent: (b: { event_type: string, listing_id?: string, slug?: string }) => req<any>('/analytics/event', { method: 'POST', body: JSON.stringify(b) }),
};

// Concierge SSE (POST + stream). Use fetch + ReadableStream reader.
export async function conciergeStream(query: string, onChunk: (c: any) => void) {
  let lastError: unknown;
  for (const base of BASES) {
    try {
      const res = await fetch(apiUrl(base, '/ai/concierge'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tok.access ? { Authorization: `Bearer ${tok.access}` } : {}),
        },
        body: JSON.stringify({ query, history: [] }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`${res.status} ${await res.text()}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split(/\r?\n\r?\n/);
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i];
          const m = line.match(/^data: (.*)$/m);
          if (m) {
            try {
              onChunk(JSON.parse(m[1]));
            } catch (e) {
              // ignore malformed stream fragments
            }
          }
        }
        buf = lines[lines.length - 1];
      }
      return;
    } catch (e) {
      lastError = e;
      if (!canTryNextBase(e)) break;
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Failed to initialize stream');
}
