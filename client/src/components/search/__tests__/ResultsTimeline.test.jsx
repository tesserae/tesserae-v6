import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import ResultsTimeline, { timelineEntries } from '../ResultsTimeline';

const rows = [
  { author: 'Vergil', year: -19, n: 3 },
  { author: 'Lucan', year: 65, n: 2 },
  { author: 'Statius', year: 92, n: 1 },
  { author: 'Ennius', year: -170, n: 1 },
  { author: 'Anonymous', year: 9999, n: 5 },
  { author: 'No_Date', year: null, n: 4 },
];

const labels = (container) =>
  Array.from(container.querySelectorAll('text.author-label')).map((t) => t.textContent);

describe('ResultsTimeline', () => {
  it('lists dated authors, latest first, each labeled with its date and count', () => {
    expect(timelineEntries(rows).map((d) => d.author)).toEqual(['Statius', 'Lucan', 'Vergil', 'Ennius']);
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} comparedAuthors={['Vergil', 'Lucan']} />);
    expect(labels(container)).toEqual(['Statius, 92 CE (1)', 'Lucan, 65 CE (2)', 'Vergil, 19 BCE (3)', 'Ennius, 170 BCE (1)']);
  });

  it('draws a date axis with year ticks, and places later authors higher than earlier ones', () => {
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} />);
    const ticks = Array.from(container.querySelectorAll('svg > g:first-of-type text')).map((t) => t.textContent);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
    expect(ticks.some((t) => t.endsWith('BCE'))).toBe(true);
    expect(ticks.some((t) => t.endsWith('CE'))).toBe(true);
    const y = Object.fromEntries(Array.from(container.querySelectorAll('text.author-label'))
      .map((t) => [t.textContent.split(',')[0], Number(t.getAttribute('y'))]));
    expect(y.Statius).toBeLessThan(y.Lucan);
    expect(y.Lucan).toBeLessThan(y.Vergil);
    expect(y.Vergil).toBeLessThan(y.Ennius);
  });

  it('draws one dot per occurrence', () => {
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} />);
    expect(container.querySelectorAll('circle')).toHaveLength(1 + 2 + 3 + 1);
  });

  it('draws the compared works in red, the rest in blue, the selected one in full color', () => {
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor="Statius" onSelectAuthor={() => {}} comparedAuthors={['Vergil', 'Lucan']} />);
    const fills = Array.from(container.querySelectorAll('circle')).map((c) => c.getAttribute('fill'));
    expect(fills).toEqual([
      'rgba(37,99,235,1)',
      'rgba(185,28,28,0.75)', 'rgba(185,28,28,0.75)',
      'rgba(185,28,28,0.75)', 'rgba(185,28,28,0.75)', 'rgba(185,28,28,0.75)',
      'rgba(37,99,235,0.75)',
    ]);
  });

  it('names the author, date and count in the hover title, singular and plural', () => {
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={() => {}} />);
    const titles = Array.from(container.querySelectorAll('title')).map((t) => t.textContent);
    expect(titles).toContain('Lucan — 65 CE — 2 occurrences');
    expect(titles).toContain('Statius — 92 CE — 1 occurrence');
  });

  it('a click on an author selects it', () => {
    const onSelect = vi.fn();
    const { container } = render(<ResultsTimeline rows={rows} selectedAuthor={null} onSelectAuthor={onSelect} />);
    const lucan = Array.from(container.querySelectorAll('text.author-label')).find((t) => t.textContent.startsWith('Lucan'));
    fireEvent.click(lucan.parentNode);
    expect(onSelect).toHaveBeenCalledWith('Lucan');
  });

  it('says so when no author has a date, and draws nothing for no rows', () => {
    const { container, rerender } = render(<ResultsTimeline rows={[{ author: 'A', year: 9999, n: 1 }]} onSelectAuthor={() => {}} />);
    expect(screen.getByText('No dated authors to place on a timeline.')).toBeTruthy();
    rerender(<ResultsTimeline rows={[]} onSelectAuthor={() => {}} />);
    expect(container.querySelector('svg')).toBeNull();
    expect(container.textContent).toBe('');
  });

  it('keeps only the forty authors with the most occurrences', () => {
    const many = Array.from({ length: 60 }, (_, i) => ({ author: `A${i}`, year: i, n: i + 1 }));
    const entries = timelineEntries(many);
    expect(entries).toHaveLength(40);
    expect(entries[0].author).toBe('A59');
    expect(entries.at(-1).author).toBe('A20');
  });
});
