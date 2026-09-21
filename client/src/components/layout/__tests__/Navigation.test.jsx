import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import Navigation from '../Navigation';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const noop = () => {};

const renderNav = (props = {}) =>
  render(
    <Navigation
      pageType="search"
      setPageType={noop}
      activeTab="la"
      setActiveTab={noop}
      {...props}
    />
  );

describe('Navigation — selected state is announced, not just colored', () => {
  it('marks the active main tab with aria-current="page" and leaves others unmarked', () => {
    renderNav({ pageType: 'browse' });
    expect(screen.getByRole('button', { name: 'Browse Corpus' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: 'Search' })).not.toHaveAttribute('aria-current');
  });

  it('marks the active language tab with aria-current and leaves others unmarked', () => {
    renderNav({ pageType: 'search', activeTab: 'grc' });
    expect(screen.getByRole('button', { name: 'Greek' })).toHaveAttribute('aria-current');
    expect(screen.getByRole('button', { name: 'Latin' })).not.toHaveAttribute('aria-current');
  });

  it('gives the active main tab a heavier font weight, not just a color change', () => {
    renderNav({ pageType: 'browse' });
    const active = screen.getByRole('button', { name: 'Browse Corpus' });
    const inactive = screen.getByRole('button', { name: 'Search' });
    expect(active.className).toMatch(/font-semibold/);
    expect(inactive.className).not.toMatch(/font-semibold/);
  });

  it('marks the admin panel button as the current page when locked to admin', () => {
    render(
      <Navigation
        pageType="admin"
        setPageType={noop}
        activeTab="la"
        setActiveTab={noop}
        lockedToAdmin
        onAdminLogout={noop}
      />
    );
    expect(screen.getByRole('button', { name: 'Admin Panel' })).toHaveAttribute('aria-current', 'page');
  });
});
