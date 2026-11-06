/**
 * Help links the pages and sections it names (2026-10-28), so a reader can follow a mention.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HelpPage from '../HelpPage';
import { mockResponse } from '../../../test/mockResponse';

function serve() {
  global.fetch = vi.fn((url) => Promise.resolve(mockResponse({ ok: true, json: () => Promise.resolve(
    String(url).startsWith('/api/languages') ? { languages: [{ code: 'la' }] } : { stoplists: {} }) })));
}
afterEach(() => { delete global.fetch; });

function question(heading) {
  return screen.getByRole('heading', { name: heading }).parentElement;
}

describe('Help: links to the pages it names', () => {
  it('links Text Credits and Provenance and Upload Your Text in the Questions section', async () => {
    serve();
    const user = userEvent.setup();
    render(<HelpPage initialSection="faq" onSectionConsumed={() => {}} />);
    await screen.findByRole('heading', { name: 'Frequently Asked Questions' });
    const credits = within(question(/Where do the texts come from/)).getByRole('link', { name: 'Text Credits and Provenance' });
    expect(credits.getAttribute('href')).toBe('/text-credits');
    const upload = within(question('Can I add my own text to Tesserae?')).getByRole('link', { name: 'Upload Your Text' });
    expect(upload.getAttribute('href')).toBe('/upload-help');
    // A section mention is a button that opens that section.
    await user.click(within(question('Does Tesserae take meter into account?')).getByRole('button', { name: 'Search Settings' }));
    expect(await screen.findByRole('heading', { name: 'Search Settings' })).toBeTruthy();
  });
});
