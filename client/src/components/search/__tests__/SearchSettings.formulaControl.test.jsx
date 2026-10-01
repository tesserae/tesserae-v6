import { describe, it, expect } from 'vitest';
import { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import SearchSettings from '../SearchSettings';

// match_type: 'lemma' (not 'fusion') keeps the component off its
// fetchFusionDefaultWeights effect, so no network/api mocking is needed here.
const baseSettings = {
  match_type: 'lemma',
  min_matches: 2,
  stoplist_basis: 'source_target',
  stoplist_size: 0,
  custom_stopwords: '',
  source_unit_type: 'line',
  target_unit_type: 'line',
  max_distance: 999,
  max_results: 0,
  bigram_boost: false,
  use_meter: false,
  freq_basis: 'corpus',
  channel_weights: {},
  disabled_channels: [],
  formula_max: null,
  formula_only: false,
};

function Harness({ initial = baseSettings }) {
  const [settings, setSettings] = useState(initial);
  return (
    <SearchSettings
      settings={settings}
      setSettings={setSettings}
      showAdvanced={true}
      setShowAdvanced={() => {}}
      language="he"
    />
  );
}

describe('SearchSettings — Formulas control', () => {
  it('defaults to "Show all" with no filtering', () => {
    render(<Harness />);
    expect(screen.getByLabelText(/Show all/)).toBeChecked();
  });

  it('switching to "Hide formulas" sets formula_max (default 5) and formula_only false', () => {
    render(<Harness />);
    fireEvent.click(screen.getByText(/Hide formulas that recur in more than/));
    const hideRadio = screen.getByText(/Hide formulas that recur in more than/)
      .closest('label').querySelector('input[type="radio"]');
    expect(hideRadio).toBeChecked();
    const input = screen.getByDisplayValue('5');
    expect(input).toBeEnabled();
  });

  it('switching to "Show only formulas" checks that radio and enables its own input', () => {
    render(<Harness />);
    const onlyLabel = screen.getByText(/Show only formulas/).closest('label');
    fireEvent.click(onlyLabel.querySelector('input[type="radio"]'));
    expect(onlyLabel.querySelector('input[type="radio"]')).toBeChecked();
    // Its own threshold input (defaulted to 5) is now enabled.
    const onlyInput = onlyLabel.querySelector('input[type="text"]');
    expect(onlyInput).toBeEnabled();
    expect(onlyInput.value).toBe('5');
  });

  it('changing the threshold while in "hide" mode updates formula_max', () => {
    let latest = null;
    function CapturingHarness() {
      const [settings, setSettings] = useState({ ...baseSettings, formula_max: 5, formula_only: false });
      latest = settings;
      return (
        <SearchSettings settings={settings} setSettings={(fn) => setSettings((prev) => {
          const next = typeof fn === 'function' ? fn(prev) : fn;
          latest = next;
          return next;
        })} showAdvanced={true} setShowAdvanced={() => {}} language="he" />
      );
    }
    render(<CapturingHarness />);
    const hideLabel = screen.getByText(/Hide formulas that recur in more than/).closest('label');
    const input = hideLabel.querySelector('input[type="text"]');
    fireEvent.change(input, { target: { value: '12' } });
    expect(latest.formula_max).toBe(12);
    expect(latest.formula_only).toBe(false);
  });
});
