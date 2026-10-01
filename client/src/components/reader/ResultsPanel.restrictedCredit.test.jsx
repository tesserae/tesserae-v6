/**
 * Similar Passages cards must carry a restricted work's licence credit line
 * beneath the passage, the same way the backend's _naming (passage_index.py)
 * attaches it to every result it builds.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import ResultsPanel from './ResultsPanel';

const SIMILAR_HITS = {
  results: [
    {
      id: 'w1', work: 'heldwork.history', language: 'la',
      ref_start: 'held. hist. 1.1', year: 100,
      display_name: 'Held Author, History',
      gist: 'A passage from the held work.',
      restricted: true,
      credit: 'Source: Test Licence Holder (example.invalid)',
    },
  ],
};

function mount(props = {}) {
  const onOpenPassage = vi.fn();
  render(
    <ResultsPanel
      selection={{ refStart: 'verg. aen. 6.1', refEnd: 'verg. aen. 6.1',
                   startIdx: 0, endIdx: 0 }}
      language="la"
      work="vergil.aeneid.part.6.tess"
      units={[{ ref: 'verg. aen. 6.1', text: 'line text' }]}
      onOpenPassage={onOpenPassage}
      initialTab="similar"
      {...props}
    />
  );
  return { onOpenPassage };
}

describe('Similar Passages card shows a restricted work\'s credit', () => {
  it('renders the credit line beneath the result', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve(SIMILAR_HITS) }));
    mount();
    expect(await screen.findByText('Source: Test Licence Holder (example.invalid)'))
      .toBeInTheDocument();
  });

  it('renders no credit line for an unrestricted result', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({
      results: [{ id: 'w2', work: 'ordinary.poem', language: 'la',
                  ref_start: 'ord. 1.1', year: 10,
                  display_name: 'Ordinary Poet, Poem', gist: 'An ordinary passage.' }],
    }) }));
    mount();
    await screen.findByText('An ordinary passage.');
    expect(screen.queryByText(/^Source: /)).not.toBeInTheDocument();
  });
});
