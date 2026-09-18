"""Object storage access for claim documents (ADR 0006, FR-030 to FR-033)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.config import Config

from .config import Settings
from .errors import UnsupportedMediaTypeError, ValidationError

ALLOWED_CONTENT_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/heic"})


@dataclass(frozen=True)
class PresignedUpload:
    storage_key: str
    upload_url: str
    expires_in_seconds: int


class DocumentStore(Protocol):
    """Narrow port so tests can substitute a stub for S3."""

    def presign_upload(self, key: str, content_type: str, ttl: int) -> str: ...

    def presign_download(self, key: str, ttl: int) -> str: ...

    def healthy(self) -> bool: ...


class S3DocumentStore:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.documents_bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def presign_upload(self, key: str, content_type: str, ttl: int) -> str:
        return str(
            self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=ttl,
            )
        )

    def presign_download(self, key: str, ttl: int) -> str:
        return str(
            self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl,
            )
        )

    def healthy(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:  # noqa: BLE001 - readiness must never raise
            return False
        return True


def build_storage_key(claim_reference: str, filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"claims/{claim_reference}/{uuid.uuid4()}.{suffix}"


def validate_document(content_type: str, size_bytes: int, settings: Settings) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedMediaTypeError(
            f"Content type {content_type} is not accepted for claim documents",
            {"allowed": sorted(ALLOWED_CONTENT_TYPES)},
        )
    if size_bytes <= 0 or size_bytes > settings.max_document_bytes:
        raise ValidationError(
            "Document size must be between 1 byte and the configured maximum",
            {"max_bytes": settings.max_document_bytes},
        )
