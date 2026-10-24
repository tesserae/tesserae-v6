import { describe, it, expect, vi, afterEach } from 'vitest';
import { searchFusionStream } from '../api';

afterEach(() => { delete global.fetch; });

describe('searchFusionStream and a pair above the size limit', () => {
  it('throws an error that carries the server answer', async () => {
    const answer = { too_large: true, line_pairs: 99, message: 'Too big.', books: [] };
    global.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      headers: { get: (h) => (h.toLowerCase() === 'content-type' ? 'application/json' : null) },
      json: () => Promise.resolve(answer),
    }));
    await expect(searchFusionStream({ source: 'a', target: 'b' })).rejects.toMatchObject({
      message: 'Too big.', tooLarge: answer,
    });
  });
});
