import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { MIGRATED_CALL_SITES } from './migratedCallSites';

const SRC = resolve(__dirname, '..');
const source = (file) => readFileSync(resolve(SRC, file), 'utf8');

// The path a call reads or writes: the first /api/... literal in the call.
const apiPath = (call) => {
  const m = call.match(/['`](\/api\/[A-Za-z0-9_\-/]+)/);
  // a path that continues into a template (`/api/text/${id}`) cannot be
  // matched whole, so it is not checked for a leftover bare fetch
  return m && !m[1].endsWith('/') ? m[1] : null;
};

describe('pages that moved to the shared request helper', () => {
  it.each(MIGRATED_CALL_SITES)('%s: %s', (file, call) => {
    const text = source(file);
    expect(text).toContain(call);
    const helperImport = /import \{[^}]*\} from '[./]+\/(utils\/)?api';/;
    expect(text).toMatch(helperImport);
    const path = apiPath(call);
    if (path) {
      // no bare fetch() left on the same path in this file
      const bare = new RegExp("fetch\\(\\s*[`'\"]" + path.replace(/\//g, '\\/'));
      expect(text).not.toMatch(bare);
    }
  });

  it('lists a non-trivial number of call sites', () => {
    expect(MIGRATED_CALL_SITES.length).toBeGreaterThan(50);
  });
});
