import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PathsSection from '../PathsSection';

describe('PathsSection', () => {
  it('renders the figures', () => {
    render(<PathsSection paths={{
      available: true, days: 30, visits: 3, page_views: 7, pages_per_visit_median: 2, one_page_visits: 1,
      visits_by_day: [{ date: '2026-10-09', visits: 3, page_views: 7 }],
      entry_pages: [{ page: 'search', visits: 2 }],
      top_paths: [{ path: 'search > read', visits: 2 }],
      pages_reached: [{ page: 'read', visits: 2 }],
      countries: [{ country: 'France', visits: 1 }],
      referrer_hosts: [{ host: 'example.org', visits: 1 }],
    }} />);
    expect(screen.getByText('Paths through the site (last 30 days)')).toBeTruthy();
    expect(screen.getByText('search > read')).toBeTruthy();
    expect(screen.getByText('France')).toBeTruthy();
    expect(screen.getByText('example.org')).toBeTruthy();
    expect(screen.getByText('Median pages per visit')).toBeTruthy();
  });

  it('says so when the table is missing', () => {
    render(<PathsSection paths={{ available: false }} />);
    expect(screen.getByText(/not being recorded yet/)).toBeTruthy();
  });
});
