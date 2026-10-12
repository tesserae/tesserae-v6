import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import SearchProgress from '../SearchProgress';

afterEach(() => { vi.useRealTimers(); });

describe('SearchProgress', () => {
  it('shows the spinner and the text at once, and a whole-seconds clock after the first second', () => {
    vi.useFakeTimers();
    render(<SearchProgress text="Comparing your description against every indexed passage…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Comparing your description');
    expect(screen.queryByTestId('search-progress-clock')).toBeNull();
    act(() => { vi.advanceTimersByTime(3100); });
    expect(screen.getByTestId('search-progress-clock')).toHaveTextContent('3s');
    expect(screen.getByTestId('search-progress-clock').textContent).not.toContain('.');
  });
});
