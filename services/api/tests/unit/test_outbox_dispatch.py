"""Unit tests for outbox dispatch semantics (FR-071) using an in-memory session double."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claims_intake.domain.enums import OutboxState
from claims_intake.models import OutboxEntry
from claims_intake.services import outbox


@dataclass
class FakeSession:
    entries: list[OutboxEntry] = field(default_factory=list)

    def scalars(self, _statement: Any) -> list[OutboxEntry]:
        return [entry for entry in self.entries if entry.state == OutboxState.PENDING.value]

    def scalar(self, _statement: Any) -> int:
        return len(self.entries)


def make_entry() -> OutboxEntry:
    return OutboxEntry(
        topic=outbox.TOPIC_CLAIM_REGISTERED,
        payload={"claim_reference": "MER-2026-000001"},
        correlation_id="c-1",
        state=OutboxState.PENDING.value,
        attempts=0,
    )


def test_fr071_successful_publish_marks_the_entry_sent() -> None:
    session = FakeSession(entries=[make_entry()])
    published = outbox.dispatch_batch(session, lambda _entry: None, batch_size=10, max_attempts=5)  # type: ignore[arg-type]
    assert published == 1
    assert session.entries[0].state == OutboxState.SENT.value
    assert session.entries[0].sent_at is not None


def test_fr071_entry_dead_letters_after_max_attempts() -> None:
    entry = make_entry()
    session = FakeSession(entries=[entry])

    def failing(_entry: OutboxEntry) -> None:
        raise RuntimeError("broker unavailable")

    for _ in range(5):
        outbox.dispatch_batch(session, failing, batch_size=10, max_attempts=5)  # type: ignore[arg-type]

    assert entry.attempts == 5
    assert entry.state == OutboxState.DEAD_LETTER.value
    assert entry.last_error == "broker unavailable"
