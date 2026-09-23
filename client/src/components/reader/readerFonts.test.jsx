import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

// The Reader asked for a font nobody loaded.
//
// TextPane set its family to `"Gentium Book Plus", Georgia, serif` and
// client/index.html fetched only Crimson Pro, Inter and Noto Sans, so every
// reader fell through to Georgia. Georgia has no polytonic Greek, so Greek
// fell back again character by character to whatever the machine held, and it
// has no Hebrew at all, so Hebrew borrowed a system face that sits smaller
// than Latin at the same size. Those were reported as two separate faults
// (Greek renders badly, Hebrew is tiny) and were one missing font link.
//
// These tests read the files rather than render, because what went wrong was
// the relationship between two files that never refer to each other.

const root = path.resolve(__dirname, '../../../..');
const html = fs.readFileSync(path.join(root, 'client/index.html'), 'utf8');
const pane = fs.readFileSync(
  path.join(root, 'client/src/components/reader/TextPane.jsx'), 'utf8');

function familiesRequested() {
  const link = html.split('\n').find((l) => l.includes('fonts.googleapis.com'));
  if (!link) return [];
  return [...link.matchAll(/family=([^&:"']+)/g)]
    .map((m) => decodeURIComponent(m[1]).replace(/\+/g, ' '));
}

function familiesUsedByThePane() {
  const m = pane.match(/fontFamily:\s*([\s\S]*?),\n\s*fontSize/);
  if (!m) return [];
  // The value is written as a concatenation over two lines, so join it back
  // into one string, drop the quotes, and read it as the comma-separated
  // list it becomes at runtime. Matching quoted runs instead returns the
  // fragments of the concatenation, which is not the font stack.
  const joined = m[1].replace(/\s*\+\s*/g, '').replace(/['"]/g, '')
    .replace(/\s+/g, ' ');
  return joined.split(',').map((f) => f.trim())
    .filter((f) => f && f !== 'serif');
}

describe('every font the Reader asks for is actually loaded', () => {
  it('requests the families the reading pane names', () => {
    const requested = familiesRequested();
    const used = familiesUsedByThePane();
    expect(used.length).toBeGreaterThan(0);
    for (const family of used) {
      // Georgia is a system font and is not fetched; everything else must be.
      if (family === 'Georgia') continue;
      expect(requested,
        `${family} is used by TextPane but never loaded in index.html`)
        .toContain(family);
    }
  });

  it('loads Gentium Book Plus, which is what covers polytonic Greek', () => {
    expect(familiesRequested()).toContain('Gentium Book Plus');
  });

  it('covers Hebrew, which Gentium does not', () => {
    expect(familiesRequested()).toContain('Noto Serif Hebrew');
    expect(familiesUsedByThePane()).toContain('Noto Serif Hebrew');
  });

  it('covers Coptic, which Gentium does not either', () => {
    expect(familiesRequested()).toContain('Noto Sans Coptic');
    expect(familiesUsedByThePane()).toContain('Noto Sans Coptic');
  });

  it('keeps Gentium first, so Latin and Greek get the reading face', () => {
    expect(familiesUsedByThePane()[0]).toBe('Gentium Book Plus');
  });
});

describe('the reading pane tells the browser what language it is showing', () => {
  it('sets lang from the text being read', () => {
    // Without this the browser guesses glyph shapes and line breaking from
    // the characters alone, which it cannot always do correctly.
    expect(pane).toMatch(/lang=\{language/);
  });

  it('still sets direction for right-to-left scripts', () => {
    expect(pane).toMatch(/dir=\{rtl \? 'rtl' : 'ltr'\}/);
  });
});
