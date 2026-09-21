import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Modal from '../Modal';

const renderModal = (props = {}) =>
  render(
    <div>
      <button>Opener</button>
      <Modal isOpen title="Test Dialog" onClose={() => {}} {...props}>
        <button>Inside 1</button>
        <button>Inside 2</button>
      </Modal>
    </div>
  );

describe('Modal — dialog semantics', () => {
  it('exposes role="dialog", aria-modal, and a label tied to its own heading', () => {
    renderModal();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const heading = screen.getByText('Test Dialog');
    expect(dialog).toHaveAttribute('aria-labelledby', heading.id);
  });

  it('gives the close button an accessible name', () => {
    renderModal();
    expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument();
  });

  it('renders nothing when isOpen is false', () => {
    render(<Modal isOpen={false} title="Hidden" onClose={() => {}}>content</Modal>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Modal — keyboard behavior', () => {
  it('calls onClose when Escape is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderModal({ onClose });
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('moves focus into the dialog when it opens', () => {
    renderModal();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toContainElement(document.activeElement);
  });

  it('returns focus to the element that opened it once it closes', async () => {
    const user = userEvent.setup();

    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button onClick={() => setOpen(true)}>Opener</button>
          <Modal isOpen={open} title="Test Dialog" onClose={() => setOpen(false)}>
            <button>Inside</button>
          </Modal>
        </div>
      );
    }

    render(<Harness />);
    const opener = screen.getByRole('button', { name: 'Opener' });
    opener.focus();
    await user.click(opener);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(opener);
  });

  it('keeps Tab focus inside the dialog (wraps from last to first)', async () => {
    const user = userEvent.setup();
    renderModal();
    const closeButton = screen.getByRole('button', { name: /close/i });
    const last = screen.getByRole('button', { name: 'Inside 2' });
    last.focus();
    await user.tab();
    expect(document.activeElement).toBe(closeButton);
  });
});
