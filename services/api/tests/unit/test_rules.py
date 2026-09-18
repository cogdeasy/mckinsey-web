"""Unit tests for the triage rule engine (FR-020 to FR-024, ADR 0004)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from claims_intake.domain.enums import Channel, Peril, Product, Segment
from claims_intake.domain.rules import (
    build_facts,
    load_rule_set,
    parse_rule_set,
)
from claims_intake.errors import ValidationError

RULE_SET_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "claims_intake" / "rules" / "triage.yaml"
)


def facts(**overrides: Any) -> dict[str, Any]:
    base = build_facts(
        product=Product.MOTOR,
        peril=Peril.COLLISION,
        estimated_exposure_minor=50_000,
        fraud_indicator=False,
        duplicate_suspected=False,
        channel=Channel.CONTACT_CENTRE,
        days_since_loss=2,
        policyholder_country="GB",
    )
    base.update(overrides)
    return base


def test_fr022_first_matching_rule_wins() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(facts(fraud_indicator=True, estimated_exposure_minor=10_000))
    assert decision.rule_id == "fraud-referral"
    assert decision.outcome.segment is Segment.SPECIAL_INVESTIGATION


def test_fr022_default_guarantees_a_decision() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(
        facts(product=Product.TRAVEL, peril=Peril.THEFT, estimated_exposure_minor=20_000)
    )
    assert decision.rule_id == "default"
    assert decision.outcome.queue == "general-standard"


def test_fr023_high_exposure_is_never_fast_tracked() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(facts(estimated_exposure_minor=5_000_000))
    assert decision.outcome.segment is not Segment.FAST_TRACK
    assert decision.outcome.segment is Segment.COMPLEX


def test_fr023_fraud_is_never_fast_tracked() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(facts(fraud_indicator=True, estimated_exposure_minor=1_000))
    assert decision.outcome.segment is not Segment.FAST_TRACK


def test_fr021_decision_carries_the_rule_set_version() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(facts())
    assert decision.rule_set_version == rule_set.version


def test_low_value_motor_damage_is_fast_tracked() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    decision = rule_set.evaluate(
        facts(peril=Peril.ACCIDENTAL_DAMAGE, estimated_exposure_minor=60_000)
    )
    assert decision.outcome.segment is Segment.FAST_TRACK
    assert decision.outcome.queue == "motor-fast-track"


def test_unknown_fact_in_a_rule_is_rejected_at_load_time() -> None:
    with pytest.raises(ValidationError) as error:
        parse_rule_set(
            {
                "version": "9.9.9",
                "rules": [
                    {
                        "id": "bad",
                        "when": {"handler_mood": {"eq": "sunny"}},
                        "then": {"segment": "STANDARD", "priority": 3, "queue": "q"},
                    }
                ],
                "default": {"segment": "STANDARD", "priority": 3, "queue": "q"},
            }
        )
    assert "handler_mood" in str(error.value)


def test_unsupported_operator_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_rule_set(
            {
                "version": "9.9.9",
                "rules": [
                    {
                        "id": "bad-operator",
                        "when": {"peril": {"matches": "COLL.*"}},
                        "then": {"segment": "STANDARD", "priority": 3, "queue": "q"},
                    }
                ],
                "default": {"segment": "STANDARD", "priority": 3, "queue": "q"},
            }
        )


def test_fr023_unbounded_fast_track_rule_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_rule_set(
            {
                "version": "9.9.9",
                "rules": [
                    {
                        "id": "reckless-fast-track",
                        "when": {"product": {"eq": "MOTOR"}},
                        "then": {"segment": "FAST_TRACK", "priority": 4, "queue": "q"},
                    }
                ],
                "default": {"segment": "STANDARD", "priority": 3, "queue": "q"},
            }
        )


def test_incomplete_facts_are_rejected() -> None:
    rule_set = load_rule_set(RULE_SET_PATH)
    with pytest.raises(ValidationError):
        rule_set.evaluate({"product": "MOTOR"})


def test_rule_set_requires_a_default() -> None:
    with pytest.raises(ValidationError):
        parse_rule_set({"version": "1.0.0", "rules": []})
