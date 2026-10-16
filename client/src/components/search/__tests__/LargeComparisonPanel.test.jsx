import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LargeComparisonPanel from '../LargeComparisonPanel';

const estimate = { pairs: 96298976, in_parts: true, parts: 20, estimated_seconds: 1637 };

describe('LargeComparisonPanel', () => {
  it('shows nothing when the comparison does not run in parts', () => {
    const { container } = render(
      <LargeComparisonPanel sourceName="A" targetName="B" estimate={{ ...estimate, in_parts: false }}
        onRun={() => {}} onChoose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    const none = render(<LargeComparisonPanel sourceName="A" targetName="B" estimate={null} />);
    expect(none.container).toBeEmptyDOMElement();
  });

  it('shows the warning and both buttons, and each button calls its handler', () => {
    const onRun = vi.fn();
    const onChoose = vi.fn();
    render(<LargeComparisonPanel sourceName="Statius, Thebaid" targetName="Vergil, Aeneid"
      estimate={estimate} onRun={onRun} onChoose={onChoose} />);
    expect(screen.getByText(
      'Large comparison. Statius, Thebaid against Vergil, Aeneid is about 96 million line pairs and '
      + 'will take about 27 minutes. The results fill in part by part, and you can leave the page '
      + 'open. Comparing selected books finishes in a minute or two.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Run the full comparison' }));
    expect(onRun).toHaveBeenCalledTimes(1);
    expect(onChoose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Choose books instead' }));
    expect(onChoose).toHaveBeenCalledTimes(1);
  });
});
