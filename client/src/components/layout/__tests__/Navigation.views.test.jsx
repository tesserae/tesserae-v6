import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import Navigation from '../Navigation';

const noop = () => {};

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ documents_enabled: true }) }));
});
afterEach(() => { cleanup(); delete global.fetch; });

const renderNav = (props = {}) => render(
  <Navigation pageType="search" setPageType={noop} activeTab="la" setActiveTab={noop} {...props} />
);

// The names of the main-menu buttons, in order, after the view switch and the Collections button.
const menuNames = () => screen.getAllByRole('button').map((b) => b.textContent.replace(/beta$/i, '').trim());

describe('the view switch', () => {
  it('shows both views and marks Literature as pressed for a new visitor', () => {
    renderNav();
    expect(screen.getByRole('button', { name: 'Literature' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'History' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('stands before the Collections button, which is a plain secondary button', () => {
    renderNav();
    const names = menuNames();
    expect(names.slice(0, 3)).toEqual(['Literature', 'History', 'Collections']);
    expect(screen.getByRole('button', { name: 'Collections' }).className).toMatch(/text-xs/);
  });

  it('switches to History, marks it, and tells the app', () => {
    const onViewChange = vi.fn();
    renderNav({ onViewChange });
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(onViewChange).toHaveBeenCalledWith('history');
    expect(screen.getByRole('button', { name: 'History' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Literature' })).toHaveAttribute('aria-pressed', 'false');
  });
});

describe('the menu order follows the view', () => {
  it('Literature leads with Search then Read', () => {
    renderNav();
    const names = menuNames();
    expect(names.indexOf('Search')).toBeLessThan(names.indexOf('Read'));
    expect(names.indexOf('Read')).toBeLessThan(names.indexOf('Theme Search'));
  });

  it('History leads with Read then Events, and Search comes after Theme Search', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    const names = menuNames();
    expect(names.indexOf('Read')).toBeLessThan(names.indexOf('Events'));
    expect(names.indexOf('Events')).toBeLessThan(names.indexOf('Theme Search'));
    expect(names.indexOf('Theme Search')).toBeLessThan(names.indexOf('Search'));
    expect(names.indexOf('Search')).toBeLessThan(names.indexOf('Coins'));
  });
});
