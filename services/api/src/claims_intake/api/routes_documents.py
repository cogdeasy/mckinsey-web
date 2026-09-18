"""Claim document endpoints (FR-030 to FR-033)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from ..schemas import (
    DocumentConfirm,
    DocumentCreate,
    DocumentUploadTicket,
    DocumentView,
    DownloadTicket,
)
from ..services import claims as claims_service
from ..services import documents as documents_service
from ..views import document_view
from .deps import (
    CorrelationDep,
    DocumentStoreDep,
    IdempotencyDep,
    PrincipalDep,
    SessionDep,
    SettingsDep,
)
from .responses import ERROR_RESPONSES, persisted, replayed

router = APIRouter(prefix="/v1/claims", tags=["documents"], responses=ERROR_RESPONSES)


@router.post(
    "/{claim_reference}/documents",
    response_model=DocumentUploadTicket,
    status_code=status.HTTP_201_CREATED,
    summary="Request a pre-signed upload URL",
)
def request_upload(
    claim_reference: str,
    payload: DocumentCreate,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
    settings: SettingsDep,
    store: DocumentStoreDep,
    idempotency_key: IdempotencyDep,
) -> Response:
    endpoint = f"POST /v1/claims/{claim_reference}/documents"
    body = payload.model_dump(mode="json")
    replay = replayed(session, key=idempotency_key, endpoint=endpoint, payload=body)
    if replay is not None:
        return replay

    claim = claims_service.get_claim(session, claim_reference)
    document, upload_url = documents_service.request_upload(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        payload=payload,
        store=store,
        settings=settings,
    )
    ticket = DocumentUploadTicket(
        document=document_view(document),
        upload_url=upload_url,
        storage_key=document.storage_key,
        expires_in_seconds=settings.presign_upload_ttl_seconds,
    )
    return persisted(
        session,
        key=idempotency_key,
        endpoint=endpoint,
        payload=body,
        status_code=status.HTTP_201_CREATED,
        model=ticket,
    )


@router.get(
    "/{claim_reference}/documents",
    response_model=list[DocumentView],
    summary="List claim documents",
)
def list_documents(
    claim_reference: str,
    session: SessionDep,
    principal: PrincipalDep,
) -> list[DocumentView]:
    claim = claims_service.get_claim(session, claim_reference, with_detail=True)
    return [document_view(document) for document in claim.documents]


@router.post(
    "/{claim_reference}/documents/{document_id}/confirm",
    response_model=DocumentView,
    summary="Confirm an upload and attach the document",
)
def confirm_upload(
    claim_reference: str,
    document_id: uuid.UUID,
    payload: DocumentConfirm,
    session: SessionDep,
    principal: PrincipalDep,
    correlation_id: CorrelationDep,
) -> DocumentView:
    claim = claims_service.get_claim(session, claim_reference)
    document = documents_service.get_document(session, claim=claim, document_id=document_id)
    confirmed = documents_service.confirm_upload(
        session,
        principal=principal,
        correlation_id=correlation_id,
        claim=claim,
        document=document,
        checksum_sha256=payload.checksum_sha256,
    )
    return document_view(confirmed)


@router.get(
    "/{claim_reference}/documents/{document_id}/download-url",
    response_model=DownloadTicket,
    summary="Issue a short-lived download URL",
)
def download_url(
    claim_reference: str,
    document_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
    store: DocumentStoreDep,
) -> DownloadTicket:
    claim = claims_service.get_claim(session, claim_reference)
    document = documents_service.get_document(session, claim=claim, document_id=document_id)
    url, ttl = documents_service.download_url(document=document, store=store, settings=settings)
    return DownloadTicket(download_url=url, expires_in_seconds=ttl)
