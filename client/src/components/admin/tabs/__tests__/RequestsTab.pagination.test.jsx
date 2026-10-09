import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RequestsTab from '../RequestsTab';
import {
  listRow, detailOf, listBody, respond, mockRequestsApi, listCalls, lastListCall,
} from './requestsApi';

const page1 = [listRow(1, 'pending', 'Aeneid'), listRow(2, 'pending', 'Georgics')];
const page2 = [listRow(3, 'approved', 'Eclogues')];
const all = [...page1, ...page2];
const byId = Object.fromEntries(all.map(r => [r.id, r]));

// 120 requests in all, so three pages at the default 50.
const pagedList = (params) =>
  listBody(params.get('page') === '2' ? page2 : page1, { total: 120, pages: 3, pending_count: 7 });

const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
};

const renderTab = () => render(<RequestsTab authHeaders={{}} onRefresh={() => {}} />);
const works = () =>
  within(screen.getByRole('table')).getAllByRole('row').slice(1)
    .map(r => within(r).getAllByRole('cell')[2].textContent);
const reviewButton = (work) =>
  within(screen.getByText(work).closest('tr')).getByRole('button', { name: /Review|Loading/ });

beforeEach(() => {
  mockRequestsApi({ list: pagedList, detail: (id) => detailOf(byId[id]) });
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

describe('RequestsTab — server-backed list', () => {
  it('asks for page 1 of 50 with the default filter and sort', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    expect(listCalls()).toEqual([{
      page: '1', per_page: '50', status: 'all', hide_completed: '1', sort_by: 'status', sort_order: 'asc',
    }]);
  });

  it('shows the server pending count and totals', async () => {
    renderTab();
    expect(await screen.findByText('7 pending')).toBeInTheDocument();
    expect(screen.getByText(/Showing 1–50 of 120 requests/)).toBeInTheDocument();
  });

  it('fetches page 2 from the server rather than slicing', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    expect(await screen.findByText('Eclogues')).toBeInTheDocument();
    expect(lastListCall().page).toBe('2');
    expect(works()).toEqual(['Eclogues']);
  });

  it('offers the server page sizes and starts over on page 1 when one is picked', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await screen.findByText('Eclogues');
    const sizes = screen.getByLabelText('Show');
    expect([...sizes.options].map(o => o.value)).toEqual(['25', '50', '100', '500']);
    await userEvent.selectOptions(sizes, '100');
    await waitFor(() => expect(lastListCall()).toMatchObject({ page: '1', per_page: '100' }));
  });

  it('resets to page 1 when the status filter changes', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await screen.findByText('Eclogues');
    await userEvent.selectOptions(screen.getByLabelText('Filter'), 'pending');
    await waitFor(() => expect(lastListCall()).toMatchObject({ page: '1', status: 'pending' }));
  });

  it('resets to page 1 when the sort changes', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await screen.findByText('Eclogues');
    await userEvent.selectOptions(screen.getByLabelText('Sort'), 'newest');
    await waitFor(() =>
      expect(lastListCall()).toMatchObject({ page: '1', sort_by: 'created_at', sort_order: 'desc' }));
  });

  it('steps back when the current page comes back empty', async () => {
    let last = page2;
    mockRequestsApi({
      list: (p) => listBody(p.get('page') === '1' ? page1 : last, { total: last.length ? 51 : 50, pages: last.length ? 2 : 1 }),
      detail: (id) => detailOf(byId[id]),
    });
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    await screen.findByText('Eclogues');
    last = []; // its only row is completed and now hidden
    await userEvent.click(screen.getByRole('button', { name: 'Mark complete' }));
    expect(await screen.findByText('Aeneid')).toBeInTheDocument();
    expect(lastListCall().page).toBe('1');
  });
});

describe('RequestsTab — loading, empty and error states', () => {
  it('shows a loading row until the first page arrives', async () => {
    const d = deferred();
    mockRequestsApi({ list: () => d.promise, detail: () => ({}) });
    renderTab();
    expect(screen.getByText('Loading text requests...')).toBeInTheDocument();
    d.resolve(await respond(listBody(page1)));
    expect(await screen.findByText('Aeneid')).toBeInTheDocument();
  });

  it('keeps the current rows on screen while the next page loads', async () => {
    const d = deferred();
    mockRequestsApi({ list: (p) => (p.get('page') === '2' ? d.promise : pagedList(p)), detail: () => ({}) });
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(screen.getByRole('button', { name: 'Go to page 2' }));
    expect(screen.getByText('Aeneid')).toBeInTheDocument();
    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true');
    d.resolve(await respond(pagedList(new URLSearchParams('page=2'))));
    expect(await screen.findByText('Eclogues')).toBeInTheDocument();
  });

  it('says so when a filter matches nothing', async () => {
    mockRequestsApi({ list: () => listBody([]), detail: () => ({}) });
    renderTab();
    expect(await screen.findByText('No text requests for this filter')).toBeInTheDocument();
  });

  it('shows the server error and retries on request', async () => {
    let fail = true;
    mockRequestsApi({
      list: () => (fail ? respond({ error: 'database unavailable' }, 500) : listBody(page1)),
      detail: () => ({}),
    });
    renderTab();
    expect(await screen.findByRole('alert')).toHaveTextContent('database unavailable');
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Aeneid')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('never lets an older response overwrite a newer one', async () => {
    const slowAll = deferred();
    mockRequestsApi({
      list: (p) => (p.get('status') === 'all' ? slowAll.promise : listBody(page2)),
      detail: () => ({}),
    });
    renderTab();
    await userEvent.selectOptions(screen.getByLabelText('Filter'), 'approved');
    expect(await screen.findByText('Eclogues')).toBeInTheDocument();
    // The superseded 'all' request finishes last.
    slowAll.resolve(await respond(listBody(page1)));
    await new Promise(r => setTimeout(r, 20));
    expect(works()).toEqual(['Eclogues']);
  });
});

describe('RequestsTab — full request loaded on demand', () => {
  it('lists without content and fetches the request when it is opened', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    expect(global.fetch.mock.calls.some(([url]) => /\/requests\/\d+/.test(url))).toBe(false);

    await userEvent.click(reviewButton('Aeneid'));
    expect(await screen.findByDisplayValue('arma virumque cano 1')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith('/api/admin/requests/1', expect.objectContaining({ credentials: 'include' }));
  });

  it('opens nothing editable until the full request has arrived', async () => {
    const d = deferred();
    mockRequestsApi({ list: pagedList, detail: () => d.promise });
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(reviewButton('Aeneid'));
    expect(reviewButton('Aeneid')).toHaveTextContent('Loading...');
    expect(screen.queryByRole('button', { name: 'Save Changes' })).not.toBeInTheDocument();
    d.resolve(await respond(detailOf(byId[1])));
    expect(await screen.findByRole('button', { name: 'Save Changes' })).toBeInTheDocument();
  });

  it('saves with the stored content, never an empty one', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(reviewButton('Aeneid'));
    await userEvent.selectOptions(await screen.findByDisplayValue('Pending'), 'rejected');
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    const put = global.fetch.mock.calls.find(([, o]) => o?.method === 'PUT');
    expect(JSON.parse(put[1].body).content).toBe('arma virumque cano 1');
  });

  it('approves with the loaded content', async () => {
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(reviewButton('Aeneid'));
    await userEvent.click(await screen.findByRole('button', { name: 'Approve & Add to Corpus' }));
    const approve = global.fetch.mock.calls.find(([url]) => url.endsWith('/approve'));
    expect(JSON.parse(approve[1].body)).toEqual({ content: 'arma virumque cano 1', overwrite: false });
  });

  it('alerts and opens nothing when the request cannot be loaded', async () => {
    mockRequestsApi({ list: pagedList, detail: () => respond({ error: 'Request not found' }, 404) });
    renderTab();
    await screen.findByText('Aeneid');
    await userEvent.click(reviewButton('Aeneid'));
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('Request not found'));
    expect(screen.queryByRole('button', { name: 'Save Changes' })).not.toBeInTheDocument();
    expect(reviewButton('Aeneid')).toHaveTextContent('Review');
  });
});
