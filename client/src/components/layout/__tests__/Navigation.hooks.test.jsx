import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import Navigation from '../Navigation';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Navigation — hooks run in the same order whether or not the menu is locked to admin', () => {
  it('switches from the admin-only menu to the full menu without a hooks error', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    const props = { pageType: 'search', setPageType: () => {}, activeTab: 'la', setActiveTab: () => {} };
    const { rerender } = render(<Navigation {...props} lockedToAdmin />);
    expect(screen.queryByRole('button', { name: /More/ })).toBeNull();
    rerender(<Navigation {...props} lockedToAdmin={false} />);
    expect(screen.getByRole('button', { name: /More/ })).toBeTruthy();
    const hookErrors = errors.mock.calls.filter((c) => String(c[0]).includes('Rendered more hooks') || String(c[0]).includes('change in the order of Hooks'));
    expect(hookErrors).toHaveLength(0);
  });
});
