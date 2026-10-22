import { describe, it, expect } from 'vitest';
import { moreCounts } from '../MentionsPage';

describe('moreCounts', () => {
  it('names adjective lines and documents for a place with no direct mention', () => {
    expect(moreCounts({ adjective_lines: 3, document_counts: { la: 6 } }))
      .toBe('named by its adjective in 3 lines · 6 inscriptions and papyri');
    expect(moreCounts({ adjective_lines: 1 })).toBe('named by its adjective in 1 line');
    expect(moreCounts({})).toBe('');
  });
});

describe('editorNoteParts', () => {
  it('splits the editor’s notes from the text of the stone', async () => {
    const { editorNoteParts } = await import('../../documents/documentDisplay');
    expect(editorNoteParts('〈:da un lato〉 / Pub(licum) Col(oniae)')).toEqual([
      { note: true, text: 'da un lato' }, { note: false, text: ' / Pub(licum) Col(oniae)' }]);
    expect(editorNoteParts('Felix Rusellis')).toEqual([{ note: false, text: 'Felix Rusellis' }]);
  });
});

describe('entryExtra', () => {
  it('sums the adjective names and passes the documents of an entry page', async () => {
    const { entryExtra, moreCounts } = await import('../MentionsPage');
    const d = { adjective_names: [{ count: 4 }], document_counts: { la: 4 } };
    expect(moreCounts(entryExtra(d))).toBe('named by its adjective in 4 lines · 4 inscriptions and papyri');
  });
});
