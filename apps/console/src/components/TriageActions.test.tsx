import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError, claimsApi } from '../api/client';
import { claimDetail } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

import { TriageActions } from './TriageActions';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    claimsApi: { ...actual.claimsApi, transition: vi.fn(), rerunTriage: vi.fn() },
  };
});

const transition = vi.mocked(claimsApi.transition);

describe('TriageActions (FR-011, FR-014)', () => {
  it('only offers transitions that are legal from the current status', () => {
    renderWithProviders(<TriageActions claim={claimDetail} />);

    const options = screen.getAllByRole('option').map((option) => option.textContent);
    expect(options).toContain('In Assessment');
    expect(options).not.toContain('Settled');
  });

  it('sends the chosen transition with a reason code', async () => {
    transition.mockResolvedValue({
      id: '1f2e3d4c-5b6a-4798-8899-aabbccddeeff',
      from_status: 'TRIAGED',
      to_status: 'REJECTED',
      reason_code: 'NO_COVER',
      note: 'Outside cover',
      actor_id: 'd.okafor',
      actor_role: 'claims_handler',
      correlation_id: 'corr-1',
      created_at: '2026-09-14T12:00:00Z',
    });
    renderWithProviders(<TriageActions claim={claimDetail} />);

    await userEvent.selectOptions(screen.getByLabelText('Move to'), 'REJECTED');
    await userEvent.selectOptions(screen.getByLabelText('Reason'), 'NO_COVER');
    await userEvent.type(screen.getByLabelText('Note'), 'Outside cover');
    await userEvent.click(screen.getByRole('button', { name: 'Apply transition' }));

    await waitFor(() => {
      expect(transition).toHaveBeenCalledWith('MER-2026-000101', {
        target_status: 'REJECTED',
        reason_code: 'NO_COVER',
        note: 'Outside cover',
      });
    });
  });

  it('shows the structured error returned by the API', async () => {
    transition.mockRejectedValue(
      new ApiError(409, {
        code: 'invalid_transition',
        message: 'Claim MER-2026-000101 cannot move from TRIAGED to IN_ASSESSMENT',
        details: {},
        correlation_id: 'corr-2',
      }),
    );
    renderWithProviders(<TriageActions claim={claimDetail} />);

    await userEvent.selectOptions(screen.getByLabelText('Move to'), 'IN_ASSESSMENT');
    await userEvent.click(screen.getByRole('button', { name: 'Apply transition' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('invalid_transition');
  });
});
