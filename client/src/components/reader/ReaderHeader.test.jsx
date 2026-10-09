/**
 * The header's dropdowns have to actually change something.
 *
 * The Reader's dropdowns appeared frozen after a reload. They
 * rendered with the right values, and every argument made from the data said
 * they should work, so the only way to settle it was to mount the thing and
 * fire a change at it.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ReaderHeader from './ReaderHeader';

// Two authors, one with books, shaped exactly as useCorpus builds it.
const HIERARCHY = [
  {
    author: 'Ovid', author_key: 'ovid',
    works: [
      { work_key: 'amores', work: 'Amores',
        sections: [{ file: 'ovid.amores.tess', label: 'Amores' }] },
      { work_key: 'tristia', work: 'Tristia',
        sections: [
          { file: 'ovid.tristia.tess', label: 'Tristia' },
          { file: 'ovid.tristia.part.3.tess', label: 'Book 3' },
          { file: 'ovid.tristia.part.4.tess', label: 'Book 4' },
        ] },
    ],
  },
  {
    author: 'Vergil', author_key: 'vergil',
    works: [
      { work_key: 'aeneid', work: 'Aeneid',
        sections: [
          { file: 'vergil.aeneid.tess', label: 'Aeneid' },
          { file: 'vergil.aeneid.part.6.tess', label: 'Book 6' },
        ] },
    ],
  },
];

function mount(props = {}) {
  const onWork = vi.fn();
  const onLanguage = vi.fn();
  render(
    <ReaderHeader
      language="la"
      onLanguage={onLanguage}
      hierarchy={HIERARCHY}
      work="ovid.tristia.part.3.tess"
      onWork={onWork}
      metadata={{ display_name: 'Ovid, Tristia, Book 3' }}
      units={[{ ref: 'ov. tr. 3.1' }]}
      selection={null}
      {...props}
    />
  );
  return { onWork, onLanguage };
}

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({ json: () => Promise.resolve({ languages: [
      { code: 'la' }, { code: 'grc' }, { code: 'en' }] }) }));
});

// Author/Work/Book are now SearchableSelect (type-to-find), not a plain
// <select>: the visible control is a text input showing the chosen option's
// LABEL (not its raw value/key), and a `fireEvent.change` on it only types a
// filter rather than choosing anything. `chooseOption` drives it the way a
// user does -- focus to open the full list, then click the option carrying
// the given value (exposed as `data-value` on each option button precisely
// so tests can find it without matching on label text) -- and `optionValues`
// reads back what the open list currently offers.
function chooseOption(labelText, value) {
  fireEvent.focus(screen.getByLabelText(labelText));
  const option = screen.getAllByRole('option').find((o) => o.dataset.value === value);
  fireEvent.pointerDown(option);
}

function optionValues(labelText) {
  fireEvent.focus(screen.getByLabelText(labelText));
  return screen.getAllByRole('option')
    .filter((o) => o.dataset.value !== undefined)
    .map((o) => o.dataset.value);
}

describe('the dropdowns reflect the open text', () => {
  it('shows the author, work and book of the work that is open', () => {
    mount();
    expect(screen.getByLabelText('Author').value).toBe('Ovid');
    expect(screen.getByLabelText('Work').value).toBe('Tristia');
    expect(screen.getByLabelText('Book').value).toBe('Book 3');
  });

  it('offers every author, not only the current one', () => {
    mount();
    const opts = optionValues('Author');
    expect(opts).toContain('ovid');
    expect(opts).toContain('vergil');
  });
});

describe('the dropdowns actually change something', () => {
  it('choosing another author opens that author', () => {
    const { onWork } = mount();
    chooseOption('Author', 'vergil');
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.tess');
  });

  it('choosing another work opens that work', () => {
    const { onWork } = mount();
    chooseOption('Work', 'amores');
    expect(onWork).toHaveBeenCalledWith('ovid.amores.tess');
  });

  it('choosing another book opens that book', () => {
    const { onWork } = mount();
    chooseOption('Book', 'ovid.tristia.part.4.tess');
    expect(onWork).toHaveBeenCalledWith('ovid.tristia.part.4.tess');
  });

  it('choosing another language changes the language', async () => {
    const { onLanguage } = mount();
    const sel = await screen.findByLabelText('Language');
    fireEvent.change(sel, { target: { value: 'grc' } });
    expect(onLanguage).toHaveBeenCalledWith('grc');
  });

  it('labels a served Hebrew option "Hebrew", not the raw code (code review 2026-09-21, finding 3)', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ languages: [
        { code: 'la' }, { code: 'grc' }, { code: 'en' }, { code: 'he' }] }) }));
    mount();
    const sel = await screen.findByLabelText('Language');
    const heOption = [...sel.options].find((o) => o.value === 'he');
    expect(heOption).toBeTruthy();
    expect(heOption.textContent).toBe('Hebrew');
  });
});

describe('a work with no books shows no Book control', () => {
  it('hides it rather than showing a dead one', () => {
    mount({ work: 'ovid.amores.tess' });
    expect(screen.queryByLabelText('Book')).toBeNull();
  });
});

describe('the header does not repeat itself', () => {
  it('names the text once, in the dropdowns', () => {
    // It also printed metadata.display_name, so the header read
    // "Vergil | Aeneid | Book 6 ... Vergil, Aeneid, Book 6".
    mount();
    expect(screen.queryByText('Ovid, Tristia, Book 3')).toBeNull();
  });

  it('shows the position, which the dropdowns cannot, as a readable citation', () => {
    mount({ selection: { refStart: 'ov. tr. 3.1', refEnd: 'ov. tr. 3.4' } });
    // Not the raw ref ("ov. tr. 3.1"): the static Latin table resolves the
    // author (and would resolve the work too, from a fuller abbreviation).
    expect(screen.queryByText(/ov\. tr\. 3\.1/)).toBeNull();
    expect(screen.getByText('Ovid 3.1–4')).toBeTruthy();
  });

  it('falls back to the line count with nothing selected', () => {
    mount({ units: [{ ref: 'a' }, { ref: 'b' }] });
    expect(screen.getByText('2 lines')).toBeTruthy();
  });
});

describe('a selection in a language with no static abbreviation table', () => {
  // Owner review of the Reader on Iqbal's Asrar-e Khudi (2026-10-08): the
  // header printed the raw site id ("iqbal.asrar_e_khudi.1.1-5") for
  // Persian and Urdu, because only Latin/Greek/English have a static
  // table -- everything else needs the corpus list's own author/title
  // (what /api/texts?language=<lang> already carries, and what the result
  // cards already resolve raw ids against).
  it('resolves a Persian selection against the corpus text map, not the raw id', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/texts')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([
          { id: 'iqbal.asrar_e_khudi.tess', author: 'Iqbal', title: 'Asrar-e Khudi' },
        ]) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ languages: [{ code: 'fa' }] }) });
    });
    mount({
      language: 'fa',
      hierarchy: [],
      work: 'iqbal.asrar_e_khudi.tess',
      selection: { refStart: 'iqbal.asrar_e_khudi.1.1', refEnd: 'iqbal.asrar_e_khudi.1.5' },
    });
    expect(await screen.findByText('Iqbal, Asrar-e Khudi 1.1–5')).toBeTruthy();
    expect(screen.queryByText(/iqbal\.asrar_e_khudi\.1\.1/)).toBeNull();
  });
});

describe('a restricted text (data/restricted_texts.json)', () => {
  it('shows the licence credit line beneath the header', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/text-descriptions')) {
        return Promise.resolve({ json: () => Promise.resolve({
          description: 'An orientation blurb.',
          restricted: true,
          credit: 'Source: Test Licence Holder (example.invalid)',
        }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({ languages: [{ code: 'la' }] }) });
    });
    mount();
    expect(await screen.findByText('Source: Test Licence Holder (example.invalid)'))
      .toBeInTheDocument();
  });

  it('shows no credit line for an ordinary text', async () => {
    global.fetch = vi.fn((url) => {
      if (String(url).includes('/api/text-descriptions')) {
        return Promise.resolve({ json: () => Promise.resolve({ description: 'A blurb.' }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({ languages: [{ code: 'la' }] }) });
    });
    mount();
    await screen.findByLabelText('About this text');
    expect(screen.queryByText(/^Source: /)).not.toBeInTheDocument();
  });
});

describe('the About panel facts column', () => {
  function mockFetch({ facts, translation } = {}) {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes('/api/text-descriptions')) {
        return Promise.resolve({ json: () => Promise.resolve({
          description: 'An orientation blurb.',
          ...(facts ? { facts } : {}),
        }) });
      }
      if (u.includes('/api/passages/translation-full')) {
        return Promise.resolve({ json: () => Promise.resolve(
          translation || { available: false, reason: 'none' }) });
      }
      return Promise.resolve({ json: () => Promise.resolve({ languages: [{ code: 'la' }] }) });
    });
  }

  // Author/work names here are deliberately NOT "Ovid"/"Vergil"/"Tristia"/
  // "Aeneid": those already sit in HIERARCHY's hidden native <select>
  // options (rendered for phones regardless of viewport in a test
  // environment), so asserting on them would match two elements.
  it('lists the facts the server sent, and links to the filtered credits page', async () => {
    mockFetch({
      facts: {
        author: 'Seneca', work: 'Thyestes', part: 'Act 3', year: -19, era: 'Augustan',
        date_note: null, kind: 'poetry',
        edition: { print_source: 'Teubner, 1900', e_source: 'Perseus',
                   e_source_url: 'https://perseus.example/thyestes' },
      },
    });
    mount({ units: [{ ref: 'a' }, { ref: 'b' }, { ref: 'c' }] });
    fireEvent.click(await screen.findByLabelText('About this text'));

    expect(await screen.findByText('Seneca')).toBeInTheDocument();
    expect(screen.getByText('Thyestes, Act 3')).toBeInTheDocument();
    expect(screen.getByText('19 BCE')).toBeInTheDocument();
    expect(screen.getByText('Augustan')).toBeInTheDocument();
    expect(screen.getByText('Poetry')).toBeInTheDocument();
    // "3 lines" also appears in the header's own position indicator (top
    // right), unrelated to the facts row -- two matches is correct here.
    expect(screen.getAllByText('3 lines')).toHaveLength(2);
    expect(screen.getByText('Teubner, 1900')).toBeInTheDocument();
    const source = screen.getByRole('link', { name: 'Perseus' });
    expect(source).toHaveAttribute('href', 'https://perseus.example/thyestes');

    const credits = screen.getByRole('link', { name: 'Full credits' });
    expect(credits).toHaveAttribute('href', '/text-credits?author=Seneca');
  });

  it('omits a row with no data rather than showing it blank', async () => {
    mockFetch({ facts: { author: 'Anonymous', work: null, year: null, era: null, kind: null } });
    mount({ units: [] });
    fireEvent.click(await screen.findByLabelText('About this text'));

    expect(await screen.findByText('Anonymous')).toBeInTheDocument();
    expect(screen.queryByText('Work')).not.toBeInTheDocument();
    expect(screen.queryByText('Date')).not.toBeInTheDocument();
    expect(screen.queryByText('Era')).not.toBeInTheDocument();
    expect(screen.queryByText('Kind')).not.toBeInTheDocument();
    expect(screen.queryByText('Lines')).not.toBeInTheDocument();
  });

  it('drops the whole facts column, including the credits link, when there are no facts at all', async () => {
    mockFetch({});
    mount({ units: [] });
    fireEvent.click(await screen.findByLabelText('About this text'));

    await screen.findByText('An orientation blurb.');
    expect(screen.queryByText('Full credits')).not.toBeInTheDocument();
  });

  it('shows the attached translation\'s attribution once the panel is open', async () => {
    mockFetch({
      facts: { author: 'Seneca', work: 'Thyestes' },
      translation: { available: true, attribution: 'A. S. Kline (2003)' },
    });
    mount();
    fireEvent.click(await screen.findByLabelText('About this text'));

    expect(await screen.findByText('A. S. Kline (2003)')).toBeInTheDocument();
  });

  it('omits the Translation row when no aligned translation exists', async () => {
    mockFetch({ facts: { author: 'Seneca', work: 'Thyestes' },
                translation: { available: false, reason: 'none' } });
    mount();
    fireEvent.click(await screen.findByLabelText('About this text'));

    await screen.findByText('Seneca');
    expect(screen.queryByText('Translation')).not.toBeInTheDocument();
  });
});
