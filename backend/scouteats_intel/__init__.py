"""ScoutEats Intel — NYC restaurant inspection scraper/enrichment backend.

Pulls from NYC Open Data's Socrata API (DOHMH Restaurant Inspection Results,
dataset 43nn-pn8j), normalizes records, deduplicates them into restaurant
"establishment" entities, and persists violations + closure (compliance) events.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
