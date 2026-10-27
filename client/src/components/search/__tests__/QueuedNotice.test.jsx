import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import QueuedNotice from '../QueuedNotice';
import { queuedText } from '../../../utils/fusionParts';

describe('QueuedNotice', () => {
  it('renders the waiting line from a poll payload, not "computing"', () => {
    const payload = {
      status: 'queued', kind: 'slots', running: 3, position: 1, wait_seconds: 100,
      message: 'Waiting to start: 3 comparisons are ahead of yours (the server lets three run at once). '
        + 'Waiting for 1:40 so far. The server holds a request for up to thirty minutes, then stops it '
        + 'and offers the comparison as a prepared file.',
    };
    render(<QueuedNotice message={queuedText(payload)} />);
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for 1:40 so far');
    expect(screen.getByRole('status')).toHaveTextContent('up to thirty minutes');
    expect(screen.getByRole('status')).not.toHaveTextContent(/computing/i);
  });
});
