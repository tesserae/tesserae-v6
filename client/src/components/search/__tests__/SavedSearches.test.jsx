// The "Saved Searches (n)" button on the search page did nothing when clicked.
// SavedSearches renders <Modal onClose title> inside a showModal test, but
// Modal returns null unless it is given isOpen, so the dialog never appeared
// and no error was raised anywhere (found 2026-09-21, the same shape as the
// assistant mounted twice: a live control that quietly does nothing).
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SavedSearches from '../SavedSearches';

const SEARCH = {
  sourceAuthor: 'Vergil', sourceText: 'vergil.aeneid.part.1.tess',
  targetAuthor: 'Lucan', targetText: 'lucan.bellum_civile.part.1.tess',
  settings: {}, activeTab: 'latin', onLoad: () => {},
};

beforeEach(() => {
  localStorage.clear();
});

describe('the Saved Searches button', () => {
  it('opens the dialog when clicked', async () => {
    render(<SavedSearches {...SEARCH} />);
    await userEvent.click(screen.getByRole('button', { name: /Saved Searches/ }));
    expect(await screen.findByText('Save Current Search')).toBeTruthy();
  });

  it('shows nothing before it is clicked', () => {
    render(<SavedSearches {...SEARCH} />);
    expect(screen.queryByText('Save Current Search')).toBeNull();
  });
});
