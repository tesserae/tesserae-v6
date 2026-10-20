import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import DownloadsPage from '../DownloadsPage';

// The "Run your own Tesserae" section. The core bundle of 14 October 2026 was
// withdrawn on 20 October 2026 (it held the Sahidica New Testament). The
// rebuilt bundle of 19 October is offered with its checksum, manifest and
// license file, and the page says why the earlier one went.
describe('Downloads page, the public bundle', () => {
  it('offers the 19 October bundle with its four files and says the 14 October one was withdrawn', () => {
    vi.stubGlobal('fetch', vi.fn());
    const { container } = render(<DownloadsPage />);
    expect(screen.getByRole('heading', { name: 'Run your own Tesserae' })).toBeTruthy();
    expect(screen.getByText(/Core bundle, 20 October 2026/)).toBeTruthy();
    expect(screen.getByText(/bundle was withdrawn on 19 October/)).toBeTruthy();
    expect(screen.getByText(/Sahidica New\s+Testament, whose license allows academic use only/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Download bundle' }).getAttribute('href'))
      .toBe('/static/downloads/bundle/tesserae-public-core-20261020.tar.zst');
    expect(screen.getByRole('link', { name: 'Checksum' }).getAttribute('href'))
      .toBe('/static/downloads/bundle/tesserae-public-core-20261020.tar.zst.sha256');
    expect(screen.getByRole('link', { name: /Manifest/ }).getAttribute('href'))
      .toBe('/static/downloads/bundle/MANIFEST-core-20261020.tsv');
    expect(screen.getByRole('link', { name: 'License file' }).getAttribute('href'))
      .toBe('/static/downloads/bundle/LICENSES-core-20261020.md');
    const links = [...container.querySelectorAll('a[href*="/static/downloads/bundle/"]')].map(a => a.getAttribute('href'));
    expect(links).toHaveLength(4);
    expect(links.some(h => h.includes('20261014'))).toBe(false);
    expect(screen.getByRole('link', { name: /The recipe/ }).getAttribute('href')).toBe('https://github.com/tesserae/tesserae-v6/blob/main/docs/RUN_YOUR_OWN.md');
    expect(screen.getByText(/offered for non-commercial use/)).toBeTruthy();
  });

  it('offers no Persian, Urdu or Arabic buttons and the filtered window-text archive', () => {
    vi.stubGlobal('fetch', vi.fn());
    const { container } = render(<DownloadsPage />);
    expect(screen.queryByText('Persian')).toBeNull();
    expect(screen.queryByText('Urdu')).toBeNull();
    expect(screen.queryByText('Arabic')).toBeNull();
    expect(screen.getByText(/Persian and Urdu texts are searchable on the site/)).toBeTruthy();
    expect(container.querySelector('a[href*="window_texts"]')).toBeTruthy();
    expect(screen.getByText(/offered again without them/)).toBeTruthy();
  });

  it('lists the developer files', () => {
    vi.stubGlobal('fetch', vi.fn());
    render(<DownloadsPage />);
    expect(screen.getByRole('heading', { name: 'For developers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'tesserae-openapi.yaml' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'tesserae_mcp.py' })).toBeTruthy();
  });

  it('lists the ten added data sets with a license note each', () => {
    vi.stubGlobal('fetch', vi.fn());
    const { container } = render(<DownloadsPage />);
    const files = ['ur_index.db.tar.gz', 'entities.sqlite.tar.gz', 'event_dossiers.sqlite.tar.gz', 'coins.tar.gz',
      'objects.sqlite.tar.gz', 'dictionaries.tar.gz', 'latin_lemma_tables.tar.gz', 'text_descriptions.tar.gz',
      'citations_without_sentences.tar.gz', 'window_texts.db.tar.gz'];
    for (const f of files) {
      expect(container.querySelector(`a[href$="/tesserae-data/${f}"]`)).toBeTruthy();
    }
    expect(screen.getByText(/CC BY-NC-SA 4.0, non-commercial, 111,739 forms/)).toBeTruthy();
    expect(screen.getByText(/The Urdu search index, which holds the line text/)).toBeTruthy();
  });
});
