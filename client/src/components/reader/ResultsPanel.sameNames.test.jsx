/**
 * "Same people and places" (research/specs/2026-10-07_names_panel_spec.md):
 * a second Similar Passages grouping, by shared rare proper names, behind the
 * page-level ?names=1 flag. Covers both halves of the acceptance check:
 * flag-off rendering is untouched, and flag-on rendering shows two sections,
 * shared names on the cards that carry them, and the weak group collapsed.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ResultsPanel from './ResultsPanel';

function mount(props = {}) {
  const onOpenPassage = vi.fn();
  render(
    <ResultsPanel
      selection={{ refStart: 'curt. hist. 3.1.1', refEnd: 'curt. hist. 3.1.4',
                   startIdx: 0, endIdx: 0 }}
      language="la"
      work="curtius_rufus.historiae_alexandri_magni.part.3.tess"
      units={[]}
      onOpenPassage={onOpenPassage}
      initialTab="similar"
      {...props}
    />
  );
  return { onOpenPassage };
}

let sent;

const SCENE_RESULT = {
  id: 'scene1', language: 'la', work: 'claudian.in_eutropium',
  display_name: 'Claudian, In Eutropium', ref_start: '2.255',
  score: 0.72, gist: 'A general marches east.',
};

const NAMES_RESULT = {
  id: 'arrian:fine:7', language: 'grc', work: 'arrian.anabasis',
  display_name: 'Arrian, Anabasis', ref_start: '1.28.7',
  score: 0.93, gist: 'Alexander takes Celaenae.',
  shared_names: ['Celaenae', 'Marsyas'],
};

const COMMENTARY_RESULT = {
  id: 'serv:fine:1', language: 'la', work: 'servius.in_aeneidem',
  display_name: 'Servius, Commentary on the Aeneid', ref_start: '1.1',
  score: 0.55, gist: 'A note on the same place-name.',
  shared_names: ['Celaenae'],
};

function withSameNames(weak) {
  return {
    source: { id: 'src', work: 'curtius_rufus.historiae_alexandri_magni.part.3',
              display_name: 'Curtius Rufus, Historiae Alexandri Magni, Book 3' },
    results: [SCENE_RESULT],
    confidence: { top: 0.72, baseline: 0.4, lift: 0.32 },
    same_names: {
      results: [NAMES_RESULT],
      commentaries: [COMMENTARY_RESULT],
      strength: weak ? 0.2 : 2.3,
      weak,
    },
  };
}

beforeEach(() => {
  sent = null;
});

afterEach(() => {
  window.history.pushState({}, '', '/');
});

describe('with ?names=0, the tab is the plain list', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/reader?names=0');
    global.fetch = vi.fn((url) => {
      sent = url;
      return Promise.resolve({
        headers: { get: () => 'application/json' }, ok: true,
        json: () => Promise.resolve(withSameNames(false)),
      });
    });
  });

  it('does not ask the server for same_names', async () => {
    mount();
    await waitFor(() => expect(sent).toBeTruthy());
    expect(sent).not.toContain('same_names');
  });

  it('shows only the flat, content-ranked list -- no section headers', async () => {
    mount();
    expect(await screen.findByText('Claudian, In Eutropium')).toBeTruthy();
    expect(screen.queryByText(/Same people and places/)).toBeNull();
    expect(screen.queryByText(/Same kind of scene/)).toBeNull();
    expect(screen.queryByText(/Shared names/)).toBeNull();
    // Even though the stubbed response happens to carry a same_names block
    // (the server would never send one without the request flag), the
    // panel must not act on it when the page itself has no ?names=1.
    expect(screen.queryByText('Arrian, Anabasis')).toBeNull();
  });
});

describe('by default, same_names present and not weak', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/reader');
    global.fetch = vi.fn((url) => {
      sent = url;
      return Promise.resolve({
        headers: { get: () => 'application/json' }, ok: true,
        json: () => Promise.resolve(withSameNames(false)),
      });
    });
  });

  it('asks the server for same_names', async () => {
    mount();
    await waitFor(() => expect(sent).toBeTruthy());
    expect(sent).toContain('same_names=1');
  });

  it('shows two section headers', async () => {
    mount();
    expect(await screen.findByText(/Same people and places/)).toBeTruthy();
    expect(await screen.findByText(/Same kind of scene/)).toBeTruthy();
  });

  it('shows the names-group card with its shared names, open by default', async () => {
    mount();
    expect(await screen.findByText('Arrian, Anabasis')).toBeTruthy();
    expect(await screen.findByText(/Shared names: Celaenae, Marsyas/)).toBeTruthy();
  });

  it('keeps the scene group as its own section, open by default', async () => {
    mount();
    expect(await screen.findByText('Claudian, In Eutropium')).toBeTruthy();
  });

  it('shows the commentary line quietly, collapsed until clicked', async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByText(/Same people and places/);
    const line = await screen.findByText(/Commentaries: Servius, Commentary on the Aeneid, 1 passage/);
    expect(screen.queryByText('Servius, Commentary on the Aeneid')).toBeNull();
    await user.click(line);
    expect(await screen.findByText('Servius, Commentary on the Aeneid')).toBeTruthy();
  });
});

describe('by default, with a weak same_names group', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/reader');
    global.fetch = vi.fn((url) => {
      sent = url;
      return Promise.resolve({
        headers: { get: () => 'application/json' }, ok: true,
        json: () => Promise.resolve(withSameNames(true)),
      });
    });
  });

  it('starts the first section collapsed with the weak note', async () => {
    const user = userEvent.setup();
    mount();
    expect(await screen.findByText('Few distinctive names in this passage')).toBeTruthy();
    expect(screen.queryByText('Arrian, Anabasis')).toBeNull();
    const header = await screen.findByText(/Same people and places/);
    await user.click(header);
    expect(await screen.findByText('Arrian, Anabasis')).toBeTruthy();
  });

  it('still shows the scene section open', async () => {
    mount();
    expect(await screen.findByText('Claudian, In Eutropium')).toBeTruthy();
  });
});
