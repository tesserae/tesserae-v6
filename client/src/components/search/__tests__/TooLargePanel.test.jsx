import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TooLargePanel from '../TooLargePanel';
import { mockResponse } from '../../../test/mockResponse';

afterEach(() => { delete global.fetch; });

const answer = {
  too_large: true,
  line_pairs: 118712416,
  limit: 100000000,
  email_notice: false,
  download_job_url: '/api/comparisons/jobs',
  books: [
    { side: 'source', work: 'vergil.aeneid.tess', id: 'vergil.aeneid.part.1.tess', label: 'Book 1', lines: 756 },
    { side: 'source', work: 'vergil.aeneid.tess', id: 'vergil.aeneid.part.2.tess', label: 'Book 2', lines: 804 },
    { side: 'target', work: 'ovid.metamorphoses.tess', id: 'ovid.metamorphoses.part.1.tess', label: 'Book 1', lines: 778 },
  ],
};
const params = { source: 'vergil.aeneid.tess', target: 'ovid.metamorphoses.tess', language: 'la', max_results: 5000 };

const show = (extra = {}) => render(
  <TooLargePanel sourceName="Vergil, Aeneid" targetName="Ovid, Metamorphoses"
    answer={{ ...answer, ...extra }} params={params} onChooseBook={() => {}} />);

describe('TooLargePanel', () => {
  it('shows nothing unless the server said too_large', () => {
    const { container } = render(
      <TooLargePanel sourceName="A" targetName="B" answer={{ line_pairs: 5 }} params={params} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('says the size in plain words and fills the book pickers from the answer', () => {
    show();
    expect(screen.getByText(/119 million line pairs/)).toBeInTheDocument();
    expect(screen.getByText(/would hold the server too long to run live/)).toBeInTheDocument();
    const source = screen.getByRole('combobox', { name: 'Source book' });
    expect(Array.from(source.options).map((o) => o.textContent)).toEqual(['Choose a book', 'Book 1', 'Book 2']);
    const target = screen.getByRole('combobox', { name: 'Target book' });
    expect(Array.from(target.options).map((o) => o.textContent)).toEqual(['Choose a book', 'Book 1']);
  });

  it('shows only the side that has books', () => {
    show({ books: answer.books.filter((b) => b.side === 'target') });
    expect(screen.queryByRole('combobox', { name: 'Source book' })).toBeNull();
    expect(screen.getByRole('combobox', { name: 'Target book' })).toBeInTheDocument();
  });

  it('choosing a book calls onChooseBook with the side and the book file', () => {
    const onChooseBook = vi.fn();
    render(<TooLargePanel sourceName="A" targetName="B" answer={answer} params={params}
      onChooseBook={onChooseBook} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Source book' }),
      { target: { value: 'vergil.aeneid.part.2.tess' } });
    expect(onChooseBook).toHaveBeenCalledWith('source', 'vergil.aeneid.part.2.tess');
  });

  it('submits the job with the settings and shows the place in line and the status link', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({
      status: 201,
      json: () => Promise.resolve({ id: 'abc123', status: 'queued', position: 3, retention_days: 14 }),
    })));
    show();
    expect(screen.queryByLabelText('Email address')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Prepare the whole comparison as a download' }));
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('/api/comparisons/jobs');
    expect(init.method).toBe('POST');
    const sent = JSON.parse(init.body);
    expect(sent).toMatchObject({ source: params.source, target: params.target, language: 'la' });
    expect(sent.settings.max_results).toBe(5000);
    expect(sent.email).toBeUndefined();
    await waitFor(() => expect(screen.getByText(/number 3 in line/)).toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'Check on it here' })).toHaveAttribute('href', '/comparisons/abc123');
    expect(screen.queryByRole('button', { name: /Prepare the whole comparison/ })).toBeNull();
  });

  it('offers the email box only when the site can send mail, and sends the address', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({
      status: 201, json: () => Promise.resolve({ id: 'zz9', status: 'queued', position: 1 }),
    })));
    show({ email_notice: true });
    await userEvent.type(screen.getByLabelText('Email address'), 'reader@example.edu');
    await userEvent.click(screen.getByRole('button', { name: 'Prepare the whole comparison as a download' }));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).email).toBe('reader@example.edu');
    await waitFor(() => expect(screen.getByText(/wait for the email/)).toBeInTheDocument());
  });

  it('shows the server message when the job is refused', async () => {
    global.fetch = vi.fn(() => Promise.resolve(mockResponse({
      ok: false, status: 429,
      json: () => Promise.resolve({ error: 'You already have 2 comparisons waiting.' }),
    })));
    show();
    await userEvent.click(screen.getByRole('button', { name: 'Prepare the whole comparison as a download' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('You already have 2 comparisons waiting.'));
    expect(screen.getByRole('button', { name: /Prepare the whole comparison/ })).not.toBeDisabled();
  });
});
