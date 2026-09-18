"""Seed a local database with representative claims for development and demos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import session_scope
from .domain.enums import Channel, ClaimStatus, Peril, Product, ReserveCategory, Role
from .domain.rules import load_rule_set
from .models import Claim
from .observability.logging import configure_logging, get_logger
from .schemas import Address, ApprovalCreate, ClaimCreate, Policyholder, ReserveCreate
from .security import Principal
from .services import claims as claims_service

logger = get_logger("claims_intake.seed")

HANDLER = Principal(
    subject="d.okafor",
    display_name="Dana Okafor",
    roles=frozenset({Role.CLAIMS_HANDLER}),
)
SENIOR = Principal(
    subject="o.haddad",
    display_name="Omar Haddad",
    roles=frozenset({Role.SENIOR_HANDLER}),
)


class SeedClaim(TypedDict):
    policy_reference: str
    product: Product
    peril: Peril
    exposure: int
    name: str
    email: str
    description: str
    days_ago: int
    fraud: bool


SEED_CLAIMS: list[SeedClaim] = [
    {
        "policy_reference": "POL-88213371",
        "product": Product.MOTOR,
        "peril": Peril.COLLISION,
        "exposure": 480_000,
        "name": "Rowan Whitfield",
        "email": "rowan.whitfield@example.com",
        "description": "Rear-ended at a junction on the A34, third party admitted liability.",
        "days_ago": 4,
        "fraud": False,
    },
    {
        "policy_reference": "POL-90117742",
        "product": Product.MOTOR,
        "peril": Peril.ACCIDENTAL_DAMAGE,
        "exposure": 62_000,
        "name": "Ines Baptista",
        "email": "ines.baptista@example.com",
        "description": "Windscreen cracked by a stone on the M40, vehicle still driveable.",
        "days_ago": 1,
        "fraud": False,
    },
    {
        "policy_reference": "POL-77410093",
        "product": Product.HOME,
        "peril": Peril.ESCAPE_OF_WATER,
        "exposure": 940_000,
        "name": "Marcus Elling",
        "email": "marcus.elling@example.com",
        "description": "Burst pipe under the kitchen floor, drying and strip-out needed.",
        "days_ago": 9,
        "fraud": False,
    },
    {
        "policy_reference": "POL-66220841",
        "product": Product.HOME,
        "peril": Peril.FIRE,
        "exposure": 4_250_000,
        "name": "Sofia Lindqvist",
        "email": "sofia.lindqvist@example.com",
        "description": "Kitchen fire spread to the first floor, property uninhabitable.",
        "days_ago": 12,
        "fraud": False,
    },
    {
        "policy_reference": "POL-51938820",
        "product": Product.TRAVEL,
        "peril": Peril.CANCELLATION,
        "exposure": 48_000,
        "name": "Ahmed Rashid",
        "email": "ahmed.rashid@example.com",
        "description": "Trip cancelled after a documented medical emergency before departure.",
        "days_ago": 2,
        "fraud": False,
    },
    {
        "policy_reference": "POL-43900217",
        "product": Product.MOTOR,
        "peril": Peril.THEFT,
        "exposure": 1_850_000,
        "name": "Delia Marchetti",
        "email": "delia.marchetti@example.com",
        "description": "Vehicle taken from a driveway overnight, keys reported still in hand.",
        "days_ago": 6,
        "fraud": True,
    },
    {
        "policy_reference": "POL-31882204",
        "product": Product.TRAVEL,
        "peril": Peril.MEDICAL,
        "exposure": 310_000,
        "name": "Tomas Vlk",
        "email": "tomas.vlk@example.com",
        "description": (
            "Hospital admission abroad, repatriation being arranged by the assistance desk."
        ),
        "days_ago": 40,
        "fraud": False,
    },
    {
        "policy_reference": "POL-20447731",
        "product": Product.HOME,
        "peril": Peril.LIABILITY,
        "exposure": 760_000,
        "name": "Grace Adeyemi",
        "email": "grace.adeyemi@example.com",
        "description": "Visitor injured by a falling boundary wall, third party claim notified.",
        "days_ago": 15,
        "fraud": False,
    },
]


def seed(session: Session) -> int:
    settings = get_settings()
    rule_set = load_rule_set(settings.rule_set_path)
    existing = session.scalar(select(Claim).limit(1))
    if existing is not None:
        logger.info("seed.skipped", extra={"reason": "claims already present"})
        return 0

    now = datetime.now(tz=UTC)
    created = 0
    for index, row in enumerate(SEED_CLAIMS):
        payload = ClaimCreate(
            policy_reference=row["policy_reference"],
            product=row["product"],
            peril=row["peril"],
            channel=Channel.CONTACT_CENTRE if index % 2 == 0 else Channel.PORTAL,
            loss_datetime=now - timedelta(days=row["days_ago"], hours=3),
            loss_description=row["description"],
            estimated_exposure_minor=row["exposure"],
            currency="GBP",
            policyholder=Policyholder(
                full_name=row["name"], email=row["email"], phone="+441865000000"
            ),
            incident_location=Address(
                line1="12 Beaumont Street", city="Oxford", postcode="OX1 2NP", country="GB"
            ),
            fraud_indicator=row["fraud"],
        )
        claim = claims_service.register_claim(
            session,
            principal=HANDLER,
            correlation_id=f"seed-{index:02d}",
            payload=payload,
            rule_set=rule_set,
        )
        created += 1

        if index % 3 == 0:
            claims_service.propose_reserve(
                session,
                principal=HANDLER,
                correlation_id=f"seed-{index:02d}",
                claim=claim,
                payload=ReserveCreate(
                    category=ReserveCategory.INDEMNITY,
                    amount_minor=min(int(str(row["exposure"])), 240_000),
                    currency="GBP",
                    note="Initial reserve from the desk estimate.",
                ),
            )
        if index % 4 == 1:
            claims_service.propose_reserve(
                session,
                principal=HANDLER,
                correlation_id=f"seed-{index:02d}",
                claim=claim,
                payload=ReserveCreate(
                    category=ReserveCategory.INDEMNITY,
                    amount_minor=int(str(row["exposure"])) + 100_000,
                    currency="GBP",
                    note="Engineer estimate exceeds the handler limit.",
                ),
            )
            if ClaimStatus(claim.status) is ClaimStatus.PENDING_APPROVAL:
                claims_service.decide_approval(
                    session,
                    principal=SENIOR,
                    correlation_id=f"seed-{index:02d}",
                    claim=claim,
                    approve=ApprovalCreate(decision="APPROVE", note="Estimate reviewed.").decision
                    == "APPROVE",
                    note="Estimate reviewed and accepted.",
                )
    return created


def main() -> None:  # pragma: no cover - script entry point
    settings = get_settings()
    configure_logging(settings.log_level, settings.service_name, settings.environment)
    with session_scope() as session:
        created = seed(session)
    logger.info("seed.completed", extra={"claims_created": created})


if __name__ == "__main__":  # pragma: no cover
    main()
