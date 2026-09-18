import type { components, paths } from './schema';

import { readApiConfig } from './config';

export type ClaimSummary = components['schemas']['ClaimSummary'];
export type ClaimDetail = components['schemas']['ClaimDetail'];
export type TimelineEntry = components['schemas']['TimelineEntry'];
export type AuditEventView = components['schemas']['AuditEventView'];
export type DocumentView = components['schemas']['DocumentView'];
export type ReserveView = components['schemas']['ReserveView'];
export type ClaimStatus = components['schemas']['ClaimStatus'];
export type Segment = components['schemas']['Segment'];
export type ReasonCode = components['schemas']['ReasonCode'];
export type ErrorResponse = components['schemas']['ErrorResponse'];

export type ClaimPage = components['schemas']['Page_ClaimSummary_'];
export type AuditPage = components['schemas']['Page_AuditEventView_'];
export type QueueQuery = NonNullable<paths['/v1/claims']['get']['parameters']['query']>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string;

  constructor(status: number, body: ErrorResponse) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.correlationId = body.correlation_id;
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  return typeof value === 'object' && value !== null && 'code' in value && 'message' in value;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { baseUrl, token } = readApiConfig();
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  const text = await response.text();
  const payload: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    if (isErrorResponse(payload)) {
      throw new ApiError(response.status, payload);
    }
    throw new Error(`The claims API returned ${response.status}`);
  }
  return payload as T;
}

function queryString(query: QueueQuery): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  const serialised = params.toString();
  return serialised ? `?${serialised}` : '';
}

function idempotent(headers: Record<string, string> = {}): Record<string, string> {
  return { 'Idempotency-Key': crypto.randomUUID(), ...headers };
}

export const claimsApi = {
  listClaims: (query: QueueQuery = {}) => request<ClaimPage>(`/v1/claims${queryString(query)}`),

  getClaim: (claimReference: string) =>
    request<ClaimDetail>(`/v1/claims/${encodeURIComponent(claimReference)}`),

  getTimeline: (claimReference: string) =>
    request<TimelineEntry[]>(`/v1/claims/${encodeURIComponent(claimReference)}/timeline`),

  getAuditEvents: (claimReference: string) =>
    request<AuditPage>(`/v1/claims/${encodeURIComponent(claimReference)}/audit-events`),

  getDocuments: (claimReference: string) =>
    request<DocumentView[]>(`/v1/claims/${encodeURIComponent(claimReference)}/documents`),

  getDownloadUrl: (claimReference: string, documentId: string) =>
    request<components['schemas']['DownloadTicket']>(
      `/v1/claims/${encodeURIComponent(claimReference)}/documents/${documentId}/download-url`,
    ),

  transition: (claimReference: string, body: components['schemas']['TransitionCreate']) =>
    request<components['schemas']['TransitionView']>(
      `/v1/claims/${encodeURIComponent(claimReference)}/transitions`,
      { method: 'POST', body: JSON.stringify(body), headers: idempotent() },
    ),

  rerunTriage: (claimReference: string) =>
    request<components['schemas']['TriageView']>(
      `/v1/claims/${encodeURIComponent(claimReference)}/triage`,
      { method: 'POST' },
    ),

  setReserve: (claimReference: string, body: components['schemas']['ReserveCreate']) =>
    request<components['schemas']['ReserveResult']>(
      `/v1/claims/${encodeURIComponent(claimReference)}/reserves`,
      { method: 'POST', body: JSON.stringify(body), headers: idempotent() },
    ),
};
