import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SelectionToolbar, { wordOf, scopeFor } from './SelectionToolbar';
import { rescope } from '../../utils/sentences';

describe('wordOf', () => {
  it('returns a double-clicked word, shorn of punctuation', () => {
    expect(wordOf({ text: 'cano' })).toBe('cano');
    expect(wordOf({ text: 'cano.' })).toBe('cano');
    expect(wordOf({ text: '“virumque,”' })).toBe('virumque');
  });
  it('handles Greek and Hebrew', () => {
    expect(wordOf({ text: 'ἄειδε' })).toBe('ἄειδε');
    expect(wordOf({ text: 'בְּרֵאשִׁית' })).toBe('בְּרֵאשִׁית');
  });
  it('returns null for phrases, empty, and non-letters', () => {
    expect(wordOf({ text: 'arma virumque' })).toBe(null);
    expect(wordOf({ text: '' })).toBe(null);
    expect(wordOf({ text: '123' })).toBe(null);
    expect(wordOf(null)).toBe(null);
  });
});

describe('scopeFor', () => {
  it('seeds word for a single selected word', () => {
    expect(scopeFor({ lineCount: 1, text: 'cano' })).toBe('word');
  });
  it('seeds line for one or two lines, passage for three or more', () => {
    expect(scopeFor({ lineCount: 1, text: 'arma virumque cano' })).toBe('line');
    expect(scopeFor({ lineCount: 2, text: 'x y' })).toBe('line');
    expect(scopeFor({ lineCount: 3, text: 'x y z' })).toBe('passage');
    expect(scopeFor(null)).toBe('line');
  });
});

// Requests workflow (2026-10-08): "Suggest a correction" pre-fills the
// dialog from exactly the passage already selected.
describe('SelectionToolbar — Suggest a correction', () => {
  afterEach(() => { delete global.fetch; });

  const selection = { refStart: '1.1', refEnd: '1.1', lineCount: 1, text: 'arma virumque cano' };

  it('opens a dialog pre-filled with the work, ref and selected text', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) }));
    const user = userEvent.setup();
    render(
      <SelectionToolbar
        selection={selection}
        scope="line"
        onScope={() => {}}
        work="vergil.aeneid.part.1.tess"
        language="la"
        onAct={() => {}}
        onClose={() => {}}
      />
    );
    await user.click(screen.getByRole('button', { name: 'Suggest a correction' }));
    expect(screen.getByRole('dialog', { name: /suggest a correction/i })).toBeTruthy();
    expect(screen.getByText('vergil.aeneid.part.1')).toBeTruthy();
    expect(screen.getByText('arma virumque cano')).toBeTruthy();
    expect(screen.getByLabelText(/corrected text \(optional\)/i)).toBeTruthy();
  });
});

// Sentences inside a long prose unit (2026-10-11).
describe('SelectionToolbar - a sentence inside a prose unit', () => {
  const pad = ' et cetera quae ad rem pertinent'.repeat(6);
  const unit = `Prima sententia est haec${pad}. Secunda sententia est illa${pad}. Tertia sententia est ultima${pad}.`;
  const second = unit.slice(unit.indexOf('Secunda'), unit.indexOf(' Tertia'));
  const at = unit.indexOf('Secunda');
  const sentence = {
    refStart: 'Tac. Ann. 1.1', refEnd: 'Tac. Ann. 1.1', lineCount: 1,
    text: second, sentenceText: second,
    charStart: at, charEnd: at + second.length, sentenceCount: 1, sentenceTotal: 3, startSentence: 1,
  };
  const whole = { ...sentence, text: unit, charStart: null, charEnd: null, sentenceCount: 3 };
  const mount = (selection, scope, onScope = () => {}, onAct = () => {}) => render(
    <SelectionToolbar selection={selection} scope={scope} onScope={onScope}
                      work="tacitus.annales.part.1.tess" language="la"
                      onAct={onAct} onClose={() => {}} />,
  );

  it('offers Word, Sentence, Section and Passage', () => {
    mount(sentence, 'sentence');
    const names = screen.getAllByRole('button').map((b) => b.textContent);
    expect(names.slice(0, 4)).toEqual(['Word', 'Sentence', 'Section', 'Passage']);
    expect(screen.queryByRole('button', { name: 'Line' })).toBeNull();
  });

  it('keeps Line for a verse selection', () => {
    mount({ refStart: '1.1', refEnd: '1.1', lineCount: 1, text: 'arma virumque cano' }, 'line');
    expect(screen.getByRole('button', { name: 'Line' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Sentence' })).toBeNull();
  });

  it('defaults to Sentence for a sentence and Section for the whole unit', () => {
    expect(scopeFor(sentence)).toBe('sentence');
    expect(scopeFor(whole)).toBe('section');
    expect(scopeFor({ ...sentence, text: 'cano', sentenceText: sentence.text })).toBe('word');
  });

  it('says which sentence is selected', () => {
    mount(sentence, 'sentence');
    expect(screen.getByText(/sentence 2 selected/)).toBeTruthy();
  });

  it('every scope button refuses to wrap or shrink', () => {
    mount(sentence, 'sentence');
    for (const name of ['Word', 'Sentence', 'Section', 'Passage']) {
      expect(screen.getByRole('button', { name }).className).toMatch(/whitespace-nowrap shrink-0/);
    }
    expect(screen.getByRole('toolbar').className).toMatch(/flex-wrap/);
  });

  it('Section widens the selection to the unit and Sentence narrows it back', () => {
    const w = rescope(sentence, unit, 'section');
    expect(w.charStart).toBeNull();
    expect(w.text).toBe(unit);
    expect(w.startSentence).toBe(1);
    const n = rescope(w, unit, 'sentence');
    expect(n.charStart).toBe(at);
    expect(n.text).toBe(second);
    expect(rescope(sentence, unit, 'sentence')).toBe(sentence);
    expect(rescope({ ...sentence, lineCount: 2 }, unit, 'section').charStart).toBe(at);
  });

  it('the Sentence action opens Line Search on the sentence text', async () => {
    const assign = vi.fn();
    const original = window.location;
    delete window.location;
    window.location = { set href(v) { assign(v); }, get href() { return ''; }, search: '' };
    try {
      mount(sentence, 'sentence');
      await userEvent.setup().click(screen.getByRole('button', { name: 'Find shared wording' }));
      const url = new URL(assign.mock.calls[0][0], 'http://x');
      expect(url.pathname).toBe('/line-search');
      expect(url.searchParams.get('q')).toBe(second);
      expect(url.searchParams.get('type')).toBe('lemma');
      expect(url.searchParams.get('work')).toBe('tacitus.annales.part.1');
      expect(url.searchParams.get('language')).toBe('la');
    } finally {
      window.location = original;
    }
  });

  it('the Section action goes by reference, as a line does', async () => {
    const assign = vi.fn();
    const original = window.location;
    delete window.location;
    window.location = { set href(v) { assign(v); }, get href() { return ''; }, search: '' };
    try {
      mount(whole, 'section');
      await userEvent.setup().click(screen.getByRole('button', { name: 'Find shared wording' }));
      const url = new URL(assign.mock.calls[0][0], 'http://x');
      expect(url.searchParams.get('ref')).toBe('Tac. Ann. 1.1');
      expect(url.searchParams.get('q')).toBeNull();
    } finally {
      window.location = original;
    }
  });
});
