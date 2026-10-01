/**
 * The Sources (credits) page must show a restricted work's licence credit
 * line and licence words in place of the usual e-text/print source columns,
 * since data/restricted_texts.json carries no provenance for it (the
 * holder's name is not public information the way the rest of the corpus's
 * sourcing is).
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TextCredits from './TextCredits';

function mockFetch() {
  return vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/passages/translations')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ works: {} }) });
    }
    if (u.startsWith('/api/text-credits')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          entries: [
            {
              author: 'Held Author', work: 'History',
              restricted: true,
              credit: 'Source: Test Licence Holder (example.invalid)',
              license: 'indexing and search only; no redistribution',
              e_source: null, print_source: null,
            },
            {
              author: 'Ordinary Poet', work: 'Poem',
              e_source: 'Perseus', e_source_url: 'https://perseus.example/poem',
              print_source: 'An Edition, 1900.', added_by: 'V6 Import',
            },
          ],
          total: 2, offset: 0, limit: 50,
        }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}

describe('Sources page shows a restricted work\'s credit and licence', () => {
  it('shows the credit line and licence words for the restricted entry', async () => {
    global.fetch = mockFetch();
    render(<TextCredits />);
    expect(await screen.findByText('Held Author')).toBeInTheDocument();
    expect(screen.getByText('Source: Test Licence Holder (example.invalid)')).toBeInTheDocument();
    expect(screen.getByText('indexing and search only; no redistribution')).toBeInTheDocument();
  });

  it('leaves an ordinary entry showing its usual e-text and print source', async () => {
    global.fetch = mockFetch();
    render(<TextCredits />);
    expect(await screen.findByText('Ordinary Poet')).toBeInTheDocument();
    expect(screen.getByText('Perseus')).toBeInTheDocument();
    expect(screen.getByText('An Edition, 1900.')).toBeInTheDocument();
  });
});
