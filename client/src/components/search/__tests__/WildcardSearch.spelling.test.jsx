import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-chartjs-2', () => ({ Bar: () => null }));
vi.mock('../../../utils/api', () => ({ wildcardSearch: vi.fn() }));

import WildcardSearch from '../WildcardSearch';
import { wildcardSearch } from '../../../utils/api';

const ROW = {
  ref: 'ghalib.1', reference: 'ghalib.1', author: 'Ghalib', title: 'Diwan', era: 'Mughal',
  year: 1850, is_poetry: true, text: 'text', highlighted_text: 'text',
  match_note: ['vowel marks ignored', 'separator variant matched'],
};

beforeEach(() => {
  wildcardSearch.mockReset();
  wildcardSearch.mockResolvedValue({
    results: [ROW], total_matches: 1, texts_searched: 1, total_texts: 1, search_time: 0.1,
    matching: { mode: 'variants', rules: 'string-fold-2', query: 'q', query_used: 'q' },
  });
});

describe('WildcardSearch spelling control', () => {
  it('offers Match spelling variants and Exact spelling for Urdu instead of Case sensitive', () => {
    render(<WildcardSearch language="ur" />);
    expect(screen.getByLabelText('Match spelling variants')).toBeChecked();
    expect(screen.getByLabelText('Exact spelling')).not.toBeChecked();
    expect(screen.queryByLabelText('Case sensitive')).toBeNull();
  });

  it('keeps Case sensitive for Latin and sends no spelling', async () => {
    render(<WildcardSearch language="la" />);
    expect(screen.getByLabelText('Case sensitive')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Enter search query...'), { target: { value: 'amor' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(wildcardSearch).toHaveBeenCalled());
    expect(wildcardSearch.mock.calls[0][0]).not.toHaveProperty('spelling');
  });

  it('sends spelling and shows the match note under the result', async () => {
    render(<WildcardSearch language="fa" />);
    fireEvent.change(screen.getByPlaceholderText('Enter search query...'), { target: { value: 'دل' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(wildcardSearch).toHaveBeenCalled());
    expect(wildcardSearch.mock.calls[0][0].spelling).toBe('variants');
    expect(await screen.findByText('vowel marks ignored, separator variant matched')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Exact spelling'));
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(wildcardSearch).toHaveBeenCalledTimes(2));
    expect(wildcardSearch.mock.calls[1][0].spelling).toBe('strict');
  });

  it('offers three choices for Hebrew and sends points', async () => {
    render(<WildcardSearch language="he" />);
    expect(screen.getByLabelText('Match spelling variants')).toBeChecked();
    expect(screen.getByLabelText('Vowel points kept')).not.toBeChecked();
    expect(screen.getByLabelText('Exact spelling')).not.toBeChecked();
    fireEvent.click(screen.getByLabelText('Vowel points kept'));
    fireEvent.change(screen.getByPlaceholderText('Enter search query...'), { target: { value: 'דָּבָר' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(wildcardSearch).toHaveBeenCalled());
    expect(wildcardSearch.mock.calls[0][0].spelling).toBe('points');
  });

  it('keeps two choices for Persian', () => {
    render(<WildcardSearch language="fa" />);
    expect(screen.queryByLabelText('Vowel points kept')).toBeNull();
  });
});
