/**
 * The search page and Reader open in the language a reader chose last, or in
 * a fixed start language, kept in this browser (NC 2026-10-07).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Navigation from '../Navigation';
import { startLanguage, getStartSetting } from '../../../utils/languagePreference';

beforeEach(() => {
  window.localStorage.clear();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({
    languages: [{ code: 'la', label: 'Latin' }, { code: 'grc', label: 'Greek' }, { code: 'fa', label: 'Persian' }] }) }));
});
afterEach(() => { delete global.fetch; });

function renderNav(setActiveTab = () => {}) {
  render(<Navigation pageType="search" setPageType={() => {}} activeTab="la" setActiveTab={setActiveTab} />);
}

describe('remembering the language', () => {
  it('a language tab click is remembered for the next visit', async () => {
    const setActiveTab = vi.fn();
    renderNav(setActiveTab);
    fireEvent.click(await screen.findByRole('button', { name: 'Persian' }));
    expect(setActiveTab).toHaveBeenCalledWith('fa');
    expect(startLanguage()).toBe('fa');
  });

  it('"Open in" fixes a start language that later clicks do not change', async () => {
    renderNav();
    const select = screen.getByLabelText('Language the site opens in');
    await waitFor(() => expect(select.querySelectorAll('option').length).toBe(4));
    fireEvent.change(select, { target: { value: 'la' } });
    expect(getStartSetting()).toBe('la');
    fireEvent.click(screen.getByRole('button', { name: 'Persian' }));
    expect(startLanguage()).toBe('la');
    fireEvent.change(select, { target: { value: 'last' } });
    expect(startLanguage()).toBe('fa');
  });

  it('does not offer Cross-Language as a start language', async () => {
    renderNav();
    await screen.findByRole('button', { name: 'Persian' });
    const labels = [...screen.getByLabelText('Language the site opens in').options].map((o) => o.textContent);
    expect(labels).not.toContain('Cross-Language');
  });
});
