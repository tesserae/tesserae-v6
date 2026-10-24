import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import YourComparisons from '../YourComparisons';
import { mockResponse } from '../../../test/mockResponse';

afterEach(() => { delete global.fetch; });

const serve = (body) => {
  global.fetch = vi.fn(() => Promise.resolve(mockResponse({ json: () => Promise.resolve(body) })));
};

describe('YourComparisons', () => {
  it('shows nothing when the visitor has no jobs', async () => {
    serve({ jobs: [] });
    const { container } = render(<YourComparisons />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(global.fetch.mock.calls[0][0]).toBe('/api/comparisons/jobs');
    expect(container).toBeEmptyDOMElement();
  });

  it('lists each job with its status and link, and a download for a finished one', async () => {
    serve({ jobs: [
      { id: 'aaa111', status: 'done', source: 'a.tess', target: 'b.tess', created: '2026-10-24T09:00:00',
        download_url: '/api/comparisons/jobs/aaa111/download' },
      { id: 'bbb222', status: 'queued', position: 2, source: 'c.tess', target: 'd.tess', created: '2026-10-24T10:00:00' },
      { id: 'ccc333', status: 'failed', source: 'e.tess', target: 'f.tess' },
    ] });
    render(<YourComparisons labelFor={(id) => id.replace('.tess', '').toUpperCase()} />);
    const region = await screen.findByRole('region', { name: 'Your prepared comparisons' });
    expect(region).toHaveTextContent('A and B: ready');
    expect(region).toHaveTextContent('C and D: waiting, number 2 in line');
    expect(region).toHaveTextContent('E and F: did not finish');
    expect(screen.getByRole('link', { name: 'A and B' })).toHaveAttribute('href', '/comparisons/aaa111');
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('href', '/api/comparisons/jobs/aaa111/download');
  });

  it('reads again when refreshKey changes', async () => {
    serve({ jobs: [] });
    const { rerender } = render(<YourComparisons refreshKey={0} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    rerender(<YourComparisons refreshKey={1} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  });

  it('shows nothing when the request fails', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('down')));
    const { container } = render(<YourComparisons />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
