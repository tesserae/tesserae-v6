import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';
import { resetScholarshipLanguagesCache } from '../../utils/scholarshipLanguages';
import { setView, setCollection } from '../../collections/collectionsStore';

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
  .filter((t) => ['Similar', 'Reuse', 'Parallels', 'Documents', 'Scholarship', 'Translation', 'Coins'].includes(t));

describe('the Reader tabs follow the view', () => {
  it('Literature keeps Similar first', () => {
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    expect(tabLabels().slice(0, 3)).toEqual(['Similar', 'Reuse', 'Parallels']);
  });

  it('History puts Similar first, then Documents, and still opens on Similar', () => {
    setView('history');
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    const labels = tabLabels();
    expect(labels.slice(0, 2)).toEqual(['Similar', 'Documents']);
    expect(labels.slice(0, 3)).toEqual(['Similar', 'Documents', 'Coins']);
    expect(labels.indexOf('Reuse')).toBeGreaterThan(labels.indexOf('Coins'));
    expect(labels.indexOf('Parallels')).toBeGreaterThan(labels.indexOf('Reuse'));
    expect(screen.getAllByRole('button', { name: 'Similar' })[0].className).toMatch(/border-red-700/);
    expect(screen.getAllByRole('button', { name: 'Reuse' })[0].className).not.toMatch(/border-red-700/);
  });

  it('Literature puts Documents after Parallels when a documents collection is on', () => {
    setCollection('inscriptions', true);
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    expect(tabLabels().slice(0, 4)).toEqual(['Similar', 'Reuse', 'Parallels', 'Documents']);
  });

  it('hides Documents when both documents collections are off', () => {
    setCollection('inscriptions', false);
    setCollection('papyri', false);
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    expect(tabLabels()).not.toContain('Documents');
  });

  it('shows Documents when only Papyri is on', () => {
    setCollection('inscriptions', false);
    setCollection('papyri', true);
    render(<ResultsPanel selection={null} language="la" work="vergil.aeneid" units={UNITS} />);
    expect(tabLabels()).toContain('Documents');
  });
});
