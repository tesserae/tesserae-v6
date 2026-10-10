import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CollectionsControl from '../CollectionsControl';

beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });

describe('CollectionsControl', () => {
  it('shows the profile, picks another and flips a switch', () => {
    render(<CollectionsControl />);
    fireEvent.click(screen.getByRole('button', { name: /Collections: Literary/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Historical' }));
    expect(screen.getByRole('checkbox', { name: /Papyri/ }).checked).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: /Papyri/ }));
    expect(screen.getByRole('button', { name: /Collections: Custom/ })).toBeTruthy();
  });

  it('lists objects and coins as switchable', () => {
    render(<CollectionsControl />);
    fireEvent.click(screen.getByRole('button', { name: /Collections/ }));
    expect(screen.getByRole('checkbox', { name: /Objects/ }).disabled).toBe(false);
    expect(screen.getByRole('checkbox', { name: /Coins/ }).disabled).toBe(false);
  });
});
