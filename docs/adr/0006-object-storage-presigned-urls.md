# ADR 0006: Claim documents in object storage via pre-signed URLs

- Status: Accepted
- Date: 2026-08-26
- Deciders: Claims Platform engineering, Information Security

## Context

Claims carry photographs, repair estimates and reports, typically 2–25 MB, at roughly 3.5
documents per claim. Streaming these through the API would dominate its resource profile and
couple availability of intake to availability of storage.

## Decision

Documents live in an S3-compatible bucket, one key prefix per claim. The API issues short-lived
pre-signed PUT URLs for upload and pre-signed GET URLs for download (FR-030, FR-033); bytes
never transit the API. Metadata, checksum and storage key are persisted, and the document
becomes visible on the timeline only once the client confirms the upload.

The bucket blocks public access, enforces server-side encryption and versioning, and has a
lifecycle policy matching the ten-year retention in NFR-008. Local development uses MinIO with
the same API.

## Consequences

- The API stays small and predictable; large uploads do not affect claim read latency.
- An abandoned upload leaves an orphaned object, reaped by a lifecycle rule on unconfirmed
  prefixes after seven days.
- Clients must handle a two-step upload, which the generated console client encapsulates.
