/**
 * Changing a dropdown has to load a different text.
 *
 * NC: "I reloaded and the dropdowns are all frozen." ReaderHeader passes its own
 * tests, so if anything is frozen it is here, where the choice becomes a fetch.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const AUTHORS = [
  { name: 'Ovid', works: [
    { id: 'ovid.amores.tess', author_key: 'ovid', work_key: 'amores',
      work: 'Amores', title: 'Amores', is_part: false },
    { id: 'ovid.tristia.tess', author_key: 'ovid', work_key: 'tristia',
      work: 'Tristia', title: 'Tristia', is_part: false },
    { id: 'ovid.tristia.part.3.tess', author_key: 'ovid', work_key: 'tristia',
      work: 'Tristia', title: 'Tristia, Book 3', part: 'Book 3', is_part: true },
    { id: 'ovid.tristia.part.4.tess', author_key: 'ovid', work_key: 'tristia',
      work: 'Tristia', title: 'Tristia, Book 4', part: 'Book 4', is_part: true },
  ] },
  { name: 'Vergil', works: [
    { id: 'vergil.aeneid.tess', author_key: 'vergil', work_key: 'aeneid',
      work: 'Aeneid', title: 'Aeneid', is_part: false },
  ] },
];

// utils/api is deliberately NOT mocked: the first version of this file mocked
// it, so the real useCorpus never ran and the test could not have seen a bug in
// the hook that feeds the dropdowns. Only global.fetch is stubbed, which is the
// boundary the browser actually has.

// Everything the panel and gutter fetch is irrelevant here; only the text load
// matters, so record which work was asked for.
const asked = [];

beforeEach(() => {
  asked.length = 0;
  window.history.replaceState({}, '', '/read?work=ovid.tristia.part.3.tess&lang=la');
  // utils/api's jsonFetch reads response.TEXT and parses it, so a stub that
  // only offers json() makes every corpus call throw. That is a harness fault,
  // not a product one, and it cost a round of chasing the wrong thing.
  const reply = (obj) => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(obj),
    text: () => Promise.resolve(JSON.stringify(obj)),
  });
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/text/')) {
      asked.push(decodeURIComponent(u.slice('/api/text/'.length).split('?')[0]));
      return reply({
        units: [{ ref: 'ov. tr. 3.1', text: 'a line' }],
        metadata: { display_name: 'a text' },
      });
    }
    if (u.includes('/authors?')) {
      return reply(AUTHORS);
    }
    if (u.includes('/texts?')) {
      return reply([]);
    }
    if (u.startsWith('/api/languages')) {
      return reply({
        languages: [{ code: 'la' }, { code: 'grc' }] });
    }
    return reply({});
  });
});

afterEach(() => { vi.clearAllMocks(); });

async function mountReader() {
  const { default: ReaderPage } = await import('./ReaderPage');
  render(<ReaderPage />);
  await waitFor(() => expect(screen.getByLabelText('Author')).toBeTruthy());
}

describe('the Reader loads what the dropdowns choose', () => {
  it('opens the work named in the URL', async () => {
    await mountReader();
    await waitFor(() => expect(asked).toContain('ovid.tristia.part.3.tess'));
  });

  it('choosing another book loads that book', async () => {
    await mountReader();
    fireEvent.change(await screen.findByLabelText('Book'),
                     { target: { value: 'ovid.tristia.part.4.tess' } });
    await waitFor(() => expect(asked).toContain('ovid.tristia.part.4.tess'));
  });

  it('choosing another work loads that work', async () => {
    await mountReader();
    fireEvent.change(await screen.findByLabelText('Work'),
                     { target: { value: 'amores' } });
    await waitFor(() => expect(asked).toContain('ovid.amores.tess'));
  });

  it('choosing another author loads that author', async () => {
    await mountReader();
    fireEvent.change(await screen.findByLabelText('Author'),
                     { target: { value: 'vergil' } });
    await waitFor(() => expect(asked).toContain('vergil.aeneid.tess'));
  });

  it('the dropdown then SHOWS the text that is open', async () => {
    await mountReader();
    fireEvent.change(await screen.findByLabelText('Book'),
                     { target: { value: 'ovid.tristia.part.4.tess' } });
    await waitFor(() =>
      expect(screen.getByLabelText('Book').value).toBe('ovid.tristia.part.4.tess'));
  });
});

describe('arriving from Theme Search, which is how NC hit it', () => {
  const FROM_THEME =
    '/read?work=ovid.tristia.part.3.tess&lang=la'
    + '&ref=' + encodeURIComponent('ov. tr. 3.1')
    + '&refEnd=' + encodeURIComponent('ov. tr. 3.1')
    + '&tab=translation&q=' + encodeURIComponent('extremes of nature');

  it('still lets the dropdowns change the text', async () => {
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    fireEvent.change(await screen.findByLabelText('Book'),
                     { target: { value: 'ovid.tristia.part.4.tess' } });
    await waitFor(() => expect(asked).toContain('ovid.tristia.part.4.tess'));
  });

  it('does not re-fetch the same text over and over', async () => {
    // A render loop would peg the browser and read as "everything is frozen".
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    await new Promise((r) => setTimeout(r, 400));
    const first = asked.filter((w) => w === 'ovid.tristia.part.3.tess').length;
    await new Promise((r) => setTimeout(r, 400));
    const second = asked.filter((w) => w === 'ovid.tristia.part.3.tess').length;
    expect(second).toBe(first);
    expect(second).toBeLessThan(4);
  });
});

describe('the arrival banner is one-shot', () => {
  const FROM_THEME =
    '/read?work=ovid.tristia.part.3.tess&lang=la'
    + '&ref=' + encodeURIComponent('ov. tr. 3.1')
    + '&tab=translation&q=' + encodeURIComponent('extremes of nature');

  it('shows on arrival', async () => {
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    expect(await screen.findByText(/Found by Theme Search/)).toBeTruthy();
  });

  it('is dropped from the URL, so a reload does not resurrect it', async () => {
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    await waitFor(() => {
      const p = new URLSearchParams(window.location.search);
      expect(p.get('q')).toBeNull();
      expect(p.get('ref')).toBeNull();
      expect(p.get('tab')).toBeNull();
    });
  });

  it('goes away when the reader opens a different work', async () => {
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    await screen.findByText(/Found by Theme Search/);
    fireEvent.change(await screen.findByLabelText('Work'),
                     { target: { value: 'amores' } });
    await waitFor(() =>
      expect(screen.queryByText(/Found by Theme Search/)).toBeNull());
  });

  it('keeps the position in the URL as `at`, which it can read back', async () => {
    window.history.replaceState({}, '', FROM_THEME);
    await mountReader();
    await waitFor(() =>
      expect(new URLSearchParams(window.location.search).get('at'))
        .toBe('ov. tr. 3.1'));
  });
});

describe('the side panel keeps its tabs', () => {
  it('shows all three tabs with nothing selected', async () => {
    window.history.replaceState({}, '', '/read?work=ovid.amores.tess&lang=la');
    await mountReader();
    for (const label of ['Similar Passages', 'Verbal Parallels', 'Translation']) {
      expect(await screen.findByRole('button', { name: label })).toBeTruthy();
    }
  });

  it('still explains what to do', async () => {
    window.history.replaceState({}, '', '/read?work=ovid.amores.tess&lang=la');
    await mountReader();
    expect(await screen.findByText(/Select a passage in the text/)).toBeTruthy();
  });
});
