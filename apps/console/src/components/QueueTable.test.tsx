import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { breachedClaim, motorClaim } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

import { QueueTable } from './QueueTable';

describe('QueueTable (FR-100)', () => {
  it('shows exposure in major units and links to the claim', () => {
    renderWithProviders(<QueueTable claims={[motorClaim]} />);

    expect(screen.getByRole('link', { name: 'MER-2026-000101' })).toHaveAttribute(
      'href',
      '/claims/MER-2026-000101',
    );
    expect(screen.getByText('£4,800.00')).toBeInTheDocument();
    expect(screen.getByText('Triaged')).toBeInTheDocument();
  });

  it('marks breached SLAs and suspected duplicates', () => {
    renderWithProviders(<QueueTable claims={[breachedClaim]} />);

    expect(screen.getByText(/^Breached/)).toBeInTheDocument();
    expect(screen.getByText('Possible duplicate')).toBeInTheDocument();
  });

  it('explains an empty queue', () => {
    renderWithProviders(<QueueTable claims={[]} />);

    expect(screen.getByText('No claims match these filters.')).toBeInTheDocument();
  });
});
