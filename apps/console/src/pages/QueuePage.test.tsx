import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { claimsApi } from '../api/client';
import { breachedClaim, motorClaim } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

import { QueuePage } from './QueuePage';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, claimsApi: { ...actual.claimsApi, listClaims: vi.fn() } };
});

const listClaims = vi.mocked(claimsApi.listClaims);

describe('QueuePage (FR-100)', () => {
  beforeEach(() => {
    listClaims.mockResolvedValue({ items: [motorClaim, breachedClaim], next_cursor: null });
  });

  it('loads the queue on mount', async () => {
    renderWithProviders(<QueuePage />);

    expect(await screen.findByText('MER-2026-000101')).toBeInTheDocument();
    expect(listClaims).toHaveBeenCalledWith({ limit: 25 });
  });

  it('passes the breached filter to the API', async () => {
    renderWithProviders(<QueuePage />);
    await screen.findByText('MER-2026-000101');

    await userEvent.click(screen.getByLabelText('Breached only'));

    await waitFor(() => {
      expect(listClaims).toHaveBeenLastCalledWith({ limit: 25, breached: true });
    });
  });

  it('surfaces API failures', async () => {
    listClaims.mockRejectedValue(new Error('The claims API returned 503'));
    renderWithProviders(<QueuePage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('The claims API returned 503');
  });
});
