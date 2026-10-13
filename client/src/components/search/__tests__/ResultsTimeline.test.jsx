import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('react-chartjs-2', async () => {
  const { forwardRef, createElement } = await vi.importActual('react');
  return {
    Bar: forwardRef(({ data, options }, ref) =>
      createElement('button', {
        ref,
        'data-testid': 'bar',
        'data-labels': JSON.stringify(data.labels),
        'data-counts': JSON.stringify(data.datasets[0].data),
        'data-colors': JSON.stringify(data.datasets[0].backgroundColor),
        'data-tooltip': options.plugins.tooltip.callbacks.label({ dataIndex: 1 }),
        onClick: () => options.onClick(null, [{ index: 1 }]),
      }, 'bar')),
  };
});
vi.mock('chart.js', () => ({
  Chart: { register: () => {} },
  CategoryScale: {}, LinearScale: {}, BarElement: {}, Title: {}, Tooltip: {}, Legend: {},
}));

import ResultsTimeline, { timelineEntries } from '../ResultsTimeline';

const rows = [
  { author: 'Vergil', year: -19, n: 3 },
  { author: 'Lucan', year: 65, n: 2 },
  { author: 'Statius', year: 92, n: 1 },
  { author: 'Ennius', year: -170, n: 1 },
  { author: 'Anonymous', year: 9999, n: 5 },
  { author: 'No_Date', year: null, n: 4 },
];

describe('ResultsTimeline', () => {
  it('lists dated authors, latest first, with the label the old timeline gave', () => {
    expect(timelineEntries(rows).map((d) => d.author)).toEqual(['Statius', 'Lucan', 'Vergil', 'Ennius']);
    render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} comparedAuthors={['Vergil', 'Lucan']} />);
    const bar = screen.getByTestId('bar');
    expect(JSON.parse(bar.dataset.labels)).toEqual(['Statius, 92 CE (1)', 'Lucan, 65 CE (2)', 'Vergil, 19 BCE (3)', 'Ennius, 170 BCE (1)']);
    expect(JSON.parse(bar.dataset.counts)).toEqual([1, 2, 3, 1]);
  });

  it('draws the compared works in red, the rest in blue, the selected one in full color', () => {
    render(<ResultsTimeline rows={rows} selectedAuthor="Statius" onSelectAuthor={() => {}} comparedAuthors={['Vergil', 'Lucan']} />);
    expect(JSON.parse(screen.getByTestId('bar').dataset.colors)).toEqual([
      'rgba(37,99,235,1)', 'rgba(185,28,28,0.75)', 'rgba(185,28,28,0.75)', 'rgba(37,99,235,0.75)',
    ]);
  });

  it('names the author, date and count in the tooltip, singular and plural', () => {
    render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} />);
    expect(screen.getByTestId('bar').dataset.tooltip).toBe('Lucan — 65 CE — 2 occurrences');
  });

  it('a click on a bar selects that author', async () => {
    const onSelect = vi.fn();
    render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={onSelect} />);
    await userEvent.click(screen.getByTestId('bar'));
    expect(onSelect).toHaveBeenCalledWith('Lucan');
  });

  it('says so when no author has a date, and draws nothing for no rows', () => {
    const { container, rerender } = render(<ResultsTimeline rows={[{ author: 'A', year: 9999, n: 1 }]} onSelectAuthor={() => {}} />);
    expect(screen.getByText('No dated authors to place on a timeline.')).toBeTruthy();
    rerender(<ResultsTimeline rows={[]} onSelectAuthor={() => {}} />);
    expect(container.querySelector('button')).toBeNull();
  });

  it('keeps only the forty authors with the most occurrences', () => {
    const many = Array.from({ length: 60 }, (_, i) => ({ author: `A${i}`, year: i, n: i + 1 }));
    const entries = timelineEntries(many);
    expect(entries).toHaveLength(40);
    expect(entries[0].author).toBe('A59');
    expect(entries.at(-1).author).toBe('A20');
  });
});
