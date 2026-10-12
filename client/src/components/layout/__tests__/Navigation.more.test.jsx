import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import Navigation from '../Navigation';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Navigation — the More menu opens where it can be seen', () => {
  it('opens on click as a fixed-position menu and picks a page', () => {
    const setPageType = vi.fn();
    render(<Navigation pageType="search" setPageType={setPageType} activeTab="la" setActiveTab={() => {}} />);
    const more = screen.getByRole('button', { name: /More/ });
    expect(screen.queryByTestId('more-menu')).toBeNull();
    fireEvent.click(more);
    const menu = screen.getByTestId('more-menu');
    // Fixed to the viewport: a menu positioned inside the scrolling tab row
    // was clipped by it and never seen.
    expect(menu.style.position).toBe('fixed');
    const items = screen.getAllByRole('menuitem');
    expect(items.length).toBeGreaterThan(0);
    fireEvent.click(items[0]);
    expect(setPageType).toHaveBeenCalled();
    expect(screen.queryByTestId('more-menu')).toBeNull();
  });
  it('closes when the page scrolls', () => {
    render(<Navigation pageType="search" setPageType={() => {}} activeTab="la" setActiveTab={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /More/ }));
    expect(screen.getByTestId('more-menu')).toBeTruthy();
    fireEvent.scroll(window);
    expect(screen.queryByTestId('more-menu')).toBeNull();
  });
});
