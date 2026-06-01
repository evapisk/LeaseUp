"""Abstract source adapter. Each adapter maps one Socrata dataset to our
establishment + violation/compliance models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

TargetModel = Literal["violation", "compliance_event", "building_only"]


@dataclass(slots=True)
class NormalizedRecord:
    """What an adapter emits per raw row."""

    source_record_id: str
    building: dict[str, Any] = field(default_factory=dict)
    violation: dict[str, Any] | None = None
    compliance_event: dict[str, Any] | None = None


class BaseSourceAdapter(ABC):
    source_key: str
    source_name: str
    dataset_id: str
    target_model: TargetModel

    # Optional explicit column projection ($select) to avoid 400s on schema drift.
    select: str | None = None

    @abstractmethod
    def get_source_record_id(self, payload: dict) -> str:
        """Stable unique id for a raw row."""

    @abstractmethod
    def build_building_payload(self, payload: dict) -> dict:
        """Establishment fields, including identifiers=[(type, value), ...]."""

    @abstractmethod
    def build_normalized_payload(self, payload: dict) -> NormalizedRecord:
        """Full normalized record (building + violation/compliance)."""

    @abstractmethod
    def build_search_filters(self, normalized_query: str) -> list[str]:
        """SoQL WHERE clauses for a free-text/identifier query."""
