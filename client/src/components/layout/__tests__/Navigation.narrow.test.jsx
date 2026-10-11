import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, cleanup, render, screen, fireEvent } from '@testing-library/react';
import Navigation from '../Navigation';
import { installPhone } from '../../../test/phone';

const noop = () => {};
let env;

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ documents_enabled: true }) }));
  env = installPhone(true, true);
});
afterEach(() => { cleanup(); env.restore(); delete global.fetch; });

const renderNav = (props = {}) => render(
  <Navigation pageType="search" setPageType={noop} activeTab="la" setActiveTab={noop} {...props} />
);

describe('the main menu on a narrow screen', () => {
  it('shows one compact view button and no pressed pair', () => {
    renderNav();
    const btn = screen.getByRole('button', { name: /Literature/ });
    expect(btn).toHaveAttribute('aria-haspopup', 'menu');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: 'History' })).toBeNull();
    expect(document.querySelectorAll('[aria-pressed]').length).toBe(0);
    expect(screen.queryByRole('button', { name: 'Collections' })).toBeNull();
  });

  it('lists Literature, History and Collections, with the current view checked', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Literature/ }));
    expect(screen.getByRole('menuitemradio', { name: 'Literature' })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('menuitemradio', { name: 'History' })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('menuitem', { name: /Collections/ })).toBeInTheDocument();
  });

  it('choosing History sets the view and tells the app', () => {
    const onViewChange = vi.fn();
    renderNav({ onViewChange });
    fireEvent.click(screen.getByRole('button', { name: /Literature/ }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'History' }));
    expect(onViewChange).toHaveBeenCalledWith('history');
    expect(screen.queryByRole('menu', { name: 'View' })).toBeNull();
    expect(screen.getByRole('button', { name: /History/ })).toBeInTheDocument();
  });

  it('choosing Collections closes the menu and opens the Collections panel', () => {
    renderNav();
    fireEvent.click(screen.getByRole('button', { name: /Literature/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: /Collections/ }));
    expect(screen.queryByRole('menu', { name: 'View' })).toBeNull();
    expect(screen.getByRole('dialog', { name: 'Collections' })).toBeInTheDocument();
  });

  it('closes on Escape and on a tap outside', () => {
    renderNav();
    const btn = screen.getByRole('button', { name: /Literature/ });
    fireEvent.click(btn);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu', { name: 'View' })).toBeNull();
    fireEvent.click(btn);
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('menu', { name: 'View' })).toBeNull();
  });

  it('leaves the beta superscript off the tabs', () => {
    renderNav();
    expect(screen.getByRole('button', { name: 'Read' })).toBeInTheDocument();
    expect(screen.queryByText(/^beta$/i)).toBeNull();
  });

  it('puts the switch back when the screen widens', () => {
    renderNav();
    act(() => env.setNarrow(false));
    expect(screen.getByRole('button', { name: 'History' })).toHaveAttribute('aria-pressed', 'false');
  });
});
