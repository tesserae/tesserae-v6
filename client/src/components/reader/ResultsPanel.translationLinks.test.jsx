/**
 * The Translation tab's external-link line.
 *
 * Some translators' English carries no licence to copy (Frances W.
 * Pritchett's Ghalib commentary, "A Desertful of Roses"): the backend sends
 * `external_links` on the /api/translation response instead of (or beside)
 * `text`. This covers the three shapes that field can take: a link with no
 * aligned translation (Ghalib's actual case today), a link alongside an
 * aligned translation, and neither.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [
  { ref: 'ghalib.diwan_wikisource.ghazal.1.1', text: 'naqsh faryaadii' },
  { ref: 'ghalib.diwan_wikisource.ghazal.1.2', text: 'kaaghazii hai pairahan' },
];

const PRITCHETT_LINK = {
  translator: 'Frances W. Pritchett',
  site_title: 'A Desertful of Roses',
  source_url: 'https://franpritchett.com/00ghalib/',
  url: 'https://franpritchett.com/00ghalib/001/1_01.html',
};

function mount(props = {}) {
  render(
    <ResultsPanel
      selection={{ refStart: UNITS[0].ref, refEnd: UNITS[0].ref, startIdx: 0, endIdx: 0 }}
      language="ur"
      work="ghalib.diwan_wikisource"
      units={UNITS}
      initialTab="translation"
      {...props}
    />
  );
}

function mockTranslationResponse(body) {
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    headers: { get: () => 'application/json' },
  }));
}

describe('a link with no aligned translation (Ghalib today)', () => {
  beforeEach(() => {
    mockTranslationResponse({
      available: false,
      reason: 'No aligned open translation for this work.',
      work: 'ghalib.diwan_wikisource',
      external_links: [PRITCHETT_LINK],
    });
  });

  it('shows the translator, the site title, and a working link', async () => {
    mount();
    const link = await screen.findByRole('link', {
      name: /Frances W\. Pritchett.*translation and commentary for this verse/,
    });
    expect(link.getAttribute('href')).toBe(PRITCHETT_LINK.url);
    expect(screen.getByText(/A Desertful of Roses/)).toBeTruthy();
  });

  it('opens the link in a new tab without leaking a referrer/opener', async () => {
    mount();
    const link = await screen.findByRole('link', { name: /Pritchett/ });
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('does not show the generic "no translation" message when a link covers it', async () => {
    mount();
    await screen.findByRole('link', { name: /Pritchett/ });
    expect(screen.queryByText(/No aligned open translation/)).toBeNull();
  });
});

describe('a work with neither an aligned translation nor a link', () => {
  it('falls back to the plain "no translation" message', async () => {
    mockTranslationResponse({
      available: false,
      reason: 'No aligned open translation for this work.',
      work: 'some.other.work',
      external_links: [],
    });
    mount({ language: 'la', work: 'some.other.work' });
    expect(await screen.findByText(/Aligned open translations/)).toBeTruthy();
    expect(screen.queryByRole('link', { name: /translation and commentary/ })).toBeNull();
  });
});

describe('a work with both an aligned translation and a link', () => {
  it('shows the translation text and the link together', async () => {
    mockTranslationResponse({
      available: true,
      work: 'xx.bothwork',
      text: 'the aligned English for this line',
      translator: 'Translator A',
      year: 1900,
      external_links: [PRITCHETT_LINK],
    });
    mount({ language: 'la', work: 'xx.bothwork' });
    expect(await screen.findByText(/the aligned English for this line/)).toBeTruthy();
    const link = await screen.findByRole('link', { name: /Pritchett/ });
    expect(link.getAttribute('href')).toBe(PRITCHETT_LINK.url);
  });
});
