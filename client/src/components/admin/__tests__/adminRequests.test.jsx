/**
 * The admin tabs and the assistant dock send their requests through utils/api.js.
 * Each test mounts a component, answers every request with a canned body, and
 * checks the URL, method and body it sent (the same ones it sent when it called
 * fetch itself), plus that a server error page now reads as a message.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UsersTab from '../tabs/UsersTab';
import SourcesTab from '../tabs/SourcesTab';
import SettingsTab from '../tabs/SettingsTab';
import AuditTab from '../tabs/AuditTab';
import MetadataTab from '../tabs/MetadataTab';
import FeedbackTab from '../tabs/FeedbackTab';
import CacheTab from '../tabs/CacheTab';
import DictionaryReviewTab from '../tabs/DictionaryReviewTab';
import GenreClassificationTab from '../tabs/GenreClassificationTab';
import AdminPanel from '../AdminPanel';
import AssistantDock from '../../assistant/AssistantDock';

const AUTH = { 'X-Admin-Key': 'k' };

// Answers each request from a table keyed "METHOD /path"; anything else is a 404 JSON.
const answerWith = (routes) => {
  global.fetch = vi.fn((url, init = {}) => {
    const key = `${init.method || 'GET'} ${String(url).split('?')[0]}`;
    const [status, body] = routes[key] || [404, { error: `no route ${key}` }];
    const text = typeof body === 'string' ? body : JSON.stringify(body);
    return Promise.resolve({ ok: status < 400, status, text: () => Promise.resolve(text) });
  });
  return global.fetch;
};

const callsTo = (method, path) =>
  global.fetch.mock.calls.filter(([url, init = {}]) =>
    (init.method || 'GET') === method && String(url).split('?')[0] === path);

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { delete global.fetch; vi.restoreAllMocks(); });

describe('admin tabs send the requests they always sent', () => {
  it('UsersTab loads users and roles with the admin headers and credentials', async () => {
    const fetchMock = answerWith({
      'GET /api/admin/users': [200, { users: [] }],
      'GET /api/admin/roles': [200, { roles: ['USER'] }],
    });
    render(<UsersTab authHeaders={AUTH} isAdmin isSuperAdmin />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(callsTo('GET', '/api/admin/users')[0][1]).toEqual({ headers: AUTH, credentials: 'include' });
    expect(callsTo('GET', '/api/admin/roles')[0][1]).toEqual({ headers: AUTH, credentials: 'include' });
  });

  it('UsersTab shows a readable message when the server answers with an error page', async () => {
    answerWith({ 'GET /api/admin/users': [502, '<html><body>502 Bad Gateway</body></html>'] });
    render(<UsersTab authHeaders={AUTH} isAdmin isSuperAdmin />);
    expect(await screen.findByText(/^502 from \/api\/admin\/users: <html>/)).toBeTruthy();
  });

  it('SourcesTab loads sources, then posts a new one with the JSON body', async () => {
    answerWith({
      'GET /api/admin/sources': [200, { sources: [] }],
      'POST /api/admin/sources': [200, { success: true }],
    });
    render(<SourcesTab authHeaders={AUTH} />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/sources')).toHaveLength(1));
    expect(callsTo('GET', '/api/admin/sources')[0][1]).toEqual({ headers: AUTH });
    await userEvent.click(screen.getByText('+ Add Source'));
    await userEvent.type(screen.getByPlaceholderText('e.g., Vergil'), 'Vergil');
    await userEvent.click(screen.getByRole('button', { name: 'Add' }));
    await waitFor(() => expect(callsTo('POST', '/api/admin/sources')).toHaveLength(1));
    const init = callsTo('POST', '/api/admin/sources')[0][1];
    expect(init.headers).toEqual({ 'Content-Type': 'application/json', ...AUTH });
    expect(JSON.parse(init.body).author).toBe('Vergil');
  });

  it('SettingsTab reads the settings and posts the notification emails', async () => {
    answerWith({
      'GET /api/admin/settings': [200, { notification_emails: 'a@b.edu' }],
      'POST /api/admin/settings': [200, { success: true }],
    });
    render(<SettingsTab authHeaders={AUTH} />);
    await waitFor(() => expect(screen.getByDisplayValue('a@b.edu')).toBeTruthy());
    await userEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(callsTo('POST', '/api/admin/settings')).toHaveLength(1));
    const init = callsTo('POST', '/api/admin/settings')[0][1];
    expect(JSON.parse(init.body)).toEqual({ notification_emails: 'a@b.edu' });
    expect(init.headers).toEqual({ 'Content-Type': 'application/json', ...AUTH });
  });

  it('AuditTab reads the audit log with the admin headers', async () => {
    answerWith({ 'GET /api/admin/audit-log': [200, { entries: [] }] });
    render(<AuditTab authHeaders={AUTH} />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/audit-log')).toHaveLength(1));
    expect(global.fetch.mock.calls[0][0]).toBe('/api/admin/audit-log?limit=100');
    expect(global.fetch.mock.calls[0][1]).toEqual({ headers: AUTH });
  });

  it('MetadataTab reads the corpus texts', async () => {
    answerWith({ 'GET /api/admin/corpus-texts': [200, { texts: [] }] });
    render(<MetadataTab authHeaders={AUTH} />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/corpus-texts')).toHaveLength(1));
    expect(global.fetch.mock.calls[0][1]).toEqual({ headers: AUTH });
  });

  it('FeedbackTab puts the new status', async () => {
    answerWith({ 'PUT /api/admin/feedback/4': [200, { success: true }] });
    render(<FeedbackTab feedback={[{ id: 4, status: 'pending', message: 'hello', created_at: '2026-10-01T00:00:00Z' }]} onRefresh={async () => {}} />);
    await userEvent.click(screen.getAllByRole('button', { name: 'Responded' }).at(-1));
    await waitFor(() => expect(callsTo('PUT', '/api/admin/feedback/4')).toHaveLength(1));
    const init = callsTo('PUT', '/api/admin/feedback/4')[0][1];
    expect(init.credentials).toBe('include');
    expect(JSON.parse(init.body)).toEqual({ status: 'responded' });
  });

  it('CacheTab clears the lemma cache with a POST of an empty object', async () => {
    answerWith({ 'POST /api/admin/lemma-cache/clear': [200, { success: true }] });
    const onRefresh = vi.fn(async () => {});
    render(<CacheTab authHeaders={AUTH} cacheInfo={{}} bigramStats={{}} onRefresh={onRefresh} onBigramStatsUpdate={() => {}} />);
    await userEvent.click(screen.getAllByText('Clear...')[1]);
    await userEvent.click(await screen.findByRole('button', { name: /Yes, Clear Cache/ }));
    await waitFor(() => expect(callsTo('POST', '/api/admin/lemma-cache/clear')).toHaveLength(1));
    const init = callsTo('POST', '/api/admin/lemma-cache/clear')[0][1];
    expect(init.body).toBe('{}');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json', ...AUTH });
  });

  it('DictionaryReviewTab loads the pending page and shows a readable message on an error page', async () => {
    answerWith({ 'GET /api/admin/dictionary-review': [500, '<html>Internal Server Error</html>'] });
    render(<DictionaryReviewTab />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/dictionary-review')).toHaveLength(1));
    expect(global.fetch.mock.calls[0][0]).toBe('/api/admin/dictionary-review?status=pending&limit=25&offset=0');
    expect(global.fetch.mock.calls[0][1]).toEqual({ credentials: 'include' });
    expect(await screen.findByText(/^500 from \/api\/admin\/dictionary-review\?status=pending/)).toBeTruthy();
  });

  it('GenreClassificationTab reads the genres with credentials', async () => {
    answerWith({ 'GET /api/admin/text-genres': [200, { texts: [], genres: [] }] });
    render(<GenreClassificationTab />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/text-genres')).toHaveLength(1));
    expect(global.fetch.mock.calls[0][1]).toEqual({ credentials: 'include' });
  });

  it('AdminPanel asks for the session once, with credentials', async () => {
    answerWith({ 'GET /api/admin/me': [401, { error: 'not signed in' }] });
    render(<AdminPanel />);
    await waitFor(() => expect(callsTo('GET', '/api/admin/me')).toHaveLength(1));
    expect(callsTo('GET', '/api/admin/me')[0][1]).toEqual({ credentials: 'include' });
  });
});

describe('the assistant dock', () => {
  it('asks for the assistant status with a bare GET', async () => {
    answerWith({ 'GET /api/assistant/status': [200, { available: true }] });
    render(<AssistantDock />);
    await waitFor(() => expect(callsTo('GET', '/api/assistant/status')).toHaveLength(1));
    expect(global.fetch.mock.calls[0]).toHaveLength(1);
  });
});
