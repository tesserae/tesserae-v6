import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import LargeComparisonNotice from '../LargeComparisonNotice';

const estimate = { pairs: 96298976, in_parts: true, parts: 20, estimated_seconds: 1637 };

describe('LargeComparisonNotice', () => {
  it('shows nothing when the comparison does not run in parts', () => {
    const { container } = render(
      <LargeComparisonNotice sourceName="A" targetName="B" estimate={{ ...estimate, in_parts: false }}
        onChoose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    const none = render(<LargeComparisonNotice sourceName="A" targetName="B" estimate={null} />);
    expect(none.container).toBeEmptyDOMElement();
  });

  it('shows the estimate line and a link that chooses books, with no confirmation button', () => {
    const onChoose = vi.fn();
    render(<LargeComparisonNotice sourceName="Statius, Thebaid" targetName="Vergil, Aeneid"
      estimate={estimate} onChoose={onChoose} />);
    expect(screen.getByRole('region', { name: 'Large comparison' })).toHaveTextContent(
      'Statius, Thebaid against Vergil, Aeneid: about 96 million line pairs, about 27 minutes. '
      + 'The results fill in part by part.');
    expect(screen.queryByRole('button', { name: 'Run the full comparison' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Compare chosen books instead' }));
    expect(onChoose).toHaveBeenCalledTimes(1);
  });
});
