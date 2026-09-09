import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestsTab from '../RequestsTab';

const req = (id, status, work) => ({
  id,
  status,
  name: 'Someone',
  author: 'Vergil',
  work,
  language: 'la',
  content: 'arma virumque cano',
  created_at: '2026-08-01T00:00:00Z',
});

const rows = [
  req(1, 'pending', 'Aeneid'),
  req(2, 'completed', 'Georgics'),
  req(3, 'approved', 'Eclogues'),
];

const renderTab = (textRequests = rows, onRefresh = () => {}) =>
  render(
    <RequestsTab authHeaders={{}} textRequests={textRequests} onRefresh={onRefresh} />
  );

const bodyRows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1);
const works = () => bodyRows().map(r => within(r).getAllByRole('cell')[2].textContent);

beforeEach(() => {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  );
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

describe('RequestsTab — completed status', () => {
  it('hides completed requests by default', () => {
    renderTab();
    expect(works()).toEqual(['Aeneid', 'Eclogues']);
  });

  it('shows them once "Hide completed" is unticked', async () => {
    renderTab();
    await userEvent.click(screen.getByLabelText('Hide completed'));
    expect(works()).toContain('Georgics');
  });

  it('sorts completed last', async () => {
    renderTab();
    await userEvent.click(screen.getByLabelText('Hide completed'));
    expect(works()).toEqual(['Aeneid', 'Eclogues', 'Georgics']);
  });

  it('gives approved and pending visually distinct badges', () => {
    renderTab();
    const cls = (work) => {
      const row = bodyRows().find(r => within(r).queryByText(work));
      return within(row).getByText(/pending|approved/).className;
    };
    expect(cls('Aeneid')).not.toBe(cls('Eclogues'));
  });
});

describe('RequestsTab — marking complete', () => {
  it('PUTs status=completed from the row action', async () => {
    renderTab();
    const row = bodyRows().find(r => within(r).queryByText('Aeneid'));
    await userEvent.click(within(row).getByRole('button', { name: 'Mark complete' }));

    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/admin/requests/1');
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body)).toEqual({ status: 'completed' });
  });

  it('offers Reopen instead once completed', async () => {
    renderTab();
    await userEvent.click(screen.getByLabelText('Hide completed'));
    const row = bodyRows().find(r => within(r).queryByText('Georgics'));
    expect(within(row).getByRole('button', { name: 'Reopen' })).toBeInTheDocument();
  });
});

describe('RequestsTab — status-only edit', () => {
  // The change guard in saveRequestChanges omitted 'status', so changing only the
  // status in the modal matched no field, returned early, and saved nothing --
  // with no error shown. Guard the regression.
  it('saves when the status is the only field changed', async () => {
    renderTab();
    const row = bodyRows().find(r => within(r).queryByText('Aeneid'));
    await userEvent.click(within(row).getByRole('button', { name: 'Review' }));

    const select = screen.getByDisplayValue('Pending');
    await userEvent.selectOptions(select, 'completed');
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    const put = global.fetch.mock.calls.find(([, o]) => o?.method === 'PUT');
    expect(put, 'no PUT issued — the change guard swallowed the edit').toBeTruthy();
    expect(JSON.parse(put[1].body).status).toBe('completed');
  });
});
