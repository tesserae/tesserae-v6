/**
 * The header's dropdowns have to actually change something.
 *
 * NC reloaded the Reader and reported "the dropdowns are all frozen". They
 * rendered with the right values, and every argument I made from the data said
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

describe('the dropdowns reflect the open text', () => {
  it('shows the author, work and book of the work that is open', () => {
    mount();
    expect(screen.getByLabelText('Author').value).toBe('ovid');
    expect(screen.getByLabelText('Work').value).toBe('tristia');
    expect(screen.getByLabelText('Book').value).toBe('ovid.tristia.part.3.tess');
  });

  it('offers every author, not only the current one', () => {
    mount();
    const opts = [...screen.getByLabelText('Author').options].map((o) => o.value);
    expect(opts).toContain('ovid');
    expect(opts).toContain('vergil');
  });
});

describe('the dropdowns actually change something', () => {
  it('choosing another author opens that author', () => {
    const { onWork } = mount();
    fireEvent.change(screen.getByLabelText('Author'), { target: { value: 'vergil' } });
    expect(onWork).toHaveBeenCalledWith('vergil.aeneid.tess');
  });

  it('choosing another work opens that work', () => {
    const { onWork } = mount();
    fireEvent.change(screen.getByLabelText('Work'), { target: { value: 'amores' } });
    expect(onWork).toHaveBeenCalledWith('ovid.amores.tess');
  });

  it('choosing another book opens that book', () => {
    const { onWork } = mount();
    fireEvent.change(screen.getByLabelText('Book'), {
      target: { value: 'ovid.tristia.part.4.tess' } });
    expect(onWork).toHaveBeenCalledWith('ovid.tristia.part.4.tess');
  });

  it('choosing another language changes the language', async () => {
    const { onLanguage } = mount();
    const sel = await screen.findByLabelText('Language');
    fireEvent.change(sel, { target: { value: 'grc' } });
    expect(onLanguage).toHaveBeenCalledWith('grc');
  });
});

describe('a work with no books shows no Book control', () => {
  it('hides it rather than showing a dead one', () => {
    mount({ work: 'ovid.amores.tess' });
    expect(screen.queryByLabelText('Book')).toBeNull();
  });
});
