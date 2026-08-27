/**
 * The Verbal Parallels tab.
 *
 * It sat on the words "Wiring in progress" from the day the Reader shipped,
 * and NC found it by opening the tab. These tests cover the two things that
 * were easy to get wrong when wiring it up: the query is the SELECTED lines
 * rather than the whole work, and a line must not be returned as a parallel to
 * itself.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const UNITS = [
  { ref: 'verg. aen. 6.1', text: 'Sic fatur lacrimans, classique immittit habenas,' },
  { ref: 'verg. aen. 6.2', text: 'et tandem Euboicis Cumarum adlabitur oris.' },
  { ref: 'verg. aen. 6.3', text: 'Obvertunt pelago proras; tum dente tenaci' },
];

// One real hit, and the source line coming back as a match for itself.
const HITS = {
  results: [
    {
      author: 'Caesar', work: 'De Bello Civili', text_id: 'caesar.de_bello_civili.tess',
      locus: '3.101.2', year: -44, matched_words: ['classem', 'immisit'],
      text: 'in Pomponianam classem immisit atque omnes naves incendit',
    },
    // The source line coming back as its own parallel. Note the text_id: the
    // Reader has "vergil.aeneid.part.6.tess" open, but the search index holds
    // the whole poem, so this is the shape the live endpoint really returns.
    {
      author: 'Vergil', work: 'Aeneid', text_id: 'vergil.aeneid.tess',
      locus: '6.1', year: -19, matched_words: ['fatur', 'classique', 'immittit'],
      text: 'Sic fatur lacrimans, classique immittit habenas,',
    },
  ],
};

let sent;

function mount(props = {}) {
  const onOpenPassage = vi.fn();
  render(
    <ResultsPanel
      selection={{ refStart: 'verg. aen. 6.1', refEnd: 'verg. aen. 6.1',
                   startIdx: 0, endIdx: 0 }}
      language="la"
      work="vergil.aeneid.part.6.tess"
      units={UNITS}
      onOpenPassage={onOpenPassage}
      initialTab="verbal"
      {...props}
    />
  );
  return { onOpenPassage };
}

beforeEach(() => {
  sent = null;
  global.fetch = vi.fn((url, opts) => {
    sent = { url, body: JSON.parse(opts?.body || '{}') };
    return Promise.resolve({ json: () => Promise.resolve(HITS) });
  });
});

describe('the tab searches the corpus for the selection', () => {
  it('sends the selected line, not the whole work', async () => {
    mount();
    await waitFor(() => expect(sent).toBeTruthy());
    expect(sent.url).toBe('/api/line-search');
    expect(sent.body.query).toBe(UNITS[0].text);
    expect(sent.body.query).not.toContain('Obvertunt');
    expect(sent.body.language).toBe('la');
  });

  it('sends a multi-line selection whole', async () => {
    mount({ selection: { refStart: 'verg. aen. 6.1', refEnd: 'verg. aen. 6.2',
                         startIdx: 0, endIdx: 1 } });
    await waitFor(() => expect(sent).toBeTruthy());
    expect(sent.body.query).toContain('Sic fatur');
    expect(sent.body.query).toContain('adlabitur oris');
    expect(sent.body.query).not.toContain('Obvertunt');
  });

  it('shows the match, and the words it matched on', async () => {
    mount();
    expect(await screen.findByText(/Caesar, De Bello Civili/)).toBeTruthy();
    // A lemma search, so the shared words are in different forms on each side
    // and naming them is the whole point of the card.
    expect(screen.getByText('classem')).toBeTruthy();
    expect(screen.getByText('immisit')).toBeTruthy();
  });

  it('says the cards open, since nothing else does', async () => {
    mount();
    expect((await screen.findAllByText(/Open in Reader/))[0]).toBeTruthy();
  });
});

describe('a line is not a parallel to itself', () => {
  it('drops the source line even though the index names the whole poem', async () => {
    mount();
    await screen.findByText(/Caesar/);
    // This is the case that actually shipped broken. The Reader has book 6
    // open as vergil.aeneid.part.6.tess, the index returns the hit against
    // vergil.aeneid.tess, and compared as plain strings the two never matched,
    // so Aeneid 6.1 was listed as a verbal parallel to itself.
    expect(screen.queryByText(/Vergil, Aeneid/)).toBeNull();
  });

  it('asks the backend to exclude the work under the name the index uses', async () => {
    mount();
    await waitFor(() => expect(sent).toBeTruthy());
    expect(sent.body.exclude_text_id).toBe('vergil.aeneid.tess');
    expect(sent.body.exclude_locus).toBe('6.1');
  });

  it('keeps other lines of the same work', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({
      results: [{ author: 'Vergil', work: 'Aeneid',
                  text_id: 'vergil.aeneid.tess', locus: '2.100',
                  year: -19, matched_words: ['habena'], text: 'elsewhere in the poem' }],
    }) }));
    mount();
    // Reading Aeneid 6.1, a reader should still be told when Aeneid 2 uses the
    // same words. Matching on the work alone would have hidden it.
    expect(await screen.findByText(/Vergil, Aeneid/)).toBeTruthy();
  });
});

describe('when the corpus has nothing', () => {
  it('says why rather than showing an empty panel', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ results: [] }) }));
    mount();
    expect(await screen.findByText(/No other passage in the corpus/)).toBeTruthy();
  });
});
