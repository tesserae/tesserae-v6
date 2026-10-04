import { vi } from 'vitest';

// A list row as GET /api/admin/requests returns it: no content.
export const listRow = (id, status, work) => ({
  id,
  status,
  author: 'Vergil',
  work,
  language: 'la',
  created_at: '2026-08-01T00:00:00Z',
  admin_updated_at: null,
});

// The full request as GET /api/admin/requests/<id> returns it.
export const detailOf = (row) => ({
  ...row,
  name: 'Someone',
  email: 'someone@example.edu',
  notes: '',
  content: `arma virumque cano ${row.id}`,
  official_author: row.author,
  official_work: row.work,
  approved_filename: '',
  suggested_filename: 'vergil.aeneid.tess',
  admin_notes: '',
  text_date: '',
  author_era: '',
  author_year: null,
  e_source: '',
  e_source_url: '',
  print_source: '',
  added_by: '',
});

export const listBody = (rows, extra = {}) => ({
  requests: rows,
  total: rows.length,
  pages: rows.length ? 1 : 0,
  current_page: 1,
  per_page: 50,
  pending_count: rows.filter(r => r.status === 'pending').length,
  ...extra,
});

export const respond = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

/**
 * Routes fetch by URL: the list endpoint answers with list(params), a detail URL
 * with detail(id), and any write (PUT/POST/DELETE) with { success: true }.
 * Either answer may be a body or a promise of a response (for deferred tests).
 */
export const mockRequestsApi = ({ list, detail }) => {
  global.fetch = vi.fn((url, opts = {}) => {
    if (opts.method && opts.method !== 'GET') return respond({ success: true });
    const [path, qs] = url.split('?');
    const id = path.match(/\/api\/admin\/requests\/(\d+)$/)?.[1];
    const answer = id ? detail(Number(id)) : list(new URLSearchParams(qs));
    return answer?.then ? answer : respond(answer);
  });
  return global.fetch;
};

export const listCalls = () =>
  global.fetch.mock.calls
    .filter(([url, opts]) => url.startsWith('/api/admin/requests?') && !opts?.method)
    .map(([url]) => Object.fromEntries(new URLSearchParams(url.split('?')[1])));

export const lastListCall = () => listCalls().at(-1);
