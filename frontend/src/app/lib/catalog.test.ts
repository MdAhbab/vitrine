import { describe, it, expect, vi } from 'vitest';

vi.mock('./api', () => ({ USE_MOCKS: true }));
vi.mock('./mockData', () => ({
  PRODUCTS: [{ id: '1', slug: 'a', name: 'A', status: 'live' }],
}));

import { catalogProducts } from './store';

describe('catalogProducts', () => {
  it('returns mock PRODUCTS when USE_MOCKS is true', () => {
    const result = catalogProducts([]);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('A');
  });
});
