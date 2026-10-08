import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SelectionToolbar, { wordOf, scopeFor } from './SelectionToolbar';

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
