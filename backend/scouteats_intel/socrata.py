"""Async Socrata client (httpx) with retry/backoff and parallel batch fetch."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings, get_settings

logger = logging.getLogger("scouteats.socrata")


@dataclass(slots=True)
class FetchSpec:
    """One Socrata query, for use with SocrataClient.fetch_many()."""

    dataset_id: str
    where: str | None = None
    limit: int | None = None
    select: str | None = None
    order: str | None = None
    tag: Any = None


class SocrataClient:
    """Wraps a single shared httpx.AsyncClient.

    Use as an async context manager so the underlying connection pool is shared
    across all queries (important for fetch_many parallelism):

        async with SocrataClient() as client:
            rows = await client.fetch_where("43nn-pn8j", "camis='40365938'", 50)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        headers = {"Accept": "application/json"}
        if self.settings.socrata_app_token:
            headers["X-App-Token"] = self.settings.socrata_app_token
        self._client = httpx.AsyncClient(
            base_url=self.settings.socrata_base_url,
            headers=headers,
            timeout=self.settings.request_timeout_seconds,
        )

    async def __aenter__(self) -> "SocrataClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- core request with retry/backoff --------------------------------------

    async def _get(self, dataset_id: str, params: dict[str, Any]) -> list[dict]:
        url = f"{dataset_id}.json"
        clean = {k: v for k, v in params.items() if v is not None}
        last_exc: Exception | None = None
        for attempt in range(1, self.settings.request_retries + 1):
            try:
                resp = await self._client.get(url, params=clean)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - retry on any transport/HTTP error
                last_exc = exc
                logger.warning(
                    "Socrata %s attempt %d/%d failed: %s",
                    dataset_id,
                    attempt,
                    self.settings.request_retries,
                    exc,
                )
                if attempt < self.settings.request_retries:
                    await asyncio.sleep(attempt)  # linear backoff: 1s, 2s, 3s
        assert last_exc is not None
        raise last_exc

    # -- single page ----------------------------------------------------------

    async def fetch_where(
        self,
        dataset_id: str,
        where: str | None,
        limit: int,
        select: str | None = None,
        order: str | None = None,
    ) -> list[dict]:
        """Fetch a single page of rows matching a SoQL WHERE clause."""
        params = {
            "$where": where,
            "$select": select,
            "$order": order,
            "$limit": limit,
        }
        return await self._get(dataset_id, params)

    # -- paginated bulk -------------------------------------------------------

    async def fetch_all(
        self,
        dataset_id: str,
        limit: int | None = None,
        where: str | None = None,
        select: str | None = None,
        order: str | None = None,
    ) -> list[dict]:
        """Page through a dataset until exhausted (or `limit` rows collected)."""
        page_size = self.settings.batch_size
        offset = 0
        out: list[dict] = []
        order = order or ":id"  # stable ordering for reliable pagination
        while True:
            want = page_size
            if limit is not None:
                want = min(page_size, limit - len(out))
                if want <= 0:
                    break
            page = await self._get(
                dataset_id,
                {
                    "$where": where,
                    "$select": select,
                    "$order": order,
                    "$limit": want,
                    "$offset": offset,
                },
            )
            out.extend(page)
            offset += len(page)
            if len(page) < want:
                break
        return out

    # -- parallel batch -------------------------------------------------------

    async def fetch_many(
        self, specs: list[FetchSpec]
    ) -> list[tuple[Any, list[dict] | Exception]]:
        """Run many queries in parallel over the shared client.

        Returns [(spec.tag, records_or_exception)] in the same order as `specs`.
        """
        async def run(spec: FetchSpec) -> list[dict]:
            return await self._get(
                spec.dataset_id,
                {
                    "$where": spec.where,
                    "$select": spec.select,
                    "$order": spec.order,
                    "$limit": spec.limit if spec.limit is not None else 1000,
                },
            )

        results = await asyncio.gather(
            *(run(s) for s in specs), return_exceptions=True
        )
        return [(spec.tag, res) for spec, res in zip(specs, results)]
