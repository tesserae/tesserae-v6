import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import AnalyticsTab from '../AnalyticsTab';

const usage = {
  available: true,
  built_at: '2026-10-10T03:10:00+00:00',
  log_first_month: '2026-09',
  log_last_month: '2026-10',
  months: [
    { month: '2026-09', app_loads: 698, api_users: 503, requests: 88951, features: { 'Search page': 400 } },
    { month: '2026-10', app_loads: 247, api_users: 204, requests: 32764, features: { 'Search page': 150 } },
  ],
  connector_addresses_by_month: {},
  referrers: [{ host: 'www.google.com', count: 12 }],
  notes: ['Counts are of network addresses, not people.'],
};

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, text: () => Promise.resolve(JSON.stringify({})) }));
});

describe('AnalyticsTab visitors section', () => {
  it('renders the months table', async () => {
    render(<AnalyticsTab usage={usage} />);
    expect(await screen.findByText('Visitors (from the web server log)')).toBeTruthy();
    expect(screen.getByText('698')).toBeTruthy();
    expect(screen.getByText('88951')).toBeTruthy();
    expect(screen.getByText('www.google.com')).toBeTruthy();
  });

  it('says the summary is not built when unavailable', async () => {
    render(<AnalyticsTab usage={{ available: false, reason: 'x' }} />);
    expect(await screen.findByText(/has not been built yet/)).toBeTruthy();
    expect(screen.getByText(/build_usage_stats\.py/)).toBeTruthy();
  });
});

describe('AnalyticsTab when the server answers with an error page', () => {
  it('shows a readable message and keeps the page standing', async () => {
    global.fetch = vi.fn(() => Promise.resolve({
      ok: false, status: 502, text: () => Promise.resolve('<html><body>502 Bad Gateway</body></html>'),
    }));
    render(<AnalyticsTab usage={null} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/502 from \/api\/admin\/analytics: <html>/);
    expect(screen.getByText('Search Analytics')).toBeTruthy();
  });
});
