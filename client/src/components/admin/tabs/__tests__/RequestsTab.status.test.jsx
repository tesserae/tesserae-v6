import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestsTab from '../RequestsTab';
import { listRow, detailOf, listBody, mockRequestsApi, lastListCall } from './requestsApi';

const rows = [
  listRow(1, 'pending', 'Aeneid'),
  listRow(2, 'completed', 'Georgics'),
  listRow(3, 'approved', 'Eclogues'),
];
const byId = Object.fromEntries(rows.map(r => [r.id, r]));

// Stands in for the server: honours hide_completed and keeps the server's order.
const serverList = (params) =>
  listBody(params.get('hide_completed') === '1' ? rows.filter(r => r.status !== 'completed') : rows);

const renderTab = async (onRefresh = () => {}) => {
  render(<RequestsTab authHeaders={{}} onRefresh={onRefresh} />);
  await screen.findByText('Aeneid');
};

const bodyRows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1);
const works = () => bodyRows().map(r => within(r).getAllByRole('cell')[2].textContent);

beforeEach(() => {
  mockRequestsApi({ list: serverList, detail: (id) => detailOf(byId[id]) });
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

describe('RequestsTab — completed status', () => {
  it('hides completed requests by default', async () => {
    await renderTab();
    expect(lastListCall().hide_completed).toBe('1');
    expect(works()).toEqual(['Aeneid', 'Eclogues']);
  });

  it('shows them once "Hide completed" is unticked', async () => {
    await renderTab();
    await userEvent.click(screen.getByLabelText('Hide completed'));
    expect(lastListCall().hide_completed).toBe('0');
    expect(await screen.findByText('Georgics')).toBeInTheDocument();
  });

  it('asks the server for open-work-first order and renders it as given', async () => {
    await renderTab();
    expect(lastListCall()).toMatchObject({ sort_by: 'status', sort_order: 'asc' });
    await userEvent.click(screen.getByLabelText('Hide completed'));
    await screen.findByText('Georgics');
    expect(works()).toEqual(['Aeneid', 'Georgics', 'Eclogues']);
  });

  it('gives approved and pending visually distinct badges', async () => {
    await renderTab();
    const cls = (work) => {
      const row = bodyRows().find(r => within(r).queryByText(work));
      return within(row).getByText(/pending|approved/).className;
    };
    expect(cls('Aeneid')).not.toBe(cls('Eclogues'));
  });
});

describe('RequestsTab — marking complete', () => {
  it('PUTs status=completed from the row action, then reloads the page', async () => {
    await renderTab();
    const before = global.fetch.mock.calls.length;
    const row = bodyRows().find(r => within(r).queryByText('Aeneid'));
    await userEvent.click(within(row).getByRole('button', { name: 'Mark complete' }));

    const [url, opts] = global.fetch.mock.calls[before];
    expect(url).toBe('/api/admin/requests/1');
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body)).toEqual({ status: 'completed' });
    await waitFor(() => expect(global.fetch.mock.calls.length).toBe(before + 2));
    expect(global.fetch.mock.calls[before + 1][0]).toMatch(/^\/api\/admin\/requests\?/);
  });

  it('offers Reopen instead once completed', async () => {
    await renderTab();
    await userEvent.click(screen.getByLabelText('Hide completed'));
    await screen.findByText('Georgics');
    const row = bodyRows().find(r => within(r).queryByText('Georgics'));
    expect(within(row).getByRole('button', { name: 'Reopen' })).toBeInTheDocument();
  });
});

describe('RequestsTab — status-only edit', () => {
  // The change guard in saveRequestChanges omitted 'status', so changing only the
  // status in the modal matched no field, returned early, and saved nothing --
  // with no error shown. Guard the regression.
  it('saves when the status is the only field changed', async () => {
    await renderTab();
    const row = bodyRows().find(r => within(r).queryByText('Aeneid'));
    await userEvent.click(within(row).getByRole('button', { name: 'Review' }));

    const select = await screen.findByDisplayValue('Pending');
    await userEvent.selectOptions(select, 'completed');
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    const put = global.fetch.mock.calls.find(([, o]) => o?.method === 'PUT');
    expect(put, 'no PUT issued — the change guard swallowed the edit').toBeTruthy();
    expect(JSON.parse(put[1].body).status).toBe('completed');
  });
});
