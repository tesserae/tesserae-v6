import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { SEARCH_SCOPE } from '../../data/searchScope';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }];

function mount(props = {}) {
  return render(
    <ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} {...props} />
  );
}

beforeEach(() => {
  resetScholarshipLanguagesCache();
  try { window.sessionStorage.clear(); window.localStorage.clear(); } catch { /* ignore */ }
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
});

afterEach(() => {
  delete global.fetch;
  window.history.replaceState({}, '', '/');
});

const lower = (t) => t.charAt(0).toLowerCase() + t.slice(1);

describe('the side panel with nothing selected', () => {
  it('lists each tab with its does line and emphasises the current tab', () => {
    const { container } = mount();
    const intro = container.querySelector('[data-testid="reader-scope-intro"]');
    const items = [...intro.querySelectorAll('li')];
    expect(items.length).toBeGreaterThanOrEqual(4);
    expect(items.length).toBeLessThanOrEqual(5);
    const similar = items.find((li) => li.textContent.startsWith('Similar'));
    expect(similar.textContent).toContain(lower(SEARCH_SCOPE.reader_similar.does));
    expect(similar.getAttribute('data-current')).toBe('true');
    expect(items.filter((li) => li.getAttribute('data-current') === 'true')).toHaveLength(1);
  });

  it('leaves out the Scholarship line when that tab is not offered, and shows the box for the current tab', () => {
    const { container } = mount();
    const intro = container.querySelector('[data-testid="reader-scope-intro"]');
    const hasScholarshipTab = !!screen.queryByRole('button', { name: 'Scholarship' });
    const hasLine = [...intro.querySelectorAll('li')].some((li) => li.textContent.startsWith('Scholarship'));
    expect(hasLine).toBe(hasScholarshipTab);
    expect(container.querySelector('[data-testid="scope-box-reader_similar"]')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Reuse' }));
    expect(container.querySelector('[data-testid="scope-box-reader_reuse"]')).toBeTruthy();
    const current = [...intro.querySelectorAll('li')].find((li) => li.getAttribute('data-current') === 'true');
    expect(current.textContent.startsWith('Reuse')).toBe(true);
  });
});

describe('the side panel with a selection', () => {
  it('toggles the box with the "What this does" link', () => {
    const { container } = mount({ selection: { start: 0, end: 0, text: 'Arma virumque cano' } });
    expect(container.querySelector('[data-testid="scope-box-reader_similar"]')).toBeNull();
    const link = screen.getByRole('button', { name: 'What this does' });
    fireEvent.click(link);
    expect(container.querySelector('[data-testid="scope-box-reader_similar"]')).toBeTruthy();
    expect(screen.getByText(/Your selection is matched by the model-written description/)).toBeTruthy();
    fireEvent.click(link);
    expect(container.querySelector('[data-testid="scope-box-reader_similar"]')).toBeNull();
  });
});
