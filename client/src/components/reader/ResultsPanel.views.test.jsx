import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { setView } from '../../collections/collectionsStore';

const UNITS = [{ ref: 'verg. aen. 1.1', text: 'Arma virumque cano' }];

beforeEach(() => {
  resetScholarshipLanguagesCache();
  window.localStorage.clear();
  window.sessionStorage.clear();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) }));
});
afterEach(() => { cleanup(); delete global.fetch; });

const tabLabels = () => screen.getAllByRole('button')
  .map((b) => b.textContent.trim())
  .filter((t) => ['Similar', 'Reuse', 'Parallels', 'Scholarship', 'Translation', 'Coins'].includes(t));

describe('the Reader tabs follow the view', () => {
  it('Literature keeps Similar first', () => {
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    expect(tabLabels().slice(0, 3)).toEqual(['Similar', 'Reuse', 'Parallels']);
  });

  it('History puts Reuse first and still opens on Similar', () => {
    setView('history');
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    const labels = tabLabels();
    expect(labels[0]).toBe('Reuse');
    expect(labels.indexOf('Similar')).toBeGreaterThan(labels.indexOf('Reuse'));
    expect(screen.getAllByRole('button', { name: 'Similar' })[0].className).toMatch(/border-red-700/);
    expect(screen.getAllByRole('button', { name: 'Reuse' })[0].className).not.toMatch(/border-red-700/);
  });
});
