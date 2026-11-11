import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ScholarshipTab from './ScholarshipTab';
import { mockResponse } from '../../test/mockResponse';

afterEach(() => { delete global.fetch; });

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano Troiae' }, { ref: 'verg. aen. 1.33', text: 'tantae molis erat' }];
const SEL = { startIdx: 0, endIdx: 1 };
const ok = (body) => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(body) }));

describe('Scholarship tab link to the viewer page', () => {
  it('uses the tab\'s own total when the list was not cut', async () => {
    global.fetch = vi.fn(() => ok({ passage: { work: 'vergil.aeneid' }, commentary: [], index: { results: [{ title: 'A', source: 'ejc' }], total: 1 } }));
    render(<ScholarshipTab work="vergil.aeneid.tess" language="la" selection={SEL} units={UNITS} />);
    const link = await screen.findByRole('link', { name: 'See all 1 article for this passage' });
    expect(link.getAttribute('href')).toBe('/scholarship/view?work=vergil.aeneid&lo=1.1&hi=1.33&scope=passage');
  });

  it('asks the endpoint for the count (per_page=1) when the tab shows a capped list', async () => {
    global.fetch = vi.fn((url) => (String(url).startsWith('/api/scholarship/list')
      ? ok({ available: true, total: 123, counts: { passage: 123 }, results: [] })
      : ok({ passage: { work: 'vergil.aeneid' }, commentary: [], index: { results: [{ title: 'A', source: 'ejc' }], total: 123 } })));
    render(<ScholarshipTab work="vergil.aeneid" language="la" selection={SEL} units={UNITS} />);
    const link = await screen.findByRole('link', { name: 'See all 123 articles for this passage' });
    expect(link.getAttribute('href')).toContain('/scholarship/view?work=vergil.aeneid');
    const call = global.fetch.mock.calls.map((c) => String(c[0])).find((u) => u.startsWith('/api/scholarship/list'));
    expect(call).toContain('per_page=1');
    expect(call).toContain('lo=1.1');
    await waitFor(() => expect(link).toBeTruthy());
  });
});
