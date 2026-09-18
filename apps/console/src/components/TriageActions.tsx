import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  ApiError,
  claimsApi,
  type ClaimDetail,
  type ClaimStatus,
  type ReasonCode,
} from '../api/client';
import { humanise } from '../lib/format';

const NEXT_STATUSES: Record<string, ClaimStatus[]> = {
  REGISTERED: ['TRIAGED', 'WITHDRAWN'],
  TRIAGED: ['IN_ASSESSMENT', 'REJECTED', 'WITHDRAWN'],
  IN_ASSESSMENT: ['PENDING_APPROVAL', 'REJECTED', 'WITHDRAWN'],
  PENDING_APPROVAL: ['APPROVED', 'IN_ASSESSMENT'],
  APPROVED: ['SETTLED'],
  SETTLED: ['CLOSED'],
  REJECTED: ['CLOSED'],
  WITHDRAWN: ['CLOSED'],
  CLOSED: [],
};

const REASONS: ReasonCode[] = [
  'NO_COVER',
  'POLICY_LAPSED',
  'FRAUD_CONFIRMED',
  'CUSTOMER_WITHDREW',
  'DUPLICATE_NOTIFICATION',
];

export function TriageActions({ claim }: { claim: ClaimDetail }) {
  const queryClient = useQueryClient();
  const options = NEXT_STATUSES[claim.status] ?? [];
  const [target, setTarget] = useState<ClaimStatus | ''>('');
  const [reason, setReason] = useState<string>('');
  const [note, setNote] = useState('');

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['claim', claim.claim_reference] });
    await queryClient.invalidateQueries({ queryKey: ['timeline', claim.claim_reference] });
    await queryClient.invalidateQueries({ queryKey: ['claims'] });
  };

  const transition = useMutation({
    mutationFn: async () => {
      if (!target) {
        throw new Error('Choose a status first');
      }
      return claimsApi.transition(claim.claim_reference, {
        target_status: target,
        reason_code: reason ? (reason as never) : null,
        note: note ? note : null,
      });
    },
    onSuccess: async () => {
      setNote('');
      await invalidate();
    },
  });

  const triage = useMutation({
    mutationFn: () => claimsApi.rerunTriage(claim.claim_reference),
    onSuccess: invalidate,
  });

  const failure = transition.error ?? triage.error;

  return (
    <section className="panel" aria-label="Triage actions">
      <h2>Actions</h2>
      <div className="actions">
        <label>
          Move to
          <select
            value={target}
            onChange={(event) => setTarget(event.target.value as ClaimStatus)}
            disabled={options.length === 0}
          >
            <option value="">Select a status</option>
            {options.map((status) => (
              <option key={status} value={status}>
                {humanise(status)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reason
          <select value={reason} onChange={(event) => setReason(event.target.value)}>
            <option value="">Not required</option>
            {REASONS.map((code) => (
              <option key={code} value={code}>
                {humanise(code)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Note
          <input
            type="text"
            value={note}
            placeholder="Context for the audit trail"
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <button type="button" onClick={() => transition.mutate()} disabled={transition.isPending}>
          Apply transition
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => triage.mutate()}
          disabled={triage.isPending}
        >
          Re-run triage
        </button>
      </div>
      {failure ? (
        <p className="error" role="alert">
          {failure instanceof ApiError ? `${failure.message} (${failure.code})` : failure.message}
        </p>
      ) : null}
    </section>
  );
}
