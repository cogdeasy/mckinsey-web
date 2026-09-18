"""Claim document lifecycle (FR-030 to FR-033, ADR 0006)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..domain.enums import DocumentState
from ..errors import NotFoundError
from ..models import Claim, ClaimDocument
from ..schemas import DocumentCreate
from ..security import Principal
from ..storage import DocumentStore, build_storage_key, validate_document
from . import audit


def request_upload(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    payload: DocumentCreate,
    store: DocumentStore,
    settings: Settings,
) -> tuple[ClaimDocument, str]:
    principal.require_write()
    validate_document(payload.content_type, payload.size_bytes, settings)

    key = build_storage_key(claim.claim_reference, payload.filename)
    document = ClaimDocument(
        claim=claim,
        filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        kind=payload.kind.value,
        storage_key=key,
        state=DocumentState.AWAITING_UPLOAD.value,
        uploaded_by=principal.subject,
    )
    session.add(document)
    upload_url = store.presign_upload(
        key, payload.content_type, settings.presign_upload_ttl_seconds
    )
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.document_requested",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={"filename": document.filename, "kind": document.kind, "storage_key": key},
    )
    session.flush()
    return document, upload_url


def get_document(session: Session, *, claim: Claim, document_id: uuid.UUID) -> ClaimDocument:
    document = session.scalar(
        select(ClaimDocument).where(
            ClaimDocument.id == document_id, ClaimDocument.claim_id == claim.id
        )
    )
    if document is None:
        raise NotFoundError("No such document on this claim", {"document_id": str(document_id)})
    return document


def confirm_upload(
    session: Session,
    *,
    principal: Principal,
    correlation_id: str,
    claim: Claim,
    document: ClaimDocument,
    checksum_sha256: str,
) -> ClaimDocument:
    principal.require_write()
    document.checksum_sha256 = checksum_sha256
    document.state = DocumentState.AVAILABLE.value
    document.confirmed_at = datetime.now(tz=UTC)
    audit.record(
        session,
        principal=principal,
        correlation_id=correlation_id,
        event_type="claim.document_attached",
        claim_id=claim.id,
        claim_reference=claim.claim_reference,
        payload={
            "document_id": str(document.id),
            "checksum_sha256": checksum_sha256,
            "size_bytes": document.size_bytes,
        },
    )
    session.flush()
    return document


def download_url(
    *, document: ClaimDocument, store: DocumentStore, settings: Settings
) -> tuple[str, int]:
    if document.state != DocumentState.AVAILABLE.value:
        raise NotFoundError(
            "The document upload has not been confirmed", {"document_id": str(document.id)}
        )
    ttl = settings.presign_download_ttl_seconds
    return store.presign_download(document.storage_key, ttl), ttl
