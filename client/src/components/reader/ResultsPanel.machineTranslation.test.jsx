/**
 * The Translation tab's "Translate by machine" button (2026-10-24): offered only
 * where no human translation covers the selection (or the aligned one is only
 * approximate), asks /api/translation/machine, and shows the one-line note with
 * the trial figure for the kind of text and a closed-by-default disclosure.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import ResultsPanel from './ResultsPanel';

const UNITS = [
  { ref: 'horace.odes.1.1', text: 'Maecenas atavis edite regibus' },
  { ref: 'horace.odes.1.2', text: 'o et praesidium et dulce decus meum' },
];

const NONE = { available: false, reason: 'No aligned open translation for this work.', external_links: [] };
const HUMAN = { available: true, text: 'Maecenas, sprung from kings', translator: 'Conington', approximate: false, external_links: [] };
const ROUGH = { ...HUMAN, approximate: true, note: 'Aligned in blocks.' };
const MACHINE = {
  available: true, model: 'GLM-5.2', lines: ['Maecenas, born of ancient kings', 'my protection and sweet glory'],
  kind: { language: 'la', language_name: 'Latin', form: 'verse' },
  reliability: { right: 16, nearly: 8, wrong: 1, of: 25 },
};

let calls;
function mockApi(translation, machine = { status: 200, body: MACHINE }) {
  calls = [];
  const reply = (status, body) => Promise.resolve({
    ok: status < 400, status, json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)), headers: { get: () => 'application/json' },
  });
  global.fetch = vi.fn((url) => {
    calls.push(String(url));
    if (String(url).startsWith('/api/translation/machine')) return reply(machine.status, machine.body);
    if (String(url).startsWith('/api/translation')) return reply(200, translation);
    return reply(200, { results: [] });
  });
}

const mount = () => render(
  <ResultsPanel selection={{ refStart: UNITS[0].ref, refEnd: UNITS[1].ref, startIdx: 0, endIdx: 1 }}
                language="la" work="horace.odes" units={UNITS} initialTab="translation" />);

afterEach(cleanup);
beforeEach(() => mockApi(NONE));

describe('Translate by machine', () => {
  it('is offered when no translation covers the passage', async () => {
    mount();
    expect(await screen.findByRole('button', { name: 'Translate by machine' })).toBeTruthy();
  });

  it('is not offered beside an aligned translation', async () => {
    mockApi(HUMAN);
    mount();
    await screen.findByText('Maecenas, sprung from kings');
    expect(screen.queryByRole('button', { name: 'Translate by machine' })).toBeNull();
  });

  it('is offered when the aligned translation is approximate', async () => {
    mockApi(ROUGH);
    mount();
    expect(await screen.findByRole('button', { name: 'Translate by machine' })).toBeTruthy();
  });

  it('calls the route and shows the lines and the note with the figure for the kind', async () => {
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Translate by machine' }));
    await screen.findByText('Maecenas, born of ancient kings');
    expect(screen.getByText('my protection and sweet glory')).toBeTruthy();
    const url = calls.find((c) => c.startsWith('/api/translation/machine'));
    expect(url).toContain('work=horace.odes');
    expect(decodeURIComponent(url)).toContain('refs=horace.odes.1.1|horace.odes.1.2');
    expect(screen.getByText(/Machine translation by GLM-5\.2, unreviewed\./)).toBeTruthy();
    expect(screen.getByText(/fully right for 16 of 25 Latin verse passages\./)).toBeTruthy();
  });

  it('opens and closes the disclosure, closed by default', async () => {
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Translate by machine' }));
    const toggle = await screen.findByRole('button', { name: 'What this means' });
    expect(screen.queryByTestId('mt-disclosure')).toBeNull();
    fireEvent.click(toggle);
    const text = screen.getByTestId('mt-disclosure').textContent;
    expect(text).toContain('16 were fully right, 8 nearly right and 1 wrong');
    expect(text).toContain('106 and 111 of the same 121 passages');
    fireEvent.click(toggle);
    expect(screen.queryByTestId('mt-disclosure')).toBeNull();
  });

  it('says the kind was not tested when the route sends no figure', async () => {
    mockApi(NONE, { status: 200, body: { ...MACHINE, reliability: null, kind: { language: 'ur', language_name: 'Urdu', form: 'verse' } } });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Translate by machine' }));
    await screen.findByText(/We did not test it on Urdu verse\./);
  });

  it('shows the plain message on a 429', async () => {
    mockApi(NONE, { status: 429, body: { available: false, reason: 'The machine translation service is busy. Please try again in a minute.' } });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Translate by machine' }));
    await waitFor(() => expect(screen.getByText(/service is busy/)).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Translate by machine' })).toBeTruthy();
  });
});

describe('Translate by machine, when the aligned translation is requested again', () => {
  it('keeps a machine translation already shown', async () => {
    mockApi(NONE);
    const props = { selection: { refStart: UNITS[0].ref, refEnd: UNITS[1].ref, startIdx: 0, endIdx: 1 },
                    language: 'la', work: 'horace.odes', initialTab: 'translation' };
    const { rerender } = render(<ResultsPanel {...props} units={UNITS} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Translate by machine' }));
    await screen.findByText('Maecenas, born of ancient kings');
    rerender(<ResultsPanel {...props} units={[...UNITS]} />);
    await waitFor(() => expect(calls.filter((c) => c.startsWith('/api/translation?')).length).toBeGreaterThan(1));
    expect(screen.getByText('Maecenas, born of ancient kings')).toBeTruthy();
  });
});
