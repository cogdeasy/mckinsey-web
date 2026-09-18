"""Claim reference formatting (FR-003)."""

from __future__ import annotations

import re

REFERENCE_PATTERN = re.compile(r"^MER-\d{4}-\d{6}$")
PREFIX = "MER"


def format_reference(year: int, sequence: int) -> str:
    if sequence < 1 or sequence > 999_999:
        raise ValueError("sequence must be between 1 and 999999")
    return f"{PREFIX}-{year:04d}-{sequence:06d}"


def is_valid_reference(value: str) -> bool:
    return bool(REFERENCE_PATTERN.match(value))
