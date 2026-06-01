"""Pydantic v2 schemas for the analysis-card enrichment service.

The card models mirror the JSON Schema ``$id``
``https://scouteats/analysis-card.schema.json`` EXACTLY (additionalProperties:
false everywhere). On *input* unknown keys are dropped (``extra="ignore"``) so the
service is lenient; on *output* only the schema fields are serialized, so the card
stays strictly conformant. All AI / steps / meta live in the sibling envelope
fields (``EnrichResponse``), never inside ``card``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import normalize as N

SCHEMA_ID = "https://scouteats/analysis-card.schema.json"

# Enums (kept as Literal so they serialize as plain strings).
RiskLevel = Literal["low", "medium", "high"]
ViolationCategory = Literal[
    "pests",
    "temperature",
    "hygiene",
    "food-protection",
    "equipment",
    "administrative",
]
Severity = Literal["critical", "not_critical"]
ComplianceEventType = Literal["closed", "re-closed", "re-opened"]
BoroughName = Literal["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]

_CARD_CONFIG = ConfigDict(extra="ignore")


# -- card $defs ---------------------------------------------------------------


class RestaurantIdentity(BaseModel):
    model_config = _CARD_CONFIG

    camis: str | None = None
    name: str | None = None
    address: str | None = None
    borough: BoroughName | None = None
    zip: str | None = None
    cuisine: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("borough", mode="before")
    @classmethod
    def _canonicalize_borough(cls, value: object) -> str | None:
        """Lenient on input: accept any borough name/code/alias, canonicalize."""
        if value is None or value == "":
            return None
        return N.canonical_borough(value)


class CategoryBreakdown(BaseModel):
    model_config = _CARD_CONFIG

    category: ViolationCategory
    count: int = Field(ge=0)


class CardSummary(BaseModel):
    model_config = _CARD_CONFIG

    total_violations: int = Field(ge=0)
    critical_violations: int = Field(ge=0)
    risk: RiskLevel
    is_closed: bool
    categories: list[ViolationCategory] = Field(default_factory=list)
    category_breakdown: list[CategoryBreakdown] = Field(default_factory=list)
    latest_grade: str | None = None
    latest_score: int | None = None
    last_inspection_date: date | None = None
    last_closure_date: date | None = None


class ViolationDetail(BaseModel):
    model_config = _CARD_CONFIG

    code: str | None = None
    category: ViolationCategory
    severity: Severity | None = None
    status: str | None = None
    description: str | None = None
    inspection_type: str | None = None
    issue_date: date | None = None


class ComplianceEventDetail(BaseModel):
    model_config = _CARD_CONFIG

    event_type: ComplianceEventType
    event_date: date | None = None
    action_text: str | None = None


class AnalysisCardPayload(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"$id": SCHEMA_ID},
    )

    schema_version: str = "1.0"
    generated_at: datetime | None = None
    data_source: str = "NYC DOHMH Restaurant Inspection Results"
    dataset_id: str | None = "43nn-pn8j"
    sources: list[Literal["socrata_live", "dohmh_csv", "manhattan_closed"]] = Field(
        default_factory=list
    )
    restaurant: RestaurantIdentity
    summary: CardSummary
    violations: list[ViolationDetail] = Field(default_factory=list)
    compliance_events: list[ComplianceEventDetail] = Field(default_factory=list)


# -- envelope -----------------------------------------------------------------


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: Literal["codify.cafe", "local_fallback"]
    available: bool
    risk: RiskLevel | None = None
    score: float | None = None
    rationale: str | None = None
    degraded_reason: str | None = None
    raw: dict | None = None


class TakeoverStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order: int
    title: str
    detail: str
    category: (
        Literal[
            "remediation", "permit", "inspection", "legal", "financial", "general"
        ]
        | None
    ) = None
    related_violation_categories: list[str] = Field(default_factory=list)


class TakeoverPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    headline: str
    summary: str
    steps: list[TakeoverStep]
    codify_url: str
    source: Literal["codify.cafe", "local_fallback"]


class EnrichmentMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    matched: bool
    hydrated: bool
    db_violations: int
    db_compliance_events: int
    degraded: bool
    notes: list[str] = Field(default_factory=list)


class EnrichResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    card: AnalysisCardPayload
    risk_assessment: RiskAssessment
    takeover: TakeoverPlan
    enrichment: EnrichmentMeta
