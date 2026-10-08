import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import InfoBadge from '../InfoBadge';

// Second pass of the result card (2026-10-08): a native `title` tooltip
// showed nothing for a second or two and did nothing on a phone, so the
// first pass gave InfoBadge an always-visible "i" mark and a help cursor.
// The owner's review called the mark a dead-looking affordance and the
// delay-free hover a source of flicker when the pointer crosses the card.
// Following the Nielsen Norman Group's tooltip guidance and the Carbon/
// Inclusive Components hover-vs-toggle distinction, InfoBadge now carries
// no icon at all: the badge itself is the trigger. It opens after a short
// delay on hover, at once on keyboard focus, and at once on tap (which
// toggles it); it stays open while the pointer is over the popover, and
// closes on Escape or a tap outside.
const renderBadge = (props = {}) =>
  render(
    <InfoBadge explanation="An explanation." {...props}>
      Label
    </InfoBadge>
  );

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  act(() => { vi.runOnlyPendingTimers(); });
  vi.useRealTimers();
});

describe('InfoBadge — no icon, no help cursor', () => {
  it('shows only the label, with no info mark and no cursor-help class', () => {
    renderBadge();
    const trigger = screen.getByRole('button');
    expect(trigger).toHaveTextContent('Label');
    expect(trigger.className).not.toContain('cursor-help');
    expect(trigger.querySelector('svg')).toBeNull();
  });

  it('has role="tooltip" and ties the trigger to it with aria-describedby', () => {
    renderBadge();
    fireEvent.click(screen.getByRole('button'));
    const popover = screen.getByRole('tooltip');
    expect(screen.getByRole('button')).toHaveAttribute('aria-describedby', popover.id);
  });

  it('the trigger is itself focusable', () => {
    renderBadge();
    const trigger = screen.getByRole('button');
    act(() => { trigger.focus(); });
    expect(document.activeElement).toBe(trigger);
  });
});

describe('InfoBadge — opens on hover (delayed), focus and tap (instant)', () => {
  it('does not open immediately on hover', () => {
    renderBadge();
    fireEvent.mouseEnter(screen.getByText('Label').closest('span'));
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('opens on hover after about 150ms', () => {
    renderBadge();
    const wrap = screen.getByText('Label').closest('span');
    fireEvent.mouseEnter(wrap);
    act(() => { vi.advanceTimersByTime(140); });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(20); });
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    expect(screen.getByText('An explanation.')).toBeInTheDocument();
  });

  it('leaving before the delay elapses cancels the open (no flicker)', () => {
    renderBadge();
    const wrap = screen.getByText('Label').closest('span');
    fireEvent.mouseEnter(wrap);
    act(() => { vi.advanceTimersByTime(80); });
    fireEvent.mouseLeave(wrap);
    act(() => { vi.advanceTimersByTime(200); });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('opens at once on keyboard focus', () => {
    renderBadge();
    fireEvent.focus(screen.getByRole('button'));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('tap (click) toggles it open, then closed, at once', () => {
    renderBadge();
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('InfoBadge — stays open and closes', () => {
  it('stays open while the pointer moves from the badge onto the popover', () => {
    renderBadge();
    const wrap = screen.getByText('Label').closest('span');
    fireEvent.mouseEnter(wrap);
    act(() => { vi.advanceTimersByTime(150); });
    const popover = screen.getByRole('tooltip');
    // The popover is a descendant of the same hoverable wrapper, so moving
    // onto it never fires the wrapper's mouseLeave.
    fireEvent.mouseEnter(popover);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('closes on Escape', () => {
    renderBadge();
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('closes on a tap outside', () => {
    render(
      <div>
        <InfoBadge explanation="An explanation.">Label</InfoBadge>
        <button>elsewhere</button>
      </div>
    );
    fireEvent.click(screen.getByRole('button', { name: /label/i }));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole('button', { name: 'elsewhere' }));
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('InfoBadge — content', () => {
  it('splits a string explanation into separate paragraphs on blank lines', () => {
    render(
      <InfoBadge explanation={'First line.\n\nSecond line.'}>
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('First line.').tagName).toBe('P');
    expect(screen.getByText('Second line.').tagName).toBe('P');
  });

  it('shows extra compact content after the explanation', () => {
    render(
      <InfoBadge explanation="Body." extra={<div>Hafez, Diwan 5097 to 5099</div>}>
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Hafez, Diwan 5097 to 5099')).toBeInTheDocument();
  });

  it('shows a "More" link that calls its onClick', () => {
    const onClick = vi.fn();
    render(
      <InfoBadge explanation="Body." more={{ anchor: 'score', onClick }}>
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button', { name: 'More' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('shows a footer line (e.g. the raw site id) after the explanation', () => {
    render(
      <InfoBadge explanation="Body." footer="Site ID: hafez.diwan.5097">
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Site ID: hafez.diwan.5097')).toBeInTheDocument();
  });
});
