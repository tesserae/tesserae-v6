/**
 * The committed rendered pages (backend/assistant/rendered_pages/) are what
 * Tessa reads; they must match the pages as they stand. A change to the Help,
 * About, Downloads, Scholarship sources or Privacy page needs
 * `npm run render:tessa` and the output committed, or this fails.
 */
import fs from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { renderPagesForTessa, helpSectionIds, OUT_DIR } from './renderPagesForTessa';

describe('the rendered pages Tessa reads', () => {
  const fresh = renderPagesForTessa();

  it('match the committed copies (otherwise run npm run render:tessa and commit the output)', () => {
    for (const [name, html] of Object.entries(fresh)) {
      const file = path.join(OUT_DIR, name);
      expect(fs.existsSync(file), `${file} is missing: run npm run render:tessa`).toBe(true);
      // The About page prints the current year, so a copy rendered last year still passes.
      const mask = (s) => (name === 'about.html' ? s.replaceAll(String(new Date().getFullYear()), 'YYYY') : s);
      expect(mask(fs.readFileSync(file, 'utf8')), `${name} is behind the page: run npm run render:tessa and commit it`).toBe(mask(html + '\n'));
    }
  });

  it('open every Help section, and only what a visitor can see', () => {
    const ids = helpSectionIds();
    expect(ids.length).toBeGreaterThan(30);
    for (const id of ids) expect(fresh['help.html']).toContain(`<!-- help section ${id} -->`);
    expect(fresh['help.html']).toContain('Use Tesserae with your AI assistant');
    // The sentence from the dead branch of 2026-11-25 (see renderPagesForTessa.jsx).
    expect(fresh['help.html']).not.toContain('official Tesserae GPT');
  });
});
