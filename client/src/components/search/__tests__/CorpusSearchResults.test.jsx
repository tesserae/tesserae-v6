import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import CorpusSearchResults from '../CorpusSearchResults';

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: async () => [] }));
});

// Search Corpus showed Persian and Urdu results with no highlighted words
// (result card tidy, second pass, 2026-10-08). The strip regexes covered
// only Latin/Greek punctuation, so a word carrying a trailing Arabic-script
// comma never matched the server's own token, and the word walk counted
// whitespace-split chunks rather than the server's own word-runs, which
// drift apart the moment a line carries a standalone punctuation mark.
// The owner's own example: a corpus-wide search on انداز
// (andaz) from the Hafez-Iqbal pair must highlight انداز
// in "باده انداز، کو سرود انداخت".

const BAADE = 'باده'; // باده
const ANDAZ = 'انداز'; // انداز
const KO = 'کو'; // کو
const SORUD = 'سرود'; // سرود
const ANDAKHT = 'انداخت'; // انداخت

describe('CorpusSearchResults — Persian/Urdu highlighting', () => {
  it('highlights the matched word even though it carries a trailing Arabic comma', () => {
    const text = `${BAADE} ${ANDAZ}، ${KO} ${SORUD} ${ANDAKHT}`;
    const results = [{
      text_id: 'hafez.diwan.tess',
      author: 'Hafez',
      title: 'Diwan',
      locus: '5097',
      citation: 'Hafez, Diwan 5097',
      text,
      matched_lemmas: [ANDAZ],
      // The server's own tokens exclude punctuation (backend/persian/
      // processor.py's tokenize_persian), so the comma is not a token.
      tokens: [BAADE, ANDAZ, KO, SORUD, ANDAKHT],
      highlight_indices: [1],
      year: 1300,
      era: 'Medieval',
      is_poetry: true,
    }];

    render(
      <CorpusSearchResults
        results={results}
        loading={false}
        error={null}
        query={null}
        onBack={() => {}}
        elapsedTime={0}
        language="fa"
      />
    );

    const mark = screen.getByText(ANDAZ, { selector: 'mark' });
    expect(mark).toBeInTheDocument();
    // The comma is not part of the highlighted run.
    expect(mark.textContent).toBe(ANDAZ);
    // Neighboring words stay unhighlighted: the word walk did not drift.
    expect(screen.queryByText(KO, { selector: 'mark' })).not.toBeInTheDocument();
    expect(screen.queryByText(SORUD, { selector: 'mark' })).not.toBeInTheDocument();
  });

  it('highlights a lemma-matched word (no server tokens) after folding Persian script variants', () => {
    // No `tokens`/`highlight_indices` on this result (a result predating
    // them, or the header's own query text), so the fallback lemma-based
    // highlighter must fold Persian ya/kaf and strip the trailing comma
    // itself before comparing.
    const text = `${BAADE} ${ANDAZ}، ${KO} ${SORUD} ${ANDAKHT}`;
    const results = [{
      text_id: 'hafez.diwan.tess',
      author: 'Hafez',
      title: 'Diwan',
      locus: '5097',
      citation: 'Hafez, Diwan 5097',
      text,
      matched_lemmas: [ANDAZ],
      tokens: [],
      highlight_indices: [],
      year: 1300,
      era: 'Medieval',
      is_poetry: true,
    }];

    render(
      <CorpusSearchResults
        results={results}
        loading={false}
        error={null}
        query={null}
        onBack={() => {}}
        elapsedTime={0}
        language="fa"
      />
    );

    const mark = screen.getByText(ANDAZ, { selector: 'mark' });
    expect(mark).toBeInTheDocument();
  });

  it('resolves the query header citation against the corpus text map rather than showing a raw id', () => {
    const query = {
      source: { ref: 'hafez.diwan.5097', text: ANDAZ, citation: '' },
      target: { ref: 'iqbal.zabur_e_ajam.26.1', text: ANDAZ, citation: '' },
      lemmas: [ANDAZ],
    };

    render(
      <CorpusSearchResults
        results={[]}
        loading={false}
        error={null}
        query={query}
        onBack={() => {}}
        elapsedTime={0}
        language="fa"
      />
    );

    // With no corpus text map loaded in this test, resolveDisplayCitation
    // falls back to the static expandLocus() table, which still title-cases
    // the id segments -- never the raw, lower-case dotted tag itself.
    expect(screen.queryByText(/hafez\.diwan\.5097/)).not.toBeInTheDocument();
    expect(screen.queryByText(/iqbal\.zabur_e_ajam\.26\.1/)).not.toBeInTheDocument();
  });
});
