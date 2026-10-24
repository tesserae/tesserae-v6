import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ComparisonJobPage, { jobIdFromPath } from '../ComparisonJobPage';
import { mockResponse } from '../../../test/mockResponse';

afterEach(() => { delete global.fetch; vi.useRealTimers(); });

const base = { id: 'abc123', source: 'vergil.aeneid.tess', target: 'ovid.metamorphoses.tess',
  language: 'la', retention_days: 14 };

function serve(...bodies) {
  let i = 0;
  global.fetch = vi.fn(() => {
    const body = bodies[Math.min(i, bodies.length - 1)];
    i += 1;
    return Promise.resolve(mockResponse({ json: () => Promise.resolve(body) }));
  });
}

describe('ComparisonJobPage', () => {
  it('reads the job id from the address', () => {
    expect(jobIdFromPath('/comparisons/abc123')).toBe('abc123');
    expect(jobIdFromPath('/comparisons/abc123/')).toBe('abc123');
    expect(jobIdFromPath('/comparisons/')).toBe('');
    expect(jobIdFromPath('/help')).toBe('');
  });

  it('shows the place in line for a queued job and asks the status route', async () => {
    serve({ ...base, status: 'queued', position: 2 });
    render(<ComparisonJobPage jobId="abc123" />);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('It is number 2 in line.'));
    expect(global.fetch.mock.calls[0][0]).toBe('/api/comparisons/jobs/abc123');
  });

  it('says it is running', async () => {
    serve({ ...base, status: 'running' });
    render(<ComparisonJobPage jobId="abc123" />);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('preparing it now'));
  });

  it('shows the download link when the file is ready, and stops asking', async () => {
    serve({ ...base, status: 'done', rows: 5000, download_url: '/api/comparisons/jobs/abc123/download' });
    render(<ComparisonJobPage jobId="abc123" />);
    const link = await screen.findByRole('link', { name: 'Download the file' });
    expect(link).toHaveAttribute('href', '/api/comparisons/jobs/abc123/download');
    expect(screen.getByText(/5000 parallels/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'the comparison page' }).getAttribute('href'))
      .toContain('source=vergil.aeneid.tess');
    await new Promise((r) => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('shows a failure and an unknown job', async () => {
    serve({ ...base, status: 'failed', error: 'The comparison did not finish.' });
    const { unmount } = render(<ComparisonJobPage jobId="abc123" />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('did not finish'));
    unmount();
    serve({ error: 'No such comparison. Files are kept 14 days.' });
    render(<ComparisonJobPage jobId="gone99" />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('No such comparison'));
  });

  it('keeps asking every ten seconds while the job waits', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    serve({ ...base, status: 'queued', position: 1 }, { ...base, status: 'running' },
      { ...base, status: 'done', rows: 1, download_url: '/x' });
    render(<ComparisonJobPage jobId="abc123" />);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('next in line'));
    await vi.advanceTimersByTimeAsync(10000);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('preparing it now'));
    await vi.advanceTimersByTimeAsync(10000);
    await screen.findByRole('link', { name: 'Download the file' });
  });
});
