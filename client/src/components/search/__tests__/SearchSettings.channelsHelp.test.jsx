import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('../../../utils/api', () => ({
  fetchFusionDefaultWeights: vi.fn(() => Promise.resolve({ weights: { lemma: 2, sound: 5 }, min: 0, max: 20 })),
}));

import SearchSettings from '../SearchSettings';

// The channels panel explains itself (owner, 2026-10-16): a link to the Help
// section on channels, and a toggle that puts one line under each channel.
const fusionSettings = {
  match_type: 'fusion', min_matches: 2, stoplist_basis: 'source_target', stoplist_size: 0, custom_stopwords: '',
  source_unit_type: 'line', target_unit_type: 'line', max_distance: 999, max_results: 0, bigram_boost: false,
  use_meter: false, freq_basis: 'corpus', channel_weights: {}, disabled_channels: [], formula_max: null, formula_only: false,
};

function Harness() {
  const [settings, setSettings] = useState(fusionSettings);
  return <SearchSettings settings={settings} setSettings={setSettings} showAdvanced setShowAdvanced={() => {}} language="la" />;
}

describe('SearchSettings channels panel: help link and notes', () => {
  it('opens Help at the channels anchor and shows a line under each channel', async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /Channels and weights \(advanced\)/ }));
    const seen = [];
    const onHelp = (e) => seen.push(e.detail);
    window.addEventListener('tesserae:open-help', onHelp);
    fireEvent.click(screen.getByTestId('channels-help-link'));
    window.removeEventListener('tesserae:open-help', onHelp);
    expect(seen).toEqual([{ section: 'reading-results', anchor: 'channels' }]);

    expect(screen.queryByTestId('channel-note-lemma')).toBeNull();
    fireEvent.click(screen.getByTestId('channels-notes-toggle'));
    expect(await screen.findByTestId('channel-note-lemma')).toHaveTextContent(/shared lemmata/);
    // Only channels with a tuned default are listed, so the second check is on sound.
    expect(screen.getByTestId('channel-note-sound')).toHaveTextContent(/trigrams/);
    fireEvent.click(screen.getByTestId('channels-notes-toggle'));
    expect(screen.queryByTestId('channel-note-lemma')).toBeNull();
  });
});
