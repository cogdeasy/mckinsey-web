import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';

import { claimsApi } from '../api/client';
import { AuditTable } from '../components/AuditTable';
import { DocumentList } from '../components/DocumentList';
import { SlaCell } from '../components/SlaCell';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { TriageActions } from '../components/TriageActions';
import { formatDateTime, formatMoney, humanise } from '../lib/format';

export function ClaimPage() {
  const { claimReference = '' } = useParams();

  const claim = useQuery({
    queryKey: ['claim', claimReference],
    queryFn: () => claimsApi.getClaim(claimReference),
  });
  const timeline = useQuery({
    queryKey: ['timeline', claimReference],
    queryFn: () => claimsApi.getTimeline(claimReference),
    enabled: claim.isSuccess,
  });
  const audit = useQuery({
    queryKey: ['audit', claimReference],
    queryFn: () => claimsApi.getAuditEvents(claimReference),
    enabled: claim.isSuccess,
  });

  if (claim.isPending) {
    return <p className="empty">Loading claim {claimReference}.</p>;
  }
  if (claim.error) {
    return (
      <p className="error" role="alert">
        {claim.error.message}
      </p>
    );
  }

  const detail = claim.data;

  return (
    <section className="claim">
      <div className="page__heading">
        <Link to="/queue" className="back">
          Back to queue
        </Link>
        <h1>{detail.claim_reference}</h1>
        <div className="claim__chips">
          <StatusBadge status={detail.status} />
          {detail.triage ? (
            <span className="chip">
              {humanise(detail.triage.segment)} - priority {detail.triage.priority} -{' '}
              {detail.triage.queue}
            </span>
          ) : null}
          <SlaCell sla={detail.sla} />
        </div>
      </div>

      <div className="claim__grid">
        <section className="panel">
          <h2>Loss</h2>
          <dl className="facts">
            <dt>Policy</dt>
            <dd>{detail.policy_reference}</dd>
            <dt>Policyholder</dt>
            <dd>
              {detail.policyholder.full_name} ({detail.policyholder.email})
            </dd>
            <dt>Product and peril</dt>
            <dd>
              {humanise(detail.product)} - {humanise(detail.peril)}
            </dd>
            <dt>Loss date</dt>
            <dd>{formatDateTime(detail.loss_datetime)}</dd>
            <dt>Reported</dt>
            <dd>
              {formatDateTime(detail.reported_at)} via {humanise(detail.channel)}
            </dd>
            <dt>Estimated exposure</dt>
            <dd>{formatMoney(detail.estimated_exposure_minor, detail.currency)}</dd>
            <dt>Approved reserve</dt>
            <dd>{formatMoney(detail.indemnity_reserve_minor, detail.currency)}</dd>
            <dt>Settled</dt>
            <dd>{formatMoney(detail.settled_minor, detail.currency)}</dd>
          </dl>
          <p className="claim__description">{detail.loss_description}</p>
        </section>

        <TriageActions claim={detail} />

        <section className="panel">
          <h2>Timeline</h2>
          <Timeline entries={timeline.data ?? []} />
        </section>

        <section className="panel">
          <h2>Documents</h2>
          <DocumentList claimReference={detail.claim_reference} documents={detail.documents} />
        </section>

        <section className="panel panel--wide">
          <h2>Audit trail</h2>
          <AuditTable events={audit.data?.items ?? []} />
        </section>
      </div>
    </section>
  );
}
