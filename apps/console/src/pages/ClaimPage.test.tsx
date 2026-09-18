import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { claimsApi } from '../api/client';
import { auditEvents, claimDetail, timelineEntries } from '../test/fixtures';
import { renderWithProviders } from '../test/render';

import { ClaimPage } from './ClaimPage';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    claimsApi: {
      ...actual.claimsApi,
      getClaim: vi.fn(),
      getTimeline: vi.fn(),
      getAuditEvents: vi.fn(),
    },
  };
});

function renderClaimPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/claims/:claimReference" element={<ClaimPage />} />
    </Routes>,
    '/claims/MER-2026-000101',
  );
}

describe('ClaimPage (FR-101, FR-061)', () => {
  beforeEach(() => {
    vi.mocked(claimsApi.getClaim).mockResolvedValue(claimDetail);
    vi.mocked(claimsApi.getTimeline).mockResolvedValue(timelineEntries);
    vi.mocked(claimsApi.getAuditEvents).mockResolvedValue({
      items: auditEvents,
      next_cursor: null,
    });
  });

  it('renders the claim header, timeline, documents and audit trail', async () => {
    renderClaimPage();

    expect(await screen.findByRole('heading', { name: 'MER-2026-000101' })).toBeInTheDocument();
    expect(screen.getByText('Rowan Whitfield (rowan.whitfield@example.com)')).toBeInTheDocument();
    expect(await screen.findByLabelText('Claim timeline')).toHaveTextContent('Claim registered');
    expect(screen.getByText('engineer-report.pdf')).toBeInTheDocument();
    expect(await screen.findByLabelText('Audit trail')).toHaveTextContent('claim.registered');
  });

  it('reports a claim that cannot be loaded', async () => {
    vi.mocked(claimsApi.getClaim).mockRejectedValue(new Error('Claim MER-2026-000101 not found'));
    renderClaimPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('not found');
  });
});
