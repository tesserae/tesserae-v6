/**
 * A sentence inside a long prose unit is the thing a click selects
 * (2026-10-11). Verse lines are unchanged.
 */
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import TextPane from './TextPane';
import { splitSentences } from '../../utils/sentences';

const S1 = 'Vrbem Romam a principio reges habuere, libertatem et consulatum L. Brutus instituit atque ad tempus dictaturae sumebantur neque decemviralis potestas ultra biennium valuit neque tribunorum militum consulare ius diu.';
const S2 = 'Tiberii Gaique et Claudii ac Neronis res florentibus ipsis ob metum falsae, postquam occiderant recentibus odiis compositae sunt, inde consilium mihi pauca de Augusto et extrema tradere mox Tiberii principatum.';
const S3 = 'Sine ira et studio, quorum causas procul habeo, et cetera quae ad rem pertinent, sed veteris populi Romani prospera vel adversa claris scriptoribus memorata sunt temporibusque Augusti dicendis non defuere decora ingenia.';
const PROSE = `${S1} ${S2} ${S3}`;
const UNITS = [
  { ref: 'Tac. Ann. 1.1', text: PROSE },
  { ref: 'Tac. Ann. 1.2', text: PROSE.replace('Vrbem', 'Vrbis') },
  { ref: 'verg. aen. 1.1', text: 'Arma virumque cano, Troiae qui primus ab oris' },
];

const originalMatchMedia = window.matchMedia;
function pointer(coarse) {
  window.matchMedia = (query) => ({
    matches: coarse && /coarse/.test(query),
    media: query, onchange: null,
    addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
    dispatchEvent: () => false,
  });
}
afterEach(() => { window.matchMedia = originalMatchMedia; window.getSelection().removeAllRanges(); });

const parts = splitSentences(PROSE);

describe('a long prose unit is drawn as sentences', () => {
  it('keeps the text exactly and marks each sentence', () => {
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={() => {}} />);
    expect(parts).toHaveLength(3);
    const first = container.querySelector('[id^="line-"]');
    expect(first.querySelectorAll('[data-sentence]')).toHaveLength(3);
    expect(first.querySelector('p').textContent).toBe(PROSE);
  });

  it('leaves a verse line as plain text', () => {
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={() => {}} />);
    const verse = container.querySelectorAll('[id^="line-"]')[2];
    expect(verse.querySelectorAll('[data-sentence]')).toHaveLength(0);
  });
});

describe('mouse', () => {
  beforeEach(() => pointer(false));

  const click = (el) => { fireEvent.mouseDown(el, { button: 0 }); fireEvent.mouseUp(window); };

  it('a click on the second sentence selects it', () => {
    const onSelect = vi.fn();
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={onSelect} />);
    click(container.querySelectorAll('[data-sentence="1"]')[0]);
    const sel = onSelect.mock.calls[0][0];
    expect(sel.startIdx).toBe(0);
    expect(sel.endIdx).toBe(0);
    expect(sel.lineCount).toBe(1);
    expect(sel.charStart).toBe(parts[1].start);
    expect(sel.charEnd).toBe(parts[1].textEnd);
    expect(sel.text).toBe(PROSE.slice(parts[1].start, parts[1].textEnd));
    expect(sel.sentenceCount).toBe(1);
    expect(PROSE.slice(sel.charStart, sel.charEnd).startsWith('Tiberii')).toBe(true);
  });

  it('a drag from the first sentence into the second selects both', () => {
    const onSelect = vi.fn();
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={onSelect} />);
    const a = container.querySelectorAll('[data-sentence="0"]')[0];
    const b = container.querySelectorAll('[data-sentence="1"]')[0];
    fireEvent.mouseDown(a, { button: 0 });
    window.getSelection().setBaseAndExtent(a.firstChild, 5, b.firstChild, 20);
    fireEvent.mouseUp(window);
    const sel = onSelect.mock.calls[0][0];
    expect(sel.charStart).toBe(parts[0].start);
    expect(sel.charEnd).toBe(parts[1].textEnd);
    expect(sel.sentenceCount).toBe(2);
    expect(sel.text).toBe(PROSE.slice(parts[0].start, parts[1].textEnd));
  });

  it('a drag that takes in every sentence is the whole unit', () => {
    const onSelect = vi.fn();
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={onSelect} />);
    const a = container.querySelectorAll('[data-sentence="0"]')[0];
    const c = container.querySelectorAll('[data-sentence="2"]')[0];
    fireEvent.mouseDown(a, { button: 0 });
    window.getSelection().setBaseAndExtent(a.firstChild, 0, c.firstChild, 30);
    fireEvent.mouseUp(window);
    const sel = onSelect.mock.calls[0][0];
    expect(sel.charStart).toBeNull();
    expect(sel.charEnd).toBeNull();
    expect(sel.sentenceTotal).toBe(3);
  });

  it('a drag across two units selects whole units, as before', () => {
    const onSelect = vi.fn();
    const { container } = render(<TextPane units={UNITS} language="la" selection={null} onSelect={onSelect} />);
    const a = container.querySelectorAll('[data-sentence="1"]')[0];
    const b = container.querySelectorAll('[data-sentence="1"]')[1];
    fireEvent.mouseDown(a, { button: 0 });
    window.getSelection().setBaseAndExtent(a.firstChild, 3, b.firstChild, 9);
    fireEvent.mouseEnter(b.closest('[id^="line-"]'));
    fireEvent.mouseUp(window);
    const sel = onSelect.mock.calls[0][0];
    expect(sel.lineCount).toBe(2);
    expect(sel.charStart).toBeUndefined();
  });

  it('a click on a verse line is as before', () => {
    const onSelect = vi.fn();
    render(<TextPane units={UNITS} language="la" selection={null} onSelect={onSelect} />);
    click(screen.getByText('Arma virumque cano, Troiae qui primus ab oris'));
    const sel = onSelect.mock.calls[0][0];
    expect(sel.startIdx).toBe(2);
    expect(sel.charStart).toBeUndefined();
  });

  it('lights the selected sentence', () => {
    const selection = { startIdx: 0, endIdx: 0, refStart: UNITS[0].ref, refEnd: UNITS[0].ref,
                        lineCount: 1, charStart: parts[1].start, charEnd: parts[1].textEnd,
                        sentenceTotal: 3, sentenceCount: 1, startSentence: 1, text: 'x' };
    const { container } = render(<TextPane units={UNITS} language="la" selection={selection} onSelect={() => {}} />);
    const spans = container.querySelectorAll('[id^="line-"]')[0].querySelectorAll('[data-sentence]');
    expect(spans[0].className).not.toMatch(/bg-red-100/);
    expect(spans[1].className).toMatch(/bg-red-100/);
    expect(spans[2].className).not.toMatch(/bg-red-100/);
  });

  it('paints the lit sentence, not the whole unit, when the selection is part of it', () => {
    // 2026-10-12: with the chapter painted pink behind a lit sentence, the
    // reader could not see which sentence was selected.
    const selection = { startIdx: 0, endIdx: 0, refStart: UNITS[0].ref, refEnd: UNITS[0].ref,
                        lineCount: 1, charStart: parts[1].start, charEnd: parts[1].textEnd,
                        sentenceTotal: 3, sentenceCount: 1, startSentence: 1, text: 'x' };
    const { container } = render(<TextPane units={UNITS} language="la" selection={selection} onSelect={() => {}} />);
    const unit = container.querySelectorAll('[id^="line-"]')[0];
    expect(unit.className).not.toMatch(/bg-red-50/);
    expect(unit.className).toMatch(/border-red-700/);
  });

  it('paints the whole unit when every sentence is selected', () => {
    const selection = { startIdx: 0, endIdx: 0, refStart: UNITS[0].ref, refEnd: UNITS[0].ref,
                        lineCount: 1, charStart: null, charEnd: null, text: PROSE };
    const { container } = render(<TextPane units={UNITS} language="la" selection={selection} onSelect={() => {}} />);
    const unit = container.querySelectorAll('[id^="line-"]')[0];
    expect(unit.className).toMatch(/bg-red-50/);
  });
});

describe('touch', () => {
  beforeEach(() => pointer(true));

  function Harness({ onSelect }) {
    const [sel, setSel] = useState(null);
    return (
      <TextPane units={UNITS} language="la" selection={sel}
                onSelect={(s) => { onSelect(s); setSel(s); }} />
    );
  }

  it('a tap selects a sentence, a second tap on another extends, a tap on the selected one widens', () => {
    const seen = [];
    const { container } = render(<Harness onSelect={(s) => seen.push(s)} />);
    const sp = (k) => container.querySelectorAll('[id^="line-"]')[0].querySelector(`[data-sentence="${k}"]`);
    fireEvent.click(sp(1));
    expect(seen[0].charStart).toBe(parts[1].start);
    fireEvent.click(sp(2));                       // extend to the third
    expect(seen[1].charStart).toBe(parts[1].start);
    expect(seen[1].charEnd).toBe(parts[2].textEnd);
    expect(seen[1].sentenceCount).toBe(2);
    fireEvent.click(sp(2));                       // inside a two-sentence span: narrow to it
    expect(seen[2].charStart).toBe(parts[2].start);
    expect(seen[2].charEnd).toBe(parts[2].textEnd);
    fireEvent.click(sp(2));                       // the one selected sentence: widen
    expect(seen[3].charStart).toBeNull();
    expect(seen[3].text).toBe(PROSE);
  });

  it('a tap on the reference label widens to the whole unit', () => {
    const seen = [];
    const { container } = render(<Harness onSelect={(s) => seen.push(s)} />);
    const unit = container.querySelectorAll('[id^="line-"]')[0];
    fireEvent.click(unit.querySelector('[data-sentence="0"]'));
    expect(seen[0].charStart).toBe(parts[0].start);
    fireEvent.click(unit.querySelector('[data-label]'));
    expect(seen[1].charStart).toBeNull();
    expect(seen[1].lineCount).toBe(1);
  });

  it('a tap in another unit extends over whole units, as before', () => {
    const seen = [];
    const { container } = render(<Harness onSelect={(s) => seen.push(s)} />);
    const units = container.querySelectorAll('[id^="line-"]');
    fireEvent.click(units[0].querySelector('[data-sentence="1"]'));
    fireEvent.click(units[1].querySelector('[data-sentence="1"]'));
    expect(seen[1].lineCount).toBe(2);
    expect(seen[1].charStart).toBeUndefined();
  });

  it('a tap on a verse line selects the line', () => {
    const seen = [];
    render(<Harness onSelect={(s) => seen.push(s)} />);
    fireEvent.click(screen.getByText('Arma virumque cano, Troiae qui primus ab oris'));
    expect(seen[0].startIdx).toBe(2);
    expect(seen[0].text).toBe('Arma virumque cano, Troiae qui primus ab oris');
  });
});
