import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import EventCoins from '../EventCoins';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('an event\'s Coins tab', () => {
  it('lists the coins with their accounts, marks the ones naming the place, and shows no confidence level', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({
        available: true, label: 'Coin types struck from 3 years before the event to 5 after it.',
        results: [{ coin_id: 'ocre:ric.1(2).aug.265A', description: 'Obverse: Head of Octavian. Reverse: Trophy on prow.',
          reverse_description: 'Trophy, rudder and anchor on base, all on prow.', n_types: 1,
          gist: 'It celebrates his naval victory over Antony and Cleopatra at Actium in 31 BCE.',
          names_event_place: true, confidence: { level: 'higher' }, coin_url: '/coins/x' }],
      }),
    });
    render(<EventCoins eventId="Q160387" />);
    expect(await screen.findByTestId('event-coins')).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/events/Q160387/coins');
    expect(screen.getByTestId('coin-gist').textContent).toMatch(/Actium in 31 BCE/);
    expect(screen.getByTestId('names-place')).toBeTruthy();
    expect(screen.queryByText('Closer match')).toBeNull();
  });

  it('says why when nothing can be shown', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, status: 200, json: async () => ({ available: false, results: [], reason: 'This event has no date, so no coins can be placed beside it.' }),
    });
    render(<EventCoins eventId="Q1" />);
    expect(await screen.findByText(/no date/)).toBeTruthy();
  });
});

describe('the Coins tab count', () => {
  it('counts the coins shown, and gives none while loading or when none can be shown', async () => {
    const { eventCoinsCount } = await import('../EventCoins');
    expect(eventCoinsCount({ data: { available: true, results: [{}, {}, {}] } })).toBe(3);
    expect(eventCoinsCount({ data: null })).toBeUndefined();
    expect(eventCoinsCount({ data: { available: false, results: [] } })).toBeUndefined();
  });
});
