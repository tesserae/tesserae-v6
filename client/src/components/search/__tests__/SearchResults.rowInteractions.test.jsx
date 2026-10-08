import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Chart.js needs a real canvas, which jsdom does not provide. Stubbed the
// same way SearchResults.pagination.test.jsx stubs it, since this file
// renders the same component and would otherwise crash on mount.
vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef((_props, ref) =>
      createElement('button', { ref, 'data-testid': 'mock-chart-bar' }, 'chart bar')
    ),
  };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {},
  Title: {}, Tooltip: {}, Legend: {},
}));
vi.mock('../../../utils/api', () => ({
  searchTexts: vi.fn(),
  searchTextsStream: vi.fn(),
  searchFusionStream: vi.fn(),
  searchSemanticCross: vi.fn(),
  searchHapax: vi.fn(),
  searchBigrams: vi.fn(),
  wildcardSearch: vi.fn(),
}));

import SearchResults from '../SearchResults';

/** One row, with enough on it to exercise the menu and the expand toggle. */
const oneResult = () => [{
  source: { ref: 'a.src.1', text: 'the source line here', tokens: ['source'], highlight_indices: [0] },
  target: { ref: 'a.tgt.1', text: 'the target line here', tokens: ['target'], highlight_indices: [0] },
  source_text: 'the source line here',
  target_text: 'the target line here',
  matched_words: [{ lemma: 'lemma1', source_word: 'source', target_word: 'target' }],
  channels: ['lemma', 'exact', 'sound'],
  overall_score: 0.9,
  base_score: 0.9,
  features: {},
}];

const baseProps = {
  loading: false,
  error: null,
  pageSize: 50,
  onPageSizeChange: () => {},
  searchRunId: 1,
  sortBy: 'score',
  setSortBy: () => {},
  searchStats: null,
  language: 'la',
};

beforeEach(() => {
  vi.clearAllMocks();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
});

afterEach(() => {
  delete global.fetch;
});

describe('SearchResults — collapsed vs expanded row', () => {
  it('hides channel names on a collapsed row but shows the channel count', () => {
    render(<SearchResults {...baseProps} results={oneResult()} />);
    // The count badge (in the always-visible bar) is there from the start.
    expect(screen.getByText('3 channels')).toBeInTheDocument();
    // The per-channel name badges only appear once expanded.
    expect(screen.queryByText('lemma')).not.toBeInTheDocument();
    expect(screen.queryByText('exact')).not.toBeInTheDocument();
  });

  it('shows channel names and matched words once the row is clicked open', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} />);
    const row = screen.getByRole('button', { name: /the source line here/ });
    await userEvent.click(row);
    expect(screen.getByText('lemma')).toBeInTheDocument();
    expect(screen.getByText('exact')).toBeInTheDocument();
    expect(screen.getByText('sound')).toBeInTheDocument();
    expect(screen.getByText(/Matches:/)).toBeInTheDocument();
  });

  it('collapses again on a second click', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} />);
    const row = screen.getByRole('button', { name: /the source line here/ });
    await userEvent.click(row);
    expect(screen.getByText('lemma')).toBeInTheDocument();
    await userEvent.click(row);
    expect(screen.queryByText('lemma')).not.toBeInTheDocument();
  });

  it('toggles on Enter and Space when the row itself has focus', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} />);
    const row = screen.getByRole('button', { name: /the source line here/ });
    row.focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByText('lemma')).toBeInTheDocument();
    await userEvent.keyboard(' ');
    expect(screen.queryByText('lemma')).not.toBeInTheDocument();
  });

  it('clicking the row menu button does not also toggle the row expanded', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} onRegister={() => {}} />);
    const menuBtn = screen.getByRole('button', { name: 'More actions for this parallel' });
    await userEvent.click(menuBtn);
    // The menu opened (Register is visible)...
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
    // ...but the row itself did not expand: channel-name badges are still absent.
    expect(screen.queryByText('lemma')).not.toBeInTheDocument();
  });
});

describe('SearchResults — row menu', () => {
  it('is closed until the three-dot button is clicked, and lists the three actions', async () => {
    const onRegister = vi.fn();
    const onCorpusSearch = vi.fn();
    render(
      <SearchResults {...baseProps} results={oneResult()} onRegister={onRegister} onCorpusSearch={onCorpusSearch} />
    );
    expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'More actions for this parallel' }));

    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search Corpus' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cite' })).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} onRegister={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: 'More actions for this parallel' }));
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();
  });

  it('closes on a click outside the menu', async () => {
    render(<SearchResults {...baseProps} results={oneResult()} onRegister={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: 'More actions for this parallel' }));
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument();

    await userEvent.click(document.body);
    expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();
  });

  it('closes after Register is chosen, and calls the handler with the row', async () => {
    const onRegister = vi.fn();
    render(<SearchResults {...baseProps} results={oneResult()} onRegister={onRegister} />);
    await userEvent.click(screen.getByRole('button', { name: 'More actions for this parallel' }));
    await userEvent.click(screen.getByRole('button', { name: 'Register' }));

    expect(onRegister).toHaveBeenCalledTimes(1);
    expect(onRegister.mock.calls[0][0].source_text).toBe('the source line here');
    expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();
  });

  it('closes after Search Corpus is chosen, and calls the handler with the row', async () => {
    const onCorpusSearch = vi.fn();
    render(<SearchResults {...baseProps} results={oneResult()} onCorpusSearch={onCorpusSearch} />);
    await userEvent.click(screen.getByRole('button', { name: 'More actions for this parallel' }));
    await userEvent.click(screen.getByRole('button', { name: 'Search Corpus' }));

    expect(onCorpusSearch).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Search Corpus' })).not.toBeInTheDocument();
  });
});
