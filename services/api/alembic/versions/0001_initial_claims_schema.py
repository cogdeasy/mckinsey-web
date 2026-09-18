"""Initial claims schema.

Creates the claim aggregate, its append-only history tables, the audit trail, the outbox,
idempotency records and the claim reference sequence (FR-003).

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS claim_reference_seq START WITH 1 INCREMENT BY 1")
    op.create_table(
        "claim",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_reference", sa.String(length=20), nullable=False),
        sa.Column("policy_reference", sa.String(length=32), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("peril", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("loss_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("loss_description", sa.Text(), nullable=False),
        sa.Column("estimated_exposure_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("policyholder_name", sa.String(length=160), nullable=False),
        sa.Column("policyholder_email", sa.String(length=320), nullable=False),
        sa.Column("policyholder_phone", sa.String(length=32), nullable=True),
        sa.Column("incident_line1", sa.String(length=160), nullable=True),
        sa.Column("incident_city", sa.String(length=80), nullable=True),
        sa.Column("incident_postcode", sa.String(length=16), nullable=True),
        sa.Column("incident_country", sa.String(length=2), nullable=False),
        sa.Column("fraud_indicator", sa.Boolean(), nullable=False),
        sa.Column("duplicate_suspected", sa.Boolean(), nullable=False),
        sa.Column("awaiting_information", sa.Boolean(), nullable=False),
        sa.Column("segment", sa.String(length=24), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("queue", sa.String(length=48), nullable=True),
        sa.Column("acknowledgement_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_contact_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("pending_kind", sa.String(length=24), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_reference"),
    )
    op.create_index(
        "ix_claim_policy_loss", "claim", ["policy_reference", "loss_datetime"], unique=False
    )
    op.create_index(op.f("ix_claim_policy_reference"), "claim", ["policy_reference"], unique=False)
    op.create_index(op.f("ix_claim_queue"), "claim", ["queue"], unique=False)
    op.create_index("ix_claim_queue_priority", "claim", ["queue", "priority"], unique=False)
    op.create_index(op.f("ix_claim_segment"), "claim", ["segment"], unique=False)
    op.create_index(op.f("ix_claim_status"), "claim", ["status"], unique=False)
    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", "endpoint", name="uq_idempotency_key_endpoint"),
    )
    op.create_table(
        "outbox_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbox_entry_state"), "outbox_entry", ["state"], unique=False)
    op.create_index(op.f("ix_outbox_entry_topic"), "outbox_entry", ["topic"], unique=False)
    op.create_table(
        "audit_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=True),
        sa.Column("claim_reference", sa.String(length=20), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_event_actor_id"), "audit_event", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_event_claim_id"), "audit_event", ["claim_id"], unique=False)
    op.create_index(
        op.f("ix_audit_event_claim_reference"), "audit_event", ["claim_reference"], unique=False
    )
    op.create_index(
        op.f("ix_audit_event_correlation_id"), "audit_event", ["correlation_id"], unique=False
    )
    op.create_index(op.f("ix_audit_event_event_type"), "audit_event", ["event_type"], unique=False)
    op.create_table(
        "claim_document",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("uploaded_by", sa.String(length=64), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_claim_document_claim_id"), "claim_document", ["claim_id"], unique=False
    )
    op.create_table(
        "claim_transition",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_claim_transition_claim_id"), "claim_transition", ["claim_id"], unique=False
    )
    op.create_table(
        "payment_instruction",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payee_name", sa.String(length=160), nullable=False),
        sa.Column("payee_reference", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("instructed_by", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_instruction_claim_id"), "payment_instruction", ["claim_id"], unique=False
    )
    op.create_table(
        "reserve_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reserve_entry_claim_id"), "reserve_entry", ["claim_id"], unique=False)
    op.create_table(
        "triage_decision",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("segment", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("queue", sa.String(length=48), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("rule_set_version", sa.String(length=16), nullable=False),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claim.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_triage_decision_claim_id"), "triage_decision", ["claim_id"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_index(op.f("ix_triage_decision_claim_id"), table_name="triage_decision")
    op.drop_table("triage_decision")
    op.drop_index(op.f("ix_reserve_entry_claim_id"), table_name="reserve_entry")
    op.drop_table("reserve_entry")
    op.drop_index(op.f("ix_payment_instruction_claim_id"), table_name="payment_instruction")
    op.drop_table("payment_instruction")
    op.drop_index(op.f("ix_claim_transition_claim_id"), table_name="claim_transition")
    op.drop_table("claim_transition")
    op.drop_index(op.f("ix_claim_document_claim_id"), table_name="claim_document")
    op.drop_table("claim_document")
    op.drop_index(op.f("ix_audit_event_event_type"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_correlation_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_claim_reference"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_claim_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_actor_id"), table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index(op.f("ix_outbox_entry_topic"), table_name="outbox_entry")
    op.drop_index(op.f("ix_outbox_entry_state"), table_name="outbox_entry")
    op.drop_table("outbox_entry")
    op.drop_table("idempotency_record")
    op.drop_index(op.f("ix_claim_status"), table_name="claim")
    op.drop_index(op.f("ix_claim_segment"), table_name="claim")
    op.drop_index("ix_claim_queue_priority", table_name="claim")
    op.drop_index(op.f("ix_claim_queue"), table_name="claim")
    op.drop_index(op.f("ix_claim_policy_reference"), table_name="claim")
    op.drop_index("ix_claim_policy_loss", table_name="claim")
    op.drop_table("claim")
    op.execute("DROP SEQUENCE IF EXISTS claim_reference_seq")
