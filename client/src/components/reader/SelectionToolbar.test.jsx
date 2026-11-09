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

// Dictionary lookup (2026-11-08): "Look up" beside "Find this word".
describe('SelectionToolbar - Look up', () => {
  afterEach(() => { delete global.fetch; });

  const word = { refStart: '1.1', refEnd: '1.1', lineCount: 1, text: 'arma' };
  const reply = (body, ok = true) => vi.fn(() => Promise.resolve({
    ok, status: ok ? 200 : 500, text: () => Promise.resolve(JSON.stringify(body)),
  }));
  const mount = (selection, scope = 'word') => render(
    <SelectionToolbar selection={selection} scope={scope} onScope={() => {}}
                      work="vergil.aeneid.part.1.tess" language="la"
                      onAct={() => {}} onClose={() => {}} />,
  );

  it('is offered for a single word, and for a line it offers the switch to Word', async () => {
    const { unmount } = mount(word);
    expect(screen.getByRole('button', { name: 'Look up' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Look up a word' })).toBeNull();
    unmount();
    const onScope = vi.fn();
    render(
      <SelectionToolbar selection={{ ...word, text: 'arma virumque cano' }} scope="line" onScope={onScope}
                        work="vergil.aeneid.part.1.tess" language="la" onAct={() => {}} onClose={() => {}} />,
    );
    expect(screen.queryByRole('button', { name: 'Look up' })).toBeNull();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up a word' }));
    expect(onScope).toHaveBeenCalledWith('word');
  });

  it('in Word scope with no word, the hint says a click looks a word up too', () => {
    mount({ ...word, text: 'arma virumque cano' }, 'word');
    expect(screen.getByText('click one word to search for it or look it up')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Look up a word' })).toBeTruthy();
  });

  it('uses the word under a plain click when no word was swept', async () => {
    global.fetch = reply({ lemma: 'cano', dictionary: 'Lewis and Short', definition: 'cano, to sing',
      url: 'https://logeion.uchicago.edu/cano' });
    mount({ ...word, text: 'arma virumque cano', clickedWord: 'cano' }, 'word');
    expect(screen.getByRole('button', { name: 'Find “cano” in the corpus' })).toBeTruthy();
    // In Word mode the clicked word's entry opens by itself.
    expect(await screen.findByText('cano, to sing')).toBeTruthy();
    expect(global.fetch.mock.calls[0][0]).toBe('/api/define?word=cano&language=la');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up' }));
    expect(screen.queryByText('cano, to sing')).toBeNull();
  });

  it('"Look up a word" opens the entry for the clicked word as soon as the scope is Word', async () => {
    global.fetch = reply({ lemma: 'deus', definition: 'deus, a god', url: 'https://x.test/deus' });
    const onScope = vi.fn();
    const sel = { ...word, text: '', clickedWord: 'deos' };
    const { rerender } = render(
      <SelectionToolbar selection={sel} scope="line" onScope={onScope}
                        work="vergil.aeneid.part.1.tess" language="la" onAct={() => {}} onClose={() => {}} />,
    );
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up a word' }));
    expect(onScope).toHaveBeenCalledWith('word');
    rerender(
      <SelectionToolbar selection={sel} scope="word" onScope={onScope}
                        work="vergil.aeneid.part.1.tess" language="la" onAct={() => {}} onClose={() => {}} />,
    );
    expect(await screen.findByText('deus, a god')).toBeTruthy();
  });

  it('in Word mode, a click on another word opens that word\'s entry at once', async () => {
    global.fetch = reply({ lemma: 'genus', definition: 'genus, birth', url: 'https://x.test/genus' });
    const first = { ...word, text: '', clickedWord: 'deos', clickedWordRange: [12, 16] };
    const { rerender } = render(
      <SelectionToolbar selection={first} scope="word" onScope={() => {}}
                        work="vergil.aeneid.part.1.tess" language="la" onAct={() => {}} onClose={() => {}} />,
    );
    rerender(
      <SelectionToolbar selection={{ ...first, clickedWord: 'genus', clickedWordRange: [24, 29] }} scope="word" onScope={() => {}}
                        work="vergil.aeneid.part.1.tess" language="la" onAct={() => {}} onClose={() => {}} />,
    );
    expect(await screen.findByText('genus, birth')).toBeTruthy();
    expect(global.fetch.mock.calls.at(-1)[0]).toBe('/api/define?word=genus&language=la');
  });

  it('names the enclitic taken off a Latin word', async () => {
    global.fetch = reply({ lemma: 'infero', enclitic: 'que', dictionary: 'Lewis and Short',
      definition: 'infero, to bring in', url: 'https://logeion.uchicago.edu/infero' });
    mount({ ...word, text: 'inferretque' });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByText('infero, to bring in')).toBeTruthy();
    expect(screen.getByText('inferretque with -que taken off')).toBeTruthy();
  });

  it('opens a popover with the lemma, dictionary, definition and full-entry link', async () => {
    global.fetch = reply({ lemma: 'arma', dictionary: 'Lewis and Short', definition: 'arma, orum, n. arms',
      url: 'https://logeion.uchicago.edu/arma' });
    mount(word);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByText('arma, orum, n. arms')).toBeTruthy();
    expect(screen.getByText('Lewis and Short')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Full entry' }).getAttribute('href'))
      .toBe('https://logeion.uchicago.edu/arma');
    expect(global.fetch.mock.calls[0][0]).toBe('/api/define?word=arma&language=la');
  });

  it('says No entry found and keeps the link when there is no definition', async () => {
    global.fetch = reply({ lemma: 'arma', dictionary: null, definition: null, url: 'https://x.test/arma' });
    mount(word);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Look up' }));
    expect(await screen.findByText('No entry found')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Full entry' })).toBeTruthy();
  });

  it('closes on Escape, on a click outside and on a new selection', async () => {
    global.fetch = reply({ lemma: 'arma', definition: 'arms', url: 'https://x.test/arma' });
    const user = userEvent.setup();
    const { rerender } = mount(word);
    const open = async () => {
      await user.click(screen.getByRole('button', { name: 'Look up' }));
      await screen.findByText('arms');
    };
    await open();
    await user.keyboard('{Escape}');
    expect(screen.queryByText('arms')).toBeNull();
    await open();
    await user.click(document.body);
    expect(screen.queryByText('arms')).toBeNull();
    await open();
    rerender(
      <SelectionToolbar selection={{ ...word, text: 'virum' }} scope="word" onScope={() => {}}
                        work="vergil.aeneid.part.1.tess" language="la"
                        onAct={() => {}} onClose={() => {}} />,
    );
    expect(screen.queryByText('arms')).toBeNull();
  });
});
