"""Deterministic lease-takeover plan builder + codify plan merge.

``build_fallback_plan`` derives an ALWAYS non-empty, ordered set of steps purely
from the enriched card (closure history, top violation categories, permits,
re-inspection, lease assignment, financials). ``merge_codify_plan`` prefers
codify-provided steps when present, else falls back to this local plan.
"""
from __future__ import annotations

import logging

from .config import get_settings
from .schemas import (
    AnalysisCardPayload,
    TakeoverPlan,
    TakeoverStep,
)

logger = logging.getLogger("scouteats.takeover")

# Human remediation guidance per violation category.
_CATEGORY_GUIDANCE: dict[str, str] = {
    "pests": (
        "Engage a licensed pest-control operator, eliminate harborage and entry "
        "points, and keep a treatment log — pest violations are a leading cause of "
        "DOHMH closures."
    ),
    "temperature": (
        "Repair or replace refrigeration/hot-holding equipment and document "
        "time-temperature controls so cold foods stay <=41F and hot foods >=140F."
    ),
    "hygiene": (
        "Reset personal-hygiene and handwashing protocols: stocked hand sinks, "
        "glove/utensil use, and a staff retraining on bare-hand-contact rules."
    ),
    "food-protection": (
        "Correct food-protection failures — covered/labeled storage, cross-"
        "contamination separation, and approved sourcing — before reopening."
    ),
    "equipment": (
        "Bring facilities and equipment up to code: surfaces, plumbing, "
        "ventilation, and lighting, with repairs documented for re-inspection."
    ),
    "administrative": (
        "Resolve administrative findings (permits, postings, required records) and "
        "make sure the Food Protection Certificate is current and on site."
    ),
}

_CATEGORY_TITLE: dict[str, str] = {
    "pests": "Remediate pest-control violations",
    "temperature": "Fix temperature-control violations",
    "hygiene": "Address hygiene and handwashing violations",
    "food-protection": "Correct food-protection violations",
    "equipment": "Repair facility and equipment violations",
    "administrative": "Clear administrative violations",
}


def codify_url(camis: str | None) -> str:
    """Deep link to codify.cafe for the restaurant."""
    base = get_settings().codify_public_base_url.rstrip("/")
    return f"{base}/restaurants/{camis}" if camis else f"{base}/restaurants"


def _restaurant_label(card: AnalysisCardPayload) -> str:
    return (card.restaurant.name or "this restaurant").strip()


def _top_categories(card: AnalysisCardPayload) -> list[tuple[str, int]]:
    """Categories present, richest first (prefers card_breakdown, else categories)."""
    if card.summary.category_breakdown:
        pairs = [(cb.category, cb.count) for cb in card.summary.category_breakdown]
        pairs.sort(key=lambda p: (-p[1], p[0]))
        return pairs
    return [(c, 0) for c in card.summary.categories]


def build_fallback_plan(card: AnalysisCardPayload) -> TakeoverPlan:
    """Build a deterministic, ordered, non-empty takeover plan from the card."""
    label = _restaurant_label(card)
    summary = card.summary
    steps: list[TakeoverStep] = []

    # 1. Closure remediation context (only if closed).
    if summary.is_closed:
        when = (
            summary.last_closure_date.isoformat()
            if summary.last_closure_date
            else "an unspecified date"
        )
        action_text = None
        for ev in card.compliance_events:
            if ev.event_type in ("closed", "re-closed") and ev.action_text:
                action_text = ev.action_text
                break
        detail = (
            f"{label} was closed by DOHMH (last closure: {when}). Review the closure "
            "order and resolve every cited condition before applying to reopen."
        )
        if action_text:
            detail += f' DOHMH action: "{action_text}".'
        steps.append(
            TakeoverStep(
                order=len(steps) + 1,
                title="Review the DOHMH closure order",
                detail=detail,
                category="remediation",
                related_violation_categories=[],
            )
        )

    # 2. One remediation step per top violation category present.
    for category, _count in _top_categories(card):
        steps.append(
            TakeoverStep(
                order=len(steps) + 1,
                title=_CATEGORY_TITLE.get(category, f"Remediate {category} violations"),
                detail=_CATEGORY_GUIDANCE.get(
                    category, f"Remediate the cited {category} violations."
                ),
                category="remediation",
                related_violation_categories=[category],
            )
        )

    # 3. Permit / pre-operational inspection.
    steps.append(
        TakeoverStep(
            order=len(steps) + 1,
            title="Secure permits and a pre-operational inspection",
            detail=(
                "Transfer or obtain the DOHMH food-service establishment permit and "
                "request a pre-operational inspection so the space is cleared for "
                "operation under new ownership."
            ),
            category="permit",
            related_violation_categories=[],
        )
    )

    # 4. Re-inspection.
    steps.append(
        TakeoverStep(
            order=len(steps) + 1,
            title="Pass the DOHMH re-inspection",
            detail=(
                "Schedule the DOHMH re-inspection once remediation is complete; a "
                "passing re-inspection is required to lift the closure and earn a "
                "letter grade."
            ),
            category="inspection",
            related_violation_categories=[],
        )
    )

    # 5. Lease assignment / legal.
    steps.append(
        TakeoverStep(
            order=len(steps) + 1,
            title="Assign the lease and clear legal liabilities",
            detail=(
                f"Negotiate assignment or a new lease for the {label} space, run a "
                "lien/UCC search, and confirm no outstanding DOHMH fines or "
                "judgments transfer with the premises."
            ),
            category="legal",
            related_violation_categories=[],
        )
    )

    # 6. Financial.
    score_txt = (
        f"last DOHMH score of {summary.latest_score}"
        if summary.latest_score is not None
        else "the violation history"
    )
    steps.append(
        TakeoverStep(
            order=len(steps) + 1,
            title="Build the takeover budget",
            detail=(
                f"Model remediation and reopening costs against {score_txt} and "
                f"{summary.critical_violations} critical violation(s): equipment "
                "repair, pest control, permit fees, and working capital through "
                "re-inspection."
            ),
            category="financial",
            related_violation_categories=[],
        )
    )

    closed_phrase = "closed by DOHMH" if summary.is_closed else "flagged"
    plan_summary = (
        f"{label} is currently {closed_phrase} with {summary.total_violations} "
        f"violation(s) ({summary.critical_violations} critical, risk: "
        f"{summary.risk}). The steps below cover remediation, permitting, "
        "re-inspection, lease assignment, and budgeting to take the space over."
    )
    return TakeoverPlan(
        headline=f"Steps to take over {label}",
        summary=plan_summary,
        steps=steps,
        codify_url=codify_url(card.restaurant.camis),
        source="local_fallback",
    )


_STEP_CATEGORIES = {
    "remediation",
    "permit",
    "inspection",
    "legal",
    "financial",
    "general",
}


def _coerce_codify_steps(raw_steps: list) -> list[TakeoverStep]:
    """Best-effort coercion of opaque codify steps into TakeoverStep models."""
    steps: list[TakeoverStep] = []
    for i, raw in enumerate(raw_steps):
        if isinstance(raw, str):
            steps.append(
                TakeoverStep(order=i + 1, title=raw[:120] or f"Step {i + 1}", detail=raw)
            )
            continue
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("name") or f"Step {i + 1}")
        detail = str(raw.get("detail") or raw.get("description") or title)
        category = raw.get("category")
        if category not in _STEP_CATEGORIES:
            category = None
        related = raw.get("related_violation_categories")
        if not isinstance(related, list):
            related = []
        order = raw.get("order")
        try:
            order = int(order)
        except (TypeError, ValueError):
            order = i + 1
        steps.append(
            TakeoverStep(
                order=order,
                title=title,
                detail=detail,
                category=category,
                related_violation_categories=[str(r) for r in related],
            )
        )
    return steps


def merge_codify_plan(result: dict | None, card: AnalysisCardPayload) -> TakeoverPlan:
    """Prefer codify-provided steps when present; else the local fallback plan."""
    fallback = build_fallback_plan(card)
    if not result:
        return fallback
    raw_steps = result.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return fallback
    steps = _coerce_codify_steps(raw_steps)
    if not steps:
        return fallback
    label = _restaurant_label(card)
    summary = result.get("summary") or result.get("rationale") or fallback.summary
    return TakeoverPlan(
        headline=result.get("headline") or f"Steps to take over {label}",
        summary=str(summary),
        steps=steps,
        codify_url=codify_url(card.restaurant.camis),
        source="codify.cafe",
    )
