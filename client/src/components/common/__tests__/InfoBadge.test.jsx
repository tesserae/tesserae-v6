import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InfoBadge from '../InfoBadge';

// Owner's review of the result card (2026-10-08): a native `title` tooltip
// shows nothing for a second or two, gives no sign anything is there, and
// does nothing on a phone. InfoBadge replaces it: a popover that opens at
// once on hover, on keyboard focus, and on tap (which toggles it), closes
// on Escape or a tap outside, and always carries a visible info mark.
const renderBadge = (props = {}) =>
  render(
    <InfoBadge heading="A heading" explanation="An explanation." {...props}>
      Label
    </InfoBadge>
  );

describe('InfoBadge — affordance', () => {
  it('shows a visible info mark and a help cursor on the trigger', () => {
    renderBadge();
    const trigger = screen.getByRole('button');
    expect(trigger).toHaveTextContent('Label');
    expect(trigger.className).toContain('cursor-help');
    // the circled "i" mark, drawn as an icon so it never depends on a font
    expect(trigger.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
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
    trigger.focus();
    expect(document.activeElement).toBe(trigger);
  });
});

describe('InfoBadge — opens on hover, focus, and tap', () => {
  it('opens on mouse hover, with no popover beforehand', () => {
    renderBadge();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByText('Label').closest('span'));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    expect(screen.getByText('A heading')).toBeInTheDocument();
    expect(screen.getByText('An explanation.')).toBeInTheDocument();
  });

  it('opens on keyboard focus', () => {
    renderBadge();
    fireEvent.focus(screen.getByRole('button'));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('tap (click) toggles it open, then closed', () => {
    renderBadge();
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('InfoBadge — closes', () => {
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
        <InfoBadge heading="A heading" explanation="An explanation.">Label</InfoBadge>
        <button>elsewhere</button>
      </div>
    );
    fireEvent.click(screen.getByRole('button', { name: /label/i }));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole('button', { name: 'elsewhere' }));
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('InfoBadge — explanation content', () => {
  it('splits a string explanation into separate paragraphs on blank lines', () => {
    render(
      <InfoBadge heading="H" explanation={'First line.\n\nSecond line.'}>
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('First line.').tagName).toBe('P');
    expect(screen.getByText('Second line.').tagName).toBe('P');
  });

  it('shows a footer line (e.g. the raw site id) after the explanation', () => {
    render(
      <InfoBadge heading="H" explanation="Body." footer="Site ID: hafez.diwan.5097">
        Label
      </InfoBadge>
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Site ID: hafez.diwan.5097')).toBeInTheDocument();
  });
});
