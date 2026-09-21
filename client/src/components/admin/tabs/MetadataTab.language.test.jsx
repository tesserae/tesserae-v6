/**
 * The corpus-metadata table's Lang column was a ternary --
 * `language === 'la' ? 'Latin' : language === 'grc' ? 'Greek' : 'English'` --
 * so every Coptic or Hebrew row (both live in production, and the default
 * "All Languages" filter shows them) read "English" (code review
 * 2026-09-21, findings 3/4: the exact "falls back to English" bug
 * utils/languageNames.js was created to close, found again here).
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import MetadataTab from './MetadataTab';

const TEXTS = [
  { id: 'vergil.aeneid.tess', author: 'Vergil', title: 'Aeneid', language: 'la', text_type: 'poetry' },
  { id: 'shenoute.canons.tess', author: 'Shenoute', title: 'Canons', language: 'cop', text_type: 'prose' },
  { id: 'genesis.tess', author: 'Anonymous', title: 'Genesis', language: 'he', text_type: 'prose' },
];

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ texts: TEXTS }) }));
});

describe('the Lang column', () => {
  it('names Coptic and Hebrew rows correctly instead of defaulting to "English"', async () => {
    render(<MetadataTab authHeaders={{}} />);
    await waitFor(() => expect(screen.getByText('Shenoute')).toBeTruthy());
    const table = screen.getByRole('table');
    expect(within(table).getByText('Coptic')).toBeTruthy();
    expect(within(table).getByText('Hebrew')).toBeTruthy();
    // "English" should appear in no row of the table -- there is no English
    // row here, and that's exactly the bug: Coptic and Hebrew both used to
    // land on it. (The filter dropdown above the table has its own
    // "English" option, which this deliberately doesn't check.)
    expect(within(table).queryByText('English')).toBeNull();
  });
});
