"""Unit tests for configuration guardrails (NFR-004)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from claims_intake.config import LOCAL_JWT_SECRET, Settings


def test_local_environment_may_use_the_development_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAIMS_JWT_SECRET", raising=False)
    settings = Settings(environment="local")

    assert settings.jwt_secret == LOCAL_JWT_SECRET


def test_deployed_environment_rejects_the_development_secret() -> None:
    with pytest.raises(ValidationError, match="CLAIMS_JWT_SECRET"):
        Settings(environment="staging", jwt_secret=LOCAL_JWT_SECRET)


def test_deployed_environment_accepts_an_injected_secret() -> None:
    settings = Settings(environment="prod", jwt_secret="injected-from-secrets-manager")

    assert settings.jwt_secret == "injected-from-secrets-manager"
