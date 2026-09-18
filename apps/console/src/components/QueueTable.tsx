import { Link } from 'react-router-dom';

import type { ClaimSummary } from '../api/client';
import { formatMoney, humanise } from '../lib/format';

import { SlaCell } from './SlaCell';
import { StatusBadge } from './StatusBadge';

interface QueueTableProps {
  claims: ClaimSummary[];
}

export function QueueTable({ claims }: QueueTableProps) {
  if (claims.length === 0) {
    return <p className="empty">No claims match these filters.</p>;
  }

  return (
    <table className="table" aria-label="Claims queue">
      <thead>
        <tr>
          <th scope="col">Claim</th>
          <th scope="col">Policyholder</th>
          <th scope="col">Product</th>
          <th scope="col">Segment</th>
          <th scope="col">Priority</th>
          <th scope="col">Exposure</th>
          <th scope="col">Status</th>
          <th scope="col">Decision SLA</th>
        </tr>
      </thead>
      <tbody>
        {claims.map((claim) => (
          <tr key={claim.claim_reference}>
            <td>
              <Link to={`/claims/${claim.claim_reference}`}>{claim.claim_reference}</Link>
              {claim.duplicate_suspected ? <span className="flag">Possible duplicate</span> : null}
            </td>
            <td>{claim.policyholder_name}</td>
            <td>{humanise(claim.product)}</td>
            <td>{claim.segment ? humanise(claim.segment) : 'Not triaged'}</td>
            <td>{claim.priority ?? '-'}</td>
            <td>{formatMoney(claim.estimated_exposure_minor, claim.currency)}</td>
            <td>
              <StatusBadge status={claim.status} />
            </td>
            <td>
              <SlaCell sla={claim.sla} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
