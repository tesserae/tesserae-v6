import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, it, expect } from 'vitest';
import { markMatchedWords, highlightResultHtml, renderInstanceText } from './highlight';
import cases from './__fixtures__/highlight_cases.json';

// highlight_cases.json holds 60 inputs and the outputs the three old
// functions in SearchResults.jsx gave for them on main (recorded before the
// module existed): twenty for the CSV export's highlightMatchedWords, twenty
// for the card's renderHighlightedText, twenty for the corpus panel's
// renderInstanceText. The one module has to give the same output for each.
const run = {
  highlightMatchedWords: (args) => markMatchedWords(...args),
  renderHighlightedText: (args) => highlightResultHtml(...args),
  renderInstanceText: (args) => {
    const r = renderInstanceText(...args);
    return r == null ? null : renderToStaticMarkup(createElement(Fragment, null, r));
  },
};

describe('highlight module against the recorded outputs of the three old functions', () => {
  it('has the sixty recorded cases', () => {
    expect(cases).toHaveLength(60);
    expect(new Set(cases.map((c) => c.fn))).toEqual(new Set(Object.keys(run)));
  });
  it.each(cases)('$name', (c) => {
    expect(run[c.fn](c.args)).toBe(c.output);
  });
});
