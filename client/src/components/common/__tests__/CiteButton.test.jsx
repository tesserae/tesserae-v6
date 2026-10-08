/**
 * The Cite popup also carries "Report a problem with this result" (requests
 * workflow, 2026-10-08), living in CiteButton itself so every result card
 * that already has Cite gets it without its own change.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CiteButton from '../CiteButton';

afterEach(() => { delete global.fetch; });

const FINDING = {
  kind: 'fusion search', source: 'Hafez, Diwan 1626', target: 'Ghalib, Diwan 264.30',
  language: 'Persian', score: 7.2, channels: 'semantic, shared vocabulary',
  corpusVersion: '2026-10-01',
};

describe('CiteButton — report a problem', () => {
  it('opens the request dialog with the finding as context', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) }));
    const user = userEvent.setup();
    render(<CiteButton finding={FINDING} />);

    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await user.click(screen.getByRole('button', { name: /report a problem with this result/i }));

    expect(screen.getByRole('dialog', { name: /report a problem with this result/i })).toBeTruthy();
    expect(screen.getByText('Hafez, Diwan 1626')).toBeTruthy();
    expect(screen.getByText('Ghalib, Diwan 264.30')).toBeTruthy();
    expect(screen.getByText('Persian')).toBeTruthy();
  });

  it('closes the citation popover when the report dialog opens', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) }));
    const user = userEvent.setup();
    render(<CiteButton finding={FINDING} />);
    await user.click(screen.getByRole('button', { name: 'Cite' }));
    await user.click(screen.getByRole('button', { name: /report a problem with this result/i }));
    expect(screen.queryByLabelText('Citation text')).toBeNull();
  });
});
