/**
 * Help is organized around how a visitor meets the site (2026-10-19): six
 * groups, one Start here section that is the default, three merged sections
 * whose old ids still open the section they merged into, and Upload Your Text
 * moved to its own page.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import HelpPage, { HELP_SECTION_ALIASES, resolveHelpSection } from '../HelpPage';
import UploadTextPage from '../UploadTextPage';
import { pageForPath } from '../../../hooks/routePaths';
import { mockResponse } from '../../../test/mockResponse';

function serve() {
  global.fetch = vi.fn((url) => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(
    String(url).startsWith('/api/languages') ? { languages: [{ code: 'la' }, { code: 'ar' }] } : { stoplists: {} }) })));
}
afterEach(() => { delete global.fetch; });

describe('Help organization', () => {
  it('opens on Start here when no section is given', async () => {
    serve();
    render(<HelpPage />);
    expect(await screen.findByRole('heading', { name: 'Start here' })).toBeTruthy();
    expect(screen.getByText(/eight kinds of search/)).toBeTruthy();
  });

  it('shows the six groups in order', async () => {
    serve();
    const { container } = render(<HelpPage />);
    await screen.findByRole('heading', { name: 'Start here' });
    const groups = [...container.querySelectorAll('nav p')]
      .map((p) => p.textContent)
      .filter((t) => t !== 'Suggest a change');
    expect(groups.slice(0, 6)).toEqual([
      'Start here', 'Searching the literature', 'Reading',
      'People, Places & Things', 'Languages', 'Reference & tools'
    ]);
  });

  it('maps the three merged ids to their sections', () => {
    expect(HELP_SECTION_ALIASES).toEqual({
      'getting-started': 'start-here',
      'search-modes': 'start-here',
      'reading-results': 'results'
    });
    expect(resolveHelpSection('reading-results')).toBe('results');
    expect(resolveHelpSection('reader')).toBe('reader');
  });

  it.each([
    ['getting-started', 'Start here'],
    ['search-modes', 'Start here'],
    ['reading-results', 'Reading the results']
  ])('opens %s on its merged section', async (id, heading) => {
    serve();
    render(<HelpPage initialSection={id} />);
    expect(await screen.findByRole('heading', { name: heading })).toBeTruthy();
  });

  it('keeps a stub for Upload Your Text that links to the page', async () => {
    serve();
    render(<HelpPage initialSection="upload-text" />);
    const link = await screen.findByRole('link', { name: 'Open Upload Your Text' });
    expect(link.getAttribute('href')).toBe('/upload-help');
  });
});

describe('Upload Your Text page', () => {
  it('has the path /upload-help and renders the form', () => {
    expect(pageForPath('/upload-help')).toBe('upload-help');
    render(<UploadTextPage />);
    expect(screen.getByRole('heading', { name: 'Upload Your Text' })).toBeTruthy();
  });
});
