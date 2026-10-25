/**
 * A work divided into stories (the Shahnameh) gets a Stories list in the
 * Reader's header and story-by-story previous and next links; a work with no
 * structure shows neither (2026-10-24).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { clearTextStructureCache } from '../../hooks/useTextStructure';

vi.mock('../../hooks/useCorpus', () => {
  const useCorpus = () => ({
    loading: false,
    hierarchy: [
      { author: 'Ferdowsi', author_key: 'ferdowsi', works: [
        { work_key: 'shahnameh', work: 'Shahnameh',
          sections: [{ file: 'ferdowsi.shahnameh.tess', label: 'Shahnameh' }] }] },
      { author: 'Ovid', author_key: 'ovid', works: [
        { work_key: 'amores', work: 'Amores',
          sections: [{ file: 'ovid.amores.tess', label: 'Amores' }] }] },
    ],
  });
  return { default: useCorpus, useCorpus };
});

const STORIES = [
  { number: 1, title_en: 'Invocation', title_fa: 'آغاز کتاب', reign_fa: 'آغاز کتاب', first_ref: 'ferdowsi.shahnameh.1.1.1' },
  { number: 2, title_en: 'Wisdom', title_fa: 'ستایشِ خرد', reign_fa: 'آغاز کتاب', first_ref: 'ferdowsi.shahnameh.2.1.1' },
  { number: 3, title_en: 'Creation', title_fa: 'آفرینش', reign_fa: 'کیومرث', first_ref: 'ferdowsi.shahnameh.3.1.1' },
];

const reply = (obj, status = 200) => Promise.resolve({
  ok: status < 400, status, json: () => Promise.resolve(obj), text: () => Promise.resolve(JSON.stringify(obj)),
});

function mockFetch(structure) {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.startsWith('/api/texts/structure/')) {
      return structure ? reply(structure) : reply({ error: 'no structure' }, 404);
    }
    if (u.startsWith('/api/text/')) {
      const rows = structure?.sections || STORIES;
      return reply({ units: rows.map((s) => ({ ref: s.first_ref, text: `line ${s.number}` })), metadata: {} });
    }
    if (u.startsWith('/api/languages')) return reply({ languages: [{ code: 'fa' }] });
    return reply({});
  });
}

beforeEach(() => { clearTextStructureCache(); window.scrollTo = vi.fn(); });
afterEach(cleanup);

async function open(work, structure) {
  window.history.replaceState({}, '', `/read?work=${work}&lang=fa`);
  mockFetch(structure);
  const { default: ReaderPage } = await import('./ReaderPage');
  render(<ReaderPage />);
}

describe('ReaderPage stories', () => {
  it('lists the stories, says how many, and steps through them', async () => {
    await open('ferdowsi.shahnameh.tess', { work: 'ferdowsi.shahnameh', unit: 'story', sections: STORIES });
    await waitFor(() => expect(screen.getAllByLabelText('Stories').length).toBeGreaterThan(0));
    expect(screen.getByText('3 stories')).toBeTruthy();
    expect(global.fetch).toHaveBeenCalledWith('/api/texts/structure/ferdowsi.shahnameh');
    // Previous is disabled at the start, next goes to story 2.
    const next = await screen.findAllByLabelText('Next story: 2 Wisdom');
    fireEvent.click(next[0]);
    await waitFor(() => expect(screen.getAllByLabelText('Next story: 3 Creation').length).toBeGreaterThan(0));
    expect(screen.getAllByLabelText('Previous story: 1 Invocation').length).toBeGreaterThan(0);
  });

  it('chooses a story from the list', async () => {
    await open('ferdowsi.shahnameh.tess', { work: 'ferdowsi.shahnameh', unit: 'story', sections: STORIES });
    const box = (await screen.findAllByRole('combobox', { name: 'Stories' }))[0];
    fireEvent.focus(box);
    // The list shows the reign as a heading and the Persian title after the English.
    expect(screen.getAllByText('کیومرث').length).toBeGreaterThan(0);
    const opt = screen.getAllByRole('option', { name: '3 Creation · آفرینش' }).find((e) => e.tagName === 'BUTTON');
    fireEvent.pointerDown(opt);
    await waitFor(() => expect(screen.getAllByLabelText('Previous story: 2 Wisdom').length).toBeGreaterThan(0));
  });

  it('shows nothing for a work with no structure (404)', async () => {
    await open('ovid.amores.tess', null);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/texts/structure/ovid.amores'));
    await waitFor(() => expect(screen.getAllByText(/line 1/).length).toBeGreaterThan(0));
    expect(screen.queryAllByLabelText('Stories')).toHaveLength(0);
    expect(screen.queryByLabelText(/story/i)).toBeNull();
    expect(screen.queryByText(/stories/)).toBeNull();
  });

  describe('sections of a Persian or Urdu work', () => {
    const MASNAVI = [
      { number: 1, title_fa: 'بخش ۱ - سرآغاز', reign_fa: 'دفتر اول', first_ref: 'ferdowsi.shahnameh.1.1.1' },
      { number: 2, title_fa: 'بخش ۲ - عاشق شدن', reign_fa: 'دفتر اول', first_ref: 'ferdowsi.shahnameh.1.35.1' },
      { number: 3, title_fa: 'بخش ۱ - آغاز', reign_fa: 'دفتر دوم', first_ref: 'ferdowsi.shahnameh.2.1.1' },
    ];
    const BAGH = [
      { number: 1, title_fa: 'آغاز', n_units: 9, first_ref: 'ferdowsi.shahnameh.1.1' },
      { number: 2, title_fa: 'سبب تالیف کتاب', n_units: 7, first_ref: 'ferdowsi.shahnameh.2.1' },
    ];

    it('counts sections, lists the Persian title alone under its daftar, and steps by number', async () => {
      await open('ferdowsi.shahnameh.tess', { work: 'ferdowsi.shahnameh', unit: 'section', sections: MASNAVI });
      await waitFor(() => expect(screen.getAllByLabelText('Sections').length).toBeGreaterThan(0));
      expect(screen.getByText('3 sections')).toBeTruthy();
      const box = (await screen.findAllByRole('combobox', { name: 'Sections' }))[0];
      fireEvent.focus(box);
      expect(screen.getAllByText('دفتر دوم').length).toBeGreaterThan(0);
      // No English title and no stray separator: "3 · title".
      const opt = screen.getAllByRole('option', { name: '3 \u00b7 بخش ۱ - آغاز' }).find((e) => e.tagName === 'BUTTON');
      expect(opt).toBeTruthy();
      fireEvent.pointerDown(opt);
      await waitFor(() => expect(screen.getAllByLabelText('Previous story: 2').length).toBeGreaterThan(0));
    });

    it('steps through a prose work whose refs have two numbers', async () => {
      await open('ferdowsi.shahnameh.tess', { work: 'ferdowsi.shahnameh', unit: 'section', sections: BAGH });
      await waitFor(() => expect(screen.getByText('2 sections')).toBeTruthy());
      const next = await screen.findAllByLabelText('Next story: 2');
      fireEvent.click(next[0]);
      await waitFor(() => expect(screen.getAllByLabelText('Previous story: 1').length).toBeGreaterThan(0));
    });
  });
});
