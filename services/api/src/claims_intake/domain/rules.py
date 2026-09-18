"""Declarative, versioned triage rule sets (FR-020 to FR-024, ADR 0004).

The evaluator is pure and first-match-wins. The fact schema is closed: a rule that references
an unknown fact fails validation at load time so the service refuses to start on a bad rule
set.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..errors import ValidationError
from .enums import Channel, Peril, Product, Segment

FACT_TYPES: dict[str, type] = {
    "product": str,
    "peril": str,
    "estimated_exposure_minor": int,
    "fraud_indicator": bool,
    "duplicate_suspected": bool,
    "channel": str,
    "days_since_loss": int,
    "policyholder_country": str,
}

OPERATORS = frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in"})

COMPLEX_EXPOSURE_THRESHOLD_MINOR = 1_000_000
"""Above this exposure a claim may never be fast-tracked (FR-023)."""


@dataclass(frozen=True)
class TriageOutcome:
    segment: Segment
    priority: int
    queue: str


@dataclass(frozen=True)
class TriageDecision:
    outcome: TriageOutcome
    rule_id: str
    rule_set_version: str


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    conditions: Mapping[str, Mapping[str, Any]]
    outcome: TriageOutcome

    def matches(self, facts: Mapping[str, Any]) -> bool:
        return all(
            _compare(facts[fact], operator, expected)
            for fact, predicate in self.conditions.items()
            for operator, expected in predicate.items()
        )


@dataclass(frozen=True)
class RuleSet:
    version: str
    rules: tuple[Rule, ...]
    default: TriageOutcome
    default_rule_id: str = "default"

    def evaluate(self, facts: Mapping[str, Any]) -> TriageDecision:
        validate_facts(facts)
        for rule in self.rules:
            if rule.matches(facts):
                return TriageDecision(rule.outcome, rule.rule_id, self.version)
        return TriageDecision(self.default, self.default_rule_id, self.version)


def _compare(value: Any, operator: str, expected: Any) -> bool:
    match operator:
        case "eq":
            return bool(value == expected)
        case "ne":
            return bool(value != expected)
        case "gt":
            return bool(value > expected)
        case "gte":
            return bool(value >= expected)
        case "lt":
            return bool(value < expected)
        case "lte":
            return bool(value <= expected)
        case "in":
            return value in expected
        case "not_in":
            return value not in expected
        case _:  # pragma: no cover - guarded by rule set validation
            raise ValidationError(f"Unsupported operator {operator}")


def validate_facts(facts: Mapping[str, Any]) -> None:
    missing = sorted(set(FACT_TYPES) - set(facts))
    if missing:
        raise ValidationError("Triage facts are incomplete", {"missing": missing})
    unknown = sorted(set(facts) - set(FACT_TYPES))
    if unknown:
        raise ValidationError("Unknown triage facts supplied", {"unknown": unknown})


def _parse_outcome(raw: Mapping[str, Any], context: str) -> TriageOutcome:
    try:
        segment = Segment(raw["segment"])
        priority = int(raw["priority"])
        queue = str(raw["queue"])
    except (KeyError, ValueError) as exc:
        raise ValidationError(f"Invalid outcome in {context}: {exc}") from exc
    if not 1 <= priority <= 5:
        raise ValidationError(f"Priority in {context} must be between 1 and 5")
    return TriageOutcome(segment=segment, priority=priority, queue=queue)


def parse_rule_set(document: Mapping[str, Any]) -> RuleSet:
    """Validate and build a rule set from its YAML representation."""

    version = str(document.get("version", "")).strip()
    if not version:
        raise ValidationError("Rule set is missing a version")
    if "default" not in document:
        raise ValidationError("Rule set is missing the mandatory default outcome")

    rules: list[Rule] = []
    seen: set[str] = set()
    for index, raw_rule in enumerate(document.get("rules") or []):
        rule_id = str(raw_rule.get("id", "")).strip()
        if not rule_id:
            raise ValidationError(f"Rule at position {index} has no id")
        if rule_id in seen:
            raise ValidationError(f"Duplicate rule id {rule_id}")
        seen.add(rule_id)

        conditions = raw_rule.get("when") or {}
        for fact, predicate in conditions.items():
            if fact not in FACT_TYPES:
                raise ValidationError(
                    f"Rule {rule_id} references unknown fact {fact}",
                    {"known_facts": sorted(FACT_TYPES)},
                )
            if not isinstance(predicate, Mapping) or not predicate:
                raise ValidationError(f"Rule {rule_id} has an empty predicate for {fact}")
            for operator in predicate:
                if operator not in OPERATORS:
                    raise ValidationError(
                        f"Rule {rule_id} uses unsupported operator {operator}",
                        {"supported": sorted(OPERATORS)},
                    )

        outcome = _parse_outcome(raw_rule.get("then") or {}, f"rule {rule_id}")
        rules.append(
            Rule(
                rule_id=rule_id,
                description=str(raw_rule.get("description", "")),
                conditions=conditions,
                outcome=outcome,
            )
        )

    rule_set = RuleSet(
        version=version,
        rules=tuple(rules),
        default=_parse_outcome(document["default"], "the default outcome"),
    )
    _assert_fast_track_guardrail(rule_set)
    return rule_set


def _assert_fast_track_guardrail(rule_set: RuleSet) -> None:
    """FR-023: high exposure or a fraud indicator must never reach FAST_TRACK."""

    offenders = [
        rule.rule_id
        for rule in rule_set.rules
        if rule.outcome.segment is Segment.FAST_TRACK and not _bounds_exposure(rule)
    ]
    if offenders or rule_set.default.segment is Segment.FAST_TRACK:
        raise ValidationError(
            "Fast-track rules must bound estimated exposure below the complex threshold",
            {"rules": offenders or [rule_set.default_rule_id]},
        )


def _bounds_exposure(rule: Rule) -> bool:
    predicate = rule.conditions.get("estimated_exposure_minor")
    if not predicate:
        return False
    for operator, expected in predicate.items():
        if operator in {"lt", "lte"} and int(expected) <= COMPLEX_EXPOSURE_THRESHOLD_MINOR:
            return True
    return False


def load_rule_set(path: Path) -> RuleSet:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, Mapping):
        raise ValidationError(f"Rule set at {path} is not a mapping")
    return parse_rule_set(document)


def build_facts(
    *,
    product: Product,
    peril: Peril,
    estimated_exposure_minor: int,
    fraud_indicator: bool,
    duplicate_suspected: bool,
    channel: Channel,
    days_since_loss: int,
    policyholder_country: str,
) -> dict[str, Any]:
    return {
        "product": product.value,
        "peril": peril.value,
        "estimated_exposure_minor": estimated_exposure_minor,
        "fraud_indicator": fraud_indicator,
        "duplicate_suspected": duplicate_suspected,
        "channel": channel.value,
        "days_since_loss": days_since_loss,
        "policyholder_country": policyholder_country,
    }
