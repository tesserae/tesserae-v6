/**
 * `npm run render:tessa`: write the pages Tessa reads, rendered, to
 * backend/assistant/rendered_pages/. Runs under vite-node, outside a browser,
 * so a jsdom window stands in for the browser's (the same kind and the same
 * URL the tests use, so the output matches renderedPages.test.jsx).
 */
import fs from 'node:fs';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:3000/' });
for (const name of ['window', 'document', 'navigator', 'localStorage', 'sessionStorage',
  'HTMLElement', 'CustomEvent', 'Node', 'Element', 'getComputedStyle', 'matchMedia']) {
  if (!(name in globalThis) && name in dom.window) globalThis[name] = dom.window[name];
}

const { renderPagesForTessa, OUT_DIR } = await import('./renderPagesForTessa.jsx');
fs.mkdirSync(OUT_DIR, { recursive: true });
for (const [name, html] of Object.entries(renderPagesForTessa())) {
  fs.writeFileSync(path.join(OUT_DIR, name), html + '\n');
  console.log(`${name}: ${html.length} characters`);
}
