import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import DownloadsPage from '../DownloadsPage';

// The "Run your own Tesserae" section (2026-10-14): the core bundle's download,
// its checksum, manifest, license file and the recipe, and the non-commercial
// sentence, are on the Downloads page.
describe('Downloads page, the public bundle', () => {
  it('links the core bundle, its checksum, manifest, license file and the recipe', () => {
    vi.stubGlobal('fetch', vi.fn());
    render(<DownloadsPage />);
    expect(screen.getByRole('heading', { name: 'Run your own Tesserae' })).toBeTruthy();
    const bundle = screen.getByRole('link', { name: 'Download bundle' });
    expect(bundle.getAttribute('href')).toMatch(/^\/static\/downloads\/bundle\/tesserae-public-core-\d{8}\.tar\.zst$/);
    expect(screen.getByRole('link', { name: 'Checksum' }).getAttribute('href')).toMatch(/\.tar\.zst\.sha256$/);
    expect(screen.getByRole('link', { name: /Manifest/ }).getAttribute('href')).toMatch(/MANIFEST-core-\d{8}\.tsv$/);
    expect(screen.getByRole('link', { name: 'License file' }).getAttribute('href')).toMatch(/LICENSES-core-\d{8}\.md$/);
    expect(screen.getByRole('link', { name: /The recipe/ }).getAttribute('href')).toBe('https://github.com/tesserae/tesserae-v6/blob/main/docs/RUN_YOUR_OWN.md');
    expect(screen.getByText(/offered for non-commercial use/)).toBeTruthy();
    expect(screen.getByText(/full bundle.*not published yet/)).toBeTruthy();
  });
});
