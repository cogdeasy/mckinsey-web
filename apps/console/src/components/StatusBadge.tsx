import type { ClaimStatus } from '../api/client';
import { humanise } from '../lib/format';

const TONE: Record<string, string> = {
  REGISTERED: 'badge--neutral',
  TRIAGED: 'badge--info',
  IN_ASSESSMENT: 'badge--info',
  PENDING_APPROVAL: 'badge--warn',
  APPROVED: 'badge--good',
  SETTLED: 'badge--good',
  REJECTED: 'badge--bad',
  WITHDRAWN: 'badge--neutral',
  CLOSED: 'badge--neutral',
};

export function StatusBadge({ status }: { status: ClaimStatus }) {
  return <span className={`badge ${TONE[status] ?? 'badge--neutral'}`}>{humanise(status)}</span>;
}
