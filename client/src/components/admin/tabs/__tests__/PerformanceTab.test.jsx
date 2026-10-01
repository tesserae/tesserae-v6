/**
 * PerformanceTab — regression tests for issue #148.
 *
 * Two bugs fixed together:
 *
 * 1. Auto-sync was a one-shot `initialLoaded` gate: sliders only populated on
 *    the very first poll, so a server-side change (another admin saves, a reset
 *    fires) was invisible until page refresh.  Fixed with an `isDirty` flag:
 *    polls update the controls whenever the admin has no unsaved edits; a touch
 *    on any control suspends live updates until Apply or Reset clears the flag.
 *
 * 2. When `active_searches > max_searches` (the cap was lowered mid-run) the
 *    card showed "5 / 2" with a full-red bar and no explanation.  Fixed by
 *    detecting the draining state and showing a chip + note.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PerformanceTab from '../PerformanceTab';

// ── helpers ──────────────────────────────────────────────────────────────────

const makeStatus = (overrides = {}) => ({
  max_searches: 2,
  memory_threshold_gb: 8,
  queue_timeout: 300,
  queue_poll_interval: 2,
  emergency_ram_floor_gb: 3.0,
  reaper_enabled: false,
  active_searches: 0,
  available_memory_gb: 16,
  emergency_active: false,
  stress_test_mode: false,
  max_emergency_floor_gb: 12.8,
  total_memory_gb: 16,
  reaper_status: { active: false, reap_count: 0 },
  defaults: {
    max_searches: 2,
    memory_threshold_gb: 8,
    queue_timeout: 300,
    queue_poll_interval: 2,
    emergency_ram_floor_gb: 3.0,
    reaper_enabled: false,
  },
  ...overrides,
});

// Builds a fetch mock that returns the given status for GET and the optional
// putResponse (else same status) for PUT.
const makeFetch = (status, putResponse = null) => vi.fn((url, opts = {}) => {
  if (opts.method === 'PUT' && url === '/api/admin/concurrency') {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(putResponse ?? status),
    });
  }
  if (url === '/api/admin/concurrency') {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(status) });
  }
  if (url.includes('/api/admin/concurrency/active')) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ active_searches: [] }) });
  }
  return Promise.resolve({ ok: false, json: () => Promise.resolve({ error: 'unexpected url' }) });
});

// Only fake setInterval/clearInterval so the poll cycle is controllable while
// userEvent's internal setTimeout calls remain on real timers (avoiding hangs).
const setupFakeInterval = () => vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });

// Returns a maxSearches badge element — the red badge in the slider label that
// shows the currently configured value. Less fragile than getByText('7').
const getMaxSearchesBadge = () =>
  within(screen.getByText(/Max Simultaneous Searches/).closest('label')).getByText(/^\d+$/);

// ── draining state ────────────────────────────────────────────────────────────

describe('PerformanceTab — draining state (issue #148)', () => {
  beforeEach(() => { vi.spyOn(window, 'confirm').mockReturnValue(false); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('shows the "draining" chip when active > max', async () => {
    global.fetch = makeFetch(makeStatus({ active_searches: 5, max_searches: 2 }));
    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByText('draining')).toBeTruthy());
    expect(screen.getByText(/running searches will finish/i)).toBeTruthy();
  });

  it('hides the chip when active is at or below the cap', async () => {
    global.fetch = makeFetch(makeStatus({ active_searches: 1, max_searches: 2 }));
    render(<PerformanceTab />);
    // "% capacity" only renders once status is loaded — assert absence after load.
    await waitFor(() => expect(screen.getByText(/% capacity/i)).toBeTruthy());
    expect(screen.queryByText('draining')).toBeNull();
  });

  it('hides the chip when there are zero active searches', async () => {
    global.fetch = makeFetch(makeStatus({ active_searches: 0, max_searches: 2 }));
    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByText(/% capacity/i)).toBeTruthy());
    expect(screen.queryByText('draining')).toBeNull();
  });
});

// ── auto-sync sliders ─────────────────────────────────────────────────────────

describe('PerformanceTab — auto-sync sliders (issue #148)', () => {
  beforeEach(() => {
    setupFakeInterval();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('populates controls from the initial poll', async () => {
    global.fetch = makeFetch(makeStatus({ max_searches: 7, queue_timeout: 180 }));
    render(<PerformanceTab />);
    // Wait for the fetch promise (microtasks) to resolve and state to update.
    await waitFor(() => expect(getMaxSearchesBadge().textContent).toBe('7'));
    expect(screen.getByDisplayValue('180')).toBeTruthy();
  });

  it('re-syncs controls on the next poll when the form is clean', async () => {
    let serverStatus = makeStatus({ max_searches: 2, queue_timeout: 300 });
    global.fetch = vi.fn((url, opts = {}) => {
      if (opts.method === 'PUT') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      if (url === '/api/admin/concurrency') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ active_searches: [] }) });
    });

    render(<PerformanceTab />);
    // Wait for initial data: "Timeout: 300s" only appears when status loaded.
    await waitFor(() => expect(screen.getByText(/Timeout: 300s/)).toBeTruthy());

    // Server is updated by another admin.
    serverStatus = makeStatus({ max_searches: 9, queue_timeout: 600 });
    // Advance past the 5-second poll interval; the interval callback fires.
    await act(async () => { await vi.advanceTimersByTimeAsync(5001); });

    // Badge and timeout input both reflect the new server values.
    await waitFor(() => expect(getMaxSearchesBadge().textContent).toBe('9'));
    expect(screen.getByDisplayValue('600')).toBeTruthy();
  });

  it('holds back a poll update while the admin has unsaved edits', async () => {
    let serverStatus = makeStatus({ queue_timeout: 300 });
    global.fetch = vi.fn((url, opts = {}) => {
      if (opts.method === 'PUT') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      if (url === '/api/admin/concurrency') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ active_searches: [] }) });
    });

    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByDisplayValue('300')).toBeTruthy());

    // Admin types a new value — form becomes dirty.
    const input = screen.getByDisplayValue('300');
    await userEvent.clear(input);
    await userEvent.type(input, '120');
    expect(screen.getByText(/unsaved changes/i)).toBeTruthy();

    // Server now has a different value; poll fires.
    serverStatus = makeStatus({ queue_timeout: 600 });
    await act(async () => { await vi.advanceTimersByTimeAsync(5001); });

    // User's local edit is NOT overwritten (isDirty guards the sync).
    await waitFor(() => expect(screen.getByDisplayValue('120')).toBeTruthy());
    expect(screen.queryByDisplayValue('600')).toBeNull();
  });

  it('clears the dirty flag and resumes auto-sync after a successful save', async () => {
    let serverStatus = makeStatus({ queue_timeout: 300 });
    global.fetch = vi.fn((url, opts = {}) => {
      if (opts.method === 'PUT') {
        serverStatus = makeStatus({ queue_timeout: 120 });
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      if (url === '/api/admin/concurrency') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(serverStatus) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ active_searches: [] }) });
    });

    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByDisplayValue('300')).toBeTruthy());

    // Edit, then save.
    const input = screen.getByDisplayValue('300');
    await userEvent.clear(input);
    await userEvent.type(input, '120');
    expect(screen.getByText(/unsaved changes/i)).toBeTruthy();

    await userEvent.click(screen.getByRole('button', { name: /apply changes/i }));
    await waitFor(() => expect(screen.queryByText(/unsaved changes/i)).toBeNull());

    // Polls resume — server returns new value and it syncs through.
    serverStatus = makeStatus({ queue_timeout: 450 });
    await act(async () => { await vi.advanceTimersByTimeAsync(5001); });
    await waitFor(() => expect(screen.getByDisplayValue('450')).toBeTruthy());
  });
});

// ── unsaved changes indicator ─────────────────────────────────────────────────

describe('PerformanceTab — unsaved changes indicator (issue #148)', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    global.fetch = makeFetch(makeStatus());
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('is hidden when the form has not been touched', async () => {
    render(<PerformanceTab />);
    // Wait until the component finishes loading, then confirm the indicator is absent.
    await waitFor(() => expect(screen.getByText(/% capacity/i)).toBeTruthy());
    expect(screen.queryByText(/unsaved changes/i)).toBeNull();
  });

  it('appears after editing the queue timeout input', async () => {
    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByDisplayValue('300')).toBeTruthy());

    const input = screen.getByDisplayValue('300');
    await userEvent.clear(input);
    await userEvent.type(input, '600');

    expect(screen.getByText(/unsaved changes/i)).toBeTruthy();
  });

  it('appears after moving the max searches slider', async () => {
    render(<PerformanceTab />);
    await waitFor(() => expect(screen.getByRole('slider')).toBeTruthy());

    const slider = screen.getByRole('slider');
    // jsdom cannot drag a slider, so dispatch a synthetic change event.
    await act(async () => {
      Object.defineProperty(slider, 'value', { value: '5', writable: true, configurable: true });
      slider.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // The onChange handler calls setIsDirty(true) — indicator appears.
    await waitFor(() => expect(screen.getByText(/unsaved changes/i)).toBeTruthy());
  });
});
