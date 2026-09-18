import type { AuditEventView, ClaimDetail, ClaimSummary, TimelineEntry } from '../api/client';

export const motorClaim: ClaimSummary = {
  claim_reference: 'MER-2026-000101',
  policy_reference: 'POL-88213371',
  product: 'MOTOR',
  peril: 'COLLISION',
  status: 'TRIAGED',
  segment: 'STANDARD',
  priority: 3,
  queue: 'motor-standard',
  policyholder_name: 'Rowan Whitfield',
  estimated_exposure_minor: 480_000,
  currency: 'GBP',
  duplicate_suspected: false,
  reported_at: '2026-09-14T09:30:00Z',
  sla: {
    acknowledgement_due_at: '2026-09-14T13:30:00Z',
    first_contact_due_at: '2026-09-15T09:30:00Z',
    decision_due_at: '2026-10-05T09:30:00Z',
    awaiting_information: false,
    breached: false,
  },
};

export const breachedClaim: ClaimSummary = {
  ...motorClaim,
  claim_reference: 'MER-2026-000102',
  policyholder_name: 'Ines Baptista',
  status: 'IN_ASSESSMENT',
  segment: 'COMPLEX',
  priority: 1,
  queue: 'large-loss',
  duplicate_suspected: true,
  estimated_exposure_minor: 2_400_000,
  sla: { ...motorClaim.sla, breached: true },
};

export const claimDetail: ClaimDetail = {
  ...motorClaim,
  id: '8f0a3b0e-0c57-4a2a-9d7c-1f8a5c2f9a11',
  channel: 'CONTACT_CENTRE',
  loss_datetime: '2026-09-12T18:05:00Z',
  loss_description: 'Rear-ended at a junction on the A34, third party admitted liability.',
  fraud_indicator: false,
  incident_location: {
    line1: 'A34 Botley interchange',
    city: 'Oxford',
    postcode: 'OX2 9RS',
    country: 'GB',
  },
  policyholder: {
    full_name: 'Rowan Whitfield',
    email: 'rowan.whitfield@example.com',
    phone: '+44 7700 900123',
  },
  triage: {
    segment: 'STANDARD',
    priority: 3,
    queue: 'motor-standard',
    rule_id: 'motor-standard',
    rule_set_version: '1.3.0',
    decided_at: '2026-09-14T09:30:05Z',
  },
  reserves: [],
  documents: [
    {
      id: '2b2a4a67-0b3e-4a50-9d54-1c1d8f6f0b21',
      filename: 'engineer-report.pdf',
      content_type: 'application/pdf',
      size_bytes: 482_133,
      kind: 'ESTIMATE',
      state: 'AVAILABLE',
      uploaded_by: 'd.okafor',
      created_at: '2026-09-14T11:02:00Z',
      confirmed_at: '2026-09-14T11:03:00Z',
    },
  ],
  payments: [],
  indemnity_reserve_minor: 0,
  settled_minor: 0,
  pending_amount_minor: null,
  created_at: '2026-09-14T09:30:00Z',
  updated_at: '2026-09-14T09:30:05Z',
};

export const timelineEntries: TimelineEntry[] = [
  {
    kind: 'TRANSITION',
    occurred_at: '2026-09-14T09:30:00Z',
    summary: 'Claim registered',
    actor_id: 'd.okafor',
  },
  {
    kind: 'TRIAGE',
    occurred_at: '2026-09-14T09:30:05Z',
    summary: 'Routed to motor-standard by rule motor-standard',
    actor_id: 'd.okafor',
  },
];

export const auditEvents: AuditEventView[] = [
  {
    id: 'a2a1b2c3-d4e5-4f60-8a1b-2c3d4e5f6071',
    event_type: 'claim.registered',
    actor_id: 'd.okafor',
    actor_role: 'claims_handler',
    claim_reference: 'MER-2026-000101',
    payload: {},
    correlation_id: '0f8c1f1e-2f2d-4a0e-9a2b-2a9d9c6f1c4a',
    payload_digest: 'c0ffee1234567890abcdef',
    created_at: '2026-09-14T09:30:00Z',
  },
];
