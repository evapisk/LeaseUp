from .base import BaseSourceAdapter, NormalizedRecord
from .dohmh_inspections import DohmhInspectionsAdapter

# Ordered registry of adapters. (Add more Socrata datasets here.)
ADAPTERS: list[BaseSourceAdapter] = [DohmhInspectionsAdapter()]
ADAPTERS_BY_KEY = {a.source_key: a for a in ADAPTERS}

__all__ = [
    "BaseSourceAdapter",
    "NormalizedRecord",
    "DohmhInspectionsAdapter",
    "ADAPTERS",
    "ADAPTERS_BY_KEY",
]
