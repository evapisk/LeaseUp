#!/usr/bin/env python3
"""CLI for the ScoutEats Intel backend.

Examples:
  python -m scripts.ingest_closed ingest --limit 500
  python -m scripts.ingest_closed search "NANCY'S RESTAURANT"
  python -m scripts.ingest_closed rehydrate 1
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow running from the backend/ directory without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scouteats_intel.db import init_db  # noqa: E402
from scouteats_intel.hydration import (  # noqa: E402
    force_rehydrate,
    hydrate_query,
    ingest_closed,
    seed_data_sources,
)


async def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="bulk-ingest closed-by-DOHMH inspections")
    p_ing.add_argument("--limit", type=int, default=None)

    p_q = sub.add_parser("search", help="hydrate + show results for a query")
    p_q.add_argument("query")
    p_q.add_argument("--all", action="store_true", help="not just closed")
    p_q.add_argument("--limit", type=int, default=100)

    p_r = sub.add_parser("rehydrate", help="parallel rehydrate one establishment")
    p_r.add_argument("establishment_id", type=int)

    args = ap.parse_args()

    init_db()
    seed_data_sources()

    if args.cmd == "ingest":
        result = await ingest_closed(limit=args.limit)
    elif args.cmd == "search":
        result = await hydrate_query(
            args.query, closed_only=not args.all, limit=args.limit
        )
    elif args.cmd == "rehydrate":
        result = await force_rehydrate(args.establishment_id)
    else:  # pragma: no cover
        ap.error("unknown command")

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
