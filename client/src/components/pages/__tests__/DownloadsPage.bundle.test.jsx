import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import DownloadsPage from '../DownloadsPage';

// The "Run your own Tesserae" section. The core bundle of 14 October 2026 was
// withdrawn on 19 October 2026 (it held the Sahidica New Testament), so the
// page carries the recipe link and the notice, and no bundle download.
describe('Downloads page, the public bundle', () => {
  it('says the bundle is withdrawn and links no bundle file', () => {
    vi.stubGlobal('fetch', vi.fn());
    const { container } = render(<DownloadsPage />);
    expect(screen.getByRole('heading', { name: 'Run your own Tesserae' })).toBeTruthy();
    expect(screen.getByText(/bundle was withdrawn on 19 October/)).toBeTruthy();
    expect(screen.getByText(/Sahidica New\s+Testament, whose license allows academic use only/)).toBeTruthy();
    expect(container.querySelector('a[href*="/static/downloads/bundle/"]')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Download bundle' })).toBeNull();
    expect(screen.getByRole('link', { name: /The recipe/ }).getAttribute('href')).toBe('https://github.com/tesserae/tesserae-v6/blob/main/docs/RUN_YOUR_OWN.md');
    expect(screen.getByText(/offered for non-commercial use/)).toBeTruthy();
  });

  it('offers no Persian, Urdu or Arabic buttons and no window-text archive', () => {
    vi.stubGlobal('fetch', vi.fn());
    const { container } = render(<DownloadsPage />);
    expect(screen.queryByText('Persian')).toBeNull();
    expect(screen.queryByText('Urdu')).toBeNull();
    expect(screen.queryByText('Arabic')).toBeNull();
    expect(screen.getByText(/Persian and Urdu texts are searchable on the site/)).toBeTruthy();
    expect(container.querySelector('a[href*="window_texts"]')).toBeNull();
    expect(screen.getByText(/window-text archive/)).toBeTruthy();
  });

  it('lists the developer files', () => {
    vi.stubGlobal('fetch', vi.fn());
    render(<DownloadsPage />);
    expect(screen.getByRole('heading', { name: 'For developers' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'tesserae-openapi.yaml' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'tesserae_mcp.py' })).toBeTruthy();
  });
});
