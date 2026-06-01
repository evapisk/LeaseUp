"""Analysis-card enrichment pipeline.

``enrich_card`` resolves a restaurant by CAMIS (then name+address), hydrates from
Socrata when local data is thin, rebuilds an authoritative card summary from the
DB, calls codify for AI risk + takeover steps, and assembles the
``EnrichResponse`` envelope. It NEVER 5xxs on codify/Socrata failure — it degrades
to a deterministic local fallback and returns 200. The ``card`` stays strictly
schema-conformant; all AI/meta live in the sibling envelope fields.

Does NOT import ``api.py`` (would be circular) — ORM -> schema mapping is local.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import normalize as N
from .codify_client import CodifyClient, CodifyUnavailable
from .config import get_settings
from .db import SessionLocal
from .hydration import force_rehydrate, hydrate_query
from .models import (
    ScoutEatsComplianceEvent,
    ScoutEatsEstablishment,
    ScoutEatsIdentifier,
    ScoutEatsViolation,
)
from .schemas import (
    AnalysisCardPayload,
    CardSummary,
    CategoryBreakdown,
    ComplianceEventDetail,
    EnrichmentMeta,
    EnrichResponse,
    RestaurantIdentity,
    RiskAssessment,
    TakeoverPlan,
    ViolationDetail,
)
from .takeover import build_fallback_plan, merge_codify_plan

logger = logging.getLogger("scouteats.enrichment")


# -- identity resolution ------------------------------------------------------


def _resolve_establishment(
    session: Session, card: AnalysisCardPayload
) -> ScoutEatsEstablishment | None:
    """Find by CAMIS identifier, then by (name, address)."""
    camis = N.normalize_identifier(card.restaurant.camis)
    if camis:
        ident = session.scalar(
            select(ScoutEatsIdentifier).where(
                ScoutEatsIdentifier.id_type == N.ID_CAMIS,
                ScoutEatsIdentifier.id_value == camis,
            )
        )
        if ident is not None:
            return ident.establishment
    name = card.restaurant.name
    address = card.restaurant.address
    if name and address:
        return session.scalar(
            select(ScoutEatsEstablishment).where(
                ScoutEatsEstablishment.display_name == name,
                ScoutEatsEstablishment.address == address,
            )
        )
    return None


def _is_thin(est: ScoutEatsEstablishment | None, violation_count: int) -> bool:
    """Thin = no establishment, no violations, or no inspection date."""
    if est is None:
        return True
    if violation_count == 0:
        return True
    return est.last_inspection_date is None


def _count_violations(session: Session, establishment_id: int) -> int:
    return len(
        list(
            session.scalars(
                select(ScoutEatsViolation.id).where(
                    ScoutEatsViolation.establishment_id == establishment_id
                )
            )
        )
    )


# -- ORM -> schema mapping ----------------------------------------------------


def _date_only(dt: datetime | None):
    return dt.date() if dt else None


def _map_violation(v: ScoutEatsViolation) -> ViolationDetail:
    meta = v.metadata_json or {}
    return ViolationDetail(
        code=v.violation_type,
        category=N.category_for_code(v.violation_type),
        severity=v.severity if v.severity in ("critical", "not_critical") else None,
        status=v.status,
        description=v.description,
        inspection_type=meta.get("inspection_type"),
        issue_date=_date_only(v.issue_date),
    )


def _map_compliance(c: ScoutEatsComplianceEvent) -> ComplianceEventDetail | None:
    if c.event_type not in ("closed", "re-closed", "re-opened"):
        return None
    return ComplianceEventDetail(
        event_type=c.event_type,
        event_date=_date_only(c.event_date),
        action_text=c.action_text,
    )


def _build_summary(
    est: ScoutEatsEstablishment, violations: list[ScoutEatsViolation]
) -> CardSummary:
    """Authoritative summary rebuilt from DB violations + establishment."""
    total = len(violations)
    critical = sum(1 for v in violations if v.severity == "critical")
    breakdown = N.category_breakdown(
        v.violation_type for v in violations if v.violation_type
    )
    categories = sorted(breakdown.keys())
    return CardSummary(
        total_violations=total,
        critical_violations=critical,
        risk=N.risk_for(critical),
        is_closed=bool(est.is_closed),
        categories=categories,
        category_breakdown=[
            CategoryBreakdown(category=cat, count=cnt)
            for cat, cnt in sorted(breakdown.items())
        ],
        latest_grade=est.latest_grade,
        latest_score=est.latest_score,
        last_inspection_date=_date_only(est.last_inspection_date),
        last_closure_date=_date_only(est.last_closure_date),
    )


def _build_identity(
    est: ScoutEatsEstablishment, submitted: RestaurantIdentity
) -> RestaurantIdentity:
    return RestaurantIdentity(
        camis=est.camis or submitted.camis,
        name=est.display_name or submitted.name,
        address=est.address or submitted.address,
        borough=N.canonical_borough(est.borough) or submitted.borough,
        zip=est.zipcode or submitted.zip,
        cuisine=est.cuisine or submitted.cuisine,
        latitude=est.latitude if est.latitude is not None else submitted.latitude,
        longitude=est.longitude if est.longitude is not None else submitted.longitude,
    )


def _idempotency_key(card: AnalysisCardPayload) -> str:
    camis = card.restaurant.camis or ""
    last = (
        card.summary.last_inspection_date.isoformat()
        if card.summary.last_inspection_date
        else ""
    )
    return hashlib.sha256(f"{camis}{last}".encode("utf-8")).hexdigest()


# -- pipeline -----------------------------------------------------------------


async def enrich_card(payload: AnalysisCardPayload) -> EnrichResponse:
    settings = get_settings()
    notes: list[str] = []
    camis = N.normalize_identifier(payload.restaurant.camis)

    # (a) resolve + (b) hydrate when thin.
    matched = False
    hydrated = False
    with SessionLocal() as session:
        est = _resolve_establishment(session, payload)
        matched = est is not None
        vio_count = _count_violations(session, est.id) if est else 0
        est_id = est.id if est else None

    if _is_thin(est, vio_count):
        try:
            if est_id is not None:
                result = await force_rehydrate(est_id)
                hydrated = not result.get("error")
                if hydrated:
                    notes.append("rehydrated full history from Socrata")
            elif camis:
                result = await hydrate_query(
                    payload.restaurant.camis, closed_only=False, limit=5000
                )
                hydrated = result.get("persisted", 0) > 0 or result.get("fetched", 0) > 0
                if hydrated:
                    notes.append("hydrated from Socrata on a local miss")
        except Exception as exc:  # noqa: BLE001 - Socrata failure must not 5xx
            logger.warning("hydration failed for camis=%s: %s", camis, exc)
            notes.append("Socrata hydration failed; used local data only")
        # Re-resolve after hydration.
        with SessionLocal() as session:
            est = _resolve_establishment(session, payload)
            matched = est is not None

    # (c)/(d)/(e) load violations + compliance, rebuild summary, map details.
    db_violations = 0
    db_compliance = 0
    if est is not None:
        with SessionLocal() as session:
            est = session.get(ScoutEatsEstablishment, est.id)
            vios = list(
                session.scalars(
                    select(ScoutEatsViolation)
                    .where(ScoutEatsViolation.establishment_id == est.id)
                    .order_by(ScoutEatsViolation.issue_date.desc())
                )
            )
            comps = list(
                session.scalars(
                    select(ScoutEatsComplianceEvent)
                    .where(ScoutEatsComplianceEvent.establishment_id == est.id)
                    .order_by(ScoutEatsComplianceEvent.event_date.desc())
                )
            )
            db_violations = len(vios)
            db_compliance = len(comps)

            identity = _build_identity(est, payload.restaurant)
            if vios:  # DB has data -> authoritative, overrides submitted.
                summary = _build_summary(est, vios)
                violations = [_map_violation(v) for v in vios]
            else:  # establishment shell only -> keep submitted card body.
                summary = payload.summary
                violations = payload.violations
            compliance = [
                m for m in (_map_compliance(c) for c in comps) if m is not None
            ]
            if not compliance:
                compliance = payload.compliance_events
    else:
        # No match at all: keep submitted card as-is.
        identity = payload.restaurant
        summary = payload.summary
        violations = payload.violations
        compliance = payload.compliance_events

    # (h) sources + stamps.
    sources: set[str] = {
        s for s in payload.sources if s in ("socrata_live", "dohmh_csv", "manhattan_closed")
    }
    if hydrated or matched:
        sources.add("socrata_live")

    enriched_card = AnalysisCardPayload(
        schema_version=payload.schema_version or "1.0",
        generated_at=datetime.now(timezone.utc),
        data_source=payload.data_source,
        dataset_id=settings.dataset_dohmh,
        sources=sorted(sources),
        restaurant=identity,
        summary=summary,
        violations=violations,
        compliance_events=compliance,
    )

    # (f)/(g) codify AI risk + steps; degrade to local fallback on failure.
    risk_assessment, takeover, degraded = await _assess_and_plan(
        enriched_card, settings
    )
    if degraded:
        notes.append("codify unavailable; used local fallback")

    return EnrichResponse(
        card=enriched_card,
        risk_assessment=risk_assessment,
        takeover=takeover,
        enrichment=EnrichmentMeta(
            matched=matched,
            hydrated=hydrated,
            db_violations=db_violations,
            db_compliance_events=db_compliance,
            degraded=degraded,
            notes=notes,
        ),
    )


def _local_risk_assessment(
    card: AnalysisCardPayload, reason: str
) -> RiskAssessment:
    return RiskAssessment(
        source="local_fallback",
        available=False,
        risk=card.summary.risk,
        score=float(card.summary.latest_score)
        if card.summary.latest_score is not None
        else None,
        rationale=(
            f"{card.summary.critical_violations} critical violation(s) across "
            f"{card.summary.total_violations} total -> {card.summary.risk} risk "
            "(computed locally from DOHMH data)."
        ),
        degraded_reason=reason,
        raw=None,
    )


async def _assess_and_plan(
    card: AnalysisCardPayload, settings
) -> tuple[RiskAssessment, TakeoverPlan, bool]:
    """Return (risk_assessment, takeover_plan, degraded)."""
    card_json = card.model_dump(mode="json")
    try:
        async with CodifyClient(settings) as client:
            result = await client.assess(
                card_json, idempotency_key=_idempotency_key(card)
            )
        risk_assessment = RiskAssessment(
            source="codify.cafe",
            available=True,
            risk=result.get("risk") or card.summary.risk,
            score=result.get("score"),
            rationale=result.get("rationale"),
            degraded_reason=None,
            raw=result.get("raw"),
        )
        takeover = merge_codify_plan(result, card)
        return risk_assessment, takeover, False
    except CodifyUnavailable as exc:
        logger.info("codify unavailable, using local fallback: %s", exc)
        risk_assessment = _local_risk_assessment(card, str(exc))
        takeover = build_fallback_plan(card)
        return risk_assessment, takeover, True
    except Exception as exc:  # noqa: BLE001 - never 5xx on codify failure
        logger.warning("codify call errored, using local fallback: %s", exc)
        risk_assessment = _local_risk_assessment(card, f"unexpected error: {exc}")
        takeover = build_fallback_plan(card)
        return risk_assessment, takeover, True
