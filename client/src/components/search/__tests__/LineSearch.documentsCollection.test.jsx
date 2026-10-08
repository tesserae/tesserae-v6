/**
 * Documents collection (stage 3b-2): the Literature/Documents/Both control
 * and the document hit card, behind /api/languages' documents_enabled.
 * With that flag false (the default in every other test in this file's
 * sibling suites, and in production until the server turns the switch on)
 * the control must not render at all, and nothing here changes a single
 * existing literary test.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));

import LineSearch from '../LineSearch';

const documentHit = {
  collection: 'documents',
  doc_id: 'edh:HD047322',
  locus: 'edh:HD047322',
  text: 'D M Aurelia',
  tokens: ['D', 'M', 'Aurelia'],
  matched_words: ['D', 'M'],
  matched_lemmas: ['d', 'manus'],
  restored_indices: [0],
  fragment_indices: [],
  credit: {
    licence_name: 'CC BY-SA 4.0',
    source_name: 'Epigraphic Database Heidelberg',
    source_url: 'https://edh.example.org/HD047322',
    principal_edition: 'AE 2001, 2169.',
  },
  date_not_before: 101, date_not_after: 300,
  ancient_place: null, modern_place: 'Rome', region: 'Roma',
  text_type_label: 'funerary inscription', object_type_label: 'stele', material_label: 'marble',
};

const literatureHit = {
  text_id: 'vergil.aeneid.tess', author: 'Vergil', work: 'Aeneid', locus: '1.1',
  text: 'arma virumque cano', era: 'Augustan', year: -19,
  is_poetry: true, matched_words: ['arma', 'virum'], matched_lemmas: ['arma', 'vir'],
};

function mockFetch({ documentsEnabled, results, trial = documentsEnabled }) {
  // The control is a trial behind ?documents=1, remembered for the visit.
  if (trial) window.sessionStorage.setItem('tesserae_documents_trial', '1');
  global.fetch = vi.fn(async (url, init) => {
    const u = String(url);
    if (u === '/api/languages') {
      return { json: async () => ({ languages: [{ code: 'la', label: 'Latin' }],
                                     crosslingual_pairs: [], documents_enabled: documentsEnabled }) };
    }
    if (u.startsWith('/api/texts')) {
      return { json: async () => ({ texts: [] }) };
    }
    if (u === '/api/line-search') {
      const body = init && init.body ? JSON.parse(init.body) : {};
      return { json: async () => ({ query: body.query, total: results.length, results }) };
    }
    return { json: async () => ({}) };
  });
}

beforeEach(() => {
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});
afterEach(() => { delete global.fetch; });

async function switchToSearchMode() {
  await userEvent.click(screen.getByRole('button', { name: 'Input Search Text' }));
}

describe('documents collection control', () => {
  it('is absent when documents_enabled is false', async () => {
    mockFetch({ documentsEnabled: false, results: [] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    expect(screen.queryByText('Search in')).toBeNull();
  });

  it('is absent without the ?documents=1 trial even when the server has documents on', async () => {
    mockFetch({ documentsEnabled: true, results: [], trial: false });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/languages'));
    expect(screen.queryByText('Search in')).toBeNull();
  });

  it('appears, and the filters stay hidden until Documents or Both is chosen', async () => {
    mockFetch({ documentsEnabled: true, results: [] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    expect(screen.queryByPlaceholderText('e.g., Latium')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    expect(screen.getByPlaceholderText('e.g., Latium')).toBeTruthy();
    expect(screen.getByPlaceholderText('e.g., epitaph')).toBeTruthy();
    expect(screen.getByPlaceholderText('e.g., marble')).toBeTruthy();
  });

  it('sends collection + filters once Documents is chosen and a filter is filled in', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('e.g., Latium'), 'Roma');
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([u]) => String(u) === '/api/line-search');
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body.collection).toBe('documents');
      expect(body.region).toBe('Roma');
    });
  });

  it('never sends collection when left on plain Literature, even with the control visible', async () => {
    mockFetch({ documentsEnabled: true, results: [literatureHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'arma virum');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([u]) => String(u) === '/api/line-search');
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body.collection).toBeUndefined();
    });
  });

  it('renders a document hit card with credit, date/place, labels, and a separate section from literary hits', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit, literatureHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Both' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    // Literary summary bar counts only the literary hit.
    await waitFor(() => expect(screen.getByText(/Found 1 parallel lines/)).toBeTruthy());
    // Document section is separate, with its own count.
    expect(screen.getByText(/Found 1 documents/)).toBeTruthy();
    // Credit line, linking to the source record.
    const link = screen.getByRole('link', { name: 'Epigraphic Database Heidelberg' });
    expect(link).toHaveAttribute('href', 'https://edh.example.org/HD047322');
    // Broader content checks via textContent (several ancestor elements
    // legitimately share this substring, which would make getByText's
    // "exactly one match" rule flaky here).
    const bodyText = document.body.textContent;
    expect(bodyText).toContain('CC BY-SA 4.0');
    expect(bodyText).toContain('AE 2001, 2169.');  // principal edition as the citation
    expect(bodyText).toMatch(/101 AD.*300 AD/);    // date range
    expect(bodyText).toContain('Rome');            // place
    // Labels (short, unique leaf spans).
    expect(screen.getByText('funerary inscription')).toBeTruthy();
    expect(screen.getByText('marble')).toBeTruthy();
  });

  it('marks a restored token with the dotted-underline style, not the matched-word <mark>', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    // Token 0 ("D") is both matched AND restored in the fixture: the <mark>
    // wraps a restored span carrying the dotted-underline class.
    const restored = document.querySelector('.decoration-dotted');
    expect(restored).toBeTruthy();
    expect(restored.textContent).toBe('D');
    expect(restored.closest('mark')).toBeTruthy();
  });
});

describe('stage 3b-3: restoration exclusion, formula hiding, and the document view link', () => {
  it('shows the restoration/formula checkboxes only once Documents or Both is chosen', async () => {
    mockFetch({ documentsEnabled: true, results: [] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    expect(screen.queryByText('Leave out matches on restored words')).toBeNull();
    expect(screen.queryByText('Hide stock formulas')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    expect(screen.getByText('Leave out matches on restored words')).toBeTruthy();
    expect(screen.getByText('Hide stock formulas')).toBeTruthy();
  });

  it('sends exclude_restored only when the checkbox is checked', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Leave out matches on restored words' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([u]) => String(u) === '/api/line-search');
      const body = JSON.parse(call[1].body);
      expect(body.exclude_restored).toBe(true);
    });
  });

  it('sends hide_formulas with the measured default only when the checkbox is checked', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Hide stock formulas' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([u]) => String(u) === '/api/line-search');
      const body = JSON.parse(call[1].body);
      expect(body.hide_formulas).toBe(100);
    });
  });

  it('neither checkbox sends anything when left unchecked', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => {
      const call = global.fetch.mock.calls.find(([u]) => String(u) === '/api/line-search');
      const body = JSON.parse(call[1].body);
      expect(body.exclude_restored).toBeUndefined();
      expect(body.hide_formulas).toBeUndefined();
    });
  });

  it('shows "match on restored text" only for a fully-restored hit', async () => {
    const fullyRestored = { ...documentHit, matched_restored: true };
    mockFetch({ documentsEnabled: true, results: [fullyRestored] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    expect(screen.getByText('match on restored text')).toBeTruthy();
  });

  it('does not show "match on restored text" for a hit that is not fully restored', async () => {
    const partial = { ...documentHit, matched_restored: false, partly_restored: true };
    mockFetch({ documentsEnabled: true, results: [partial] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    expect(screen.queryByText('match on restored text')).toBeNull();
  });

  it('the citation links to the document view with the query and language carried over', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit] });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    const link = screen.getByRole('link', { name: 'AE 2001, 2169.' });
    const href = link.getAttribute('href');
    expect(href.startsWith('/document?')).toBe(true);
    const params = new URLSearchParams(href.slice('/document?'.length));
    expect(params.get('doc')).toBe('edh:HD047322');
    expect(params.get('lang')).toBe('la');
    expect(params.get('q')).toBe('dis manibus');
    expect(params.get('type')).toBe('lemma');
  });

  it('carries the documents=1 trial flag on the document-view link when the trial is active', async () => {
    mockFetch({ documentsEnabled: true, results: [documentHit], trial: true });
    render(<LineSearch language="la" />);
    await switchToSearchMode();
    await waitFor(() => expect(screen.getByText('Search in')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: 'Documents' }));
    await userEvent.type(screen.getByPlaceholderText('Enter word or phrase...'), 'dis manibus');
    await userEvent.click(screen.getByRole('button', { name: 'Search Lines' }));

    await waitFor(() => expect(screen.getByText(/Found 1 documents/)).toBeTruthy());
    const link = screen.getByRole('link', { name: 'AE 2001, 2169.' });
    const params = new URLSearchParams(link.getAttribute('href').split('?')[1]);
    expect(params.get('documents')).toBe('1');
  });
});
