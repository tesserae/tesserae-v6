import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ScholarshipTab from './ScholarshipTab';
import { mockResponse } from '../../test/mockResponse';

afterEach(() => { delete global.fetch; });

describe('Scholarship tab header', () => {
  it('links to the sources and methods page at the methods section', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({
      ok: true, json: () => Promise.resolve({ passage: { work: 'vergil.aeneid' }, index: { results: [] }, commentary: [] }),
    })));
    render(<ScholarshipTab work="vergil.aeneid" language="la" selection={{ startIdx: 0, endIdx: 0 }}
                           units={[{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano Troiae' }]} />);
    const link = await screen.findByTestId('about-these-sources');
    expect(link).toHaveAttribute('href', '/scholarship-sources#methods');
    expect(link.textContent).toBe('About these sources');
  });
});
