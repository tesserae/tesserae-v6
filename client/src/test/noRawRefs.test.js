/**
 * Guard: no page prints a corpus file's line tag.
 *
 * The corpus files tag lines with abbreviations ("thuc. pele. 2.57.1",
 * "verg. aen. 1.1"). A page that prints `ref_start`, `ref_end` or `ref` as it
 * is shows the tag to the reader. Print the server's `locus` (or
 * windowLocus / bareLocus from components/reader/refId.js) and put the full
 * tag in `title=` as hover text. The same mistake was fixed three times in
 * October 2026 in different places; this test is what stops a fourth.
 */
import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { existsSync } from 'node:fs';

// vitest is started from the repo root or from client/.
const ROOT = [join(process.cwd(), 'client', 'src', 'components'), join(process.cwd(), 'src', 'components')]
  .find((p) => existsSync(p));

// Lines that print `{something.ref_start}`, `{something.ref_end}` or `{something.ref}`.
// `${...}` inside a template literal is not JSX text and is not matched.
const RAW_PRINT = /(?<!\$)\{\s*[\w$.?[\]]*\.(?:ref_start|ref_end|ref)\s*\}/;
// Attributes that are not display. They are cut out of the line before it is
// checked, so a line with `title={...}` and a raw print is still caught.
// (Helper calls such as bareLocus( or displayRef( never match RAW_PRINT: the
// ref is inside parentheses there, not directly inside the braces.)
// `ref=` is React's element reference (ref={menu.ref}), not a passage reference.
const NOT_DISPLAY = /\b(?:key|href|title|aria-label|ref)=(?:\{(?:[^{}]|\{[^{}]*\})*\}|"[^"]*")/g;

// Files allowed to print a raw ref, with the reason. Keep this empty if possible.
const EXCEPTIONS = {
  // 'components/example/File.jsx': 'why a raw tag is right here',
};

function jsxFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...jsxFiles(p));
    else if (p.endsWith('.jsx') && !/\.test\.jsx$/.test(p)) out.push(p);
  }
  return out;
}

export function rawRefPrints(source) {
  const hits = [];
  source.split('\n').forEach((line, i) => {
    if (RAW_PRINT.test(line.replace(NOT_DISPLAY, ''))) hits.push({ line: i + 1, text: line.trim() });
  });
  return hits;
}

describe('passage references on pages', () => {
  it('no component prints a raw ref_start, ref_end or ref', () => {
    const problems = [];
    for (const file of jsxFiles(ROOT)) {
      const rel = `components/${relative(ROOT, file)}`;
      if (EXCEPTIONS[rel]) continue;
      for (const h of rawRefPrints(readFileSync(file, 'utf8'))) {
        problems.push(`${rel}:${h.line}  ${h.text}`);
      }
    }
    expect(
      problems,
      `These lines print the file's line tag. Use the server's \`locus\` or bareLocus()/windowLocus() from reader/refId.js, with the tag in title=:\n${problems.join('\n')}`,
    ).toEqual([]);
  });

  it('the pattern catches a raw print and lets the allowed forms through', () => {
    expect(rawRefPrints('<p>{b.ref_start}</p>')).toHaveLength(1);
    expect(rawRefPrints('<p>{r?.ref_end}</p>')).toHaveLength(1);
    expect(rawRefPrints('<p>{u.ref}</p>')).toHaveLength(1);
    expect(rawRefPrints('<li key={b.ref_start}>')).toHaveLength(0);
    expect(rawRefPrints('<a title={b.ref_start}>{windowLocus(b)}</a>')).toHaveLength(0);
    expect(rawRefPrints('<span>{displayRef(u.ref)}</span>')).toHaveLength(0);
    expect(rawRefPrints('<p title={fullRef(b)}>{b.ref_start}</p>')).toHaveLength(1);
    expect(rawRefPrints('const k = `${r.work}|${r.ref_start}`;')).toHaveLength(0);
  });
});
