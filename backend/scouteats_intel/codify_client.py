"""Async Codify (codify.cafe = P2X Laravel api) client.

Mirrors ``socrata.py``: a single shared ``httpx.AsyncClient``, linear
retry/backoff, used as an async context manager. Used for synchronous AI
enrichment via ``POST /api/pipes/invoke``. Any failure (disabled, no token,
transport error, bad status, unexpected body) raises ``CodifyUnavailable`` so
callers degrade to a deterministic local fallback and never 5xx.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import Settings, get_settings

logger = logging.getLogger("scouteats.codify")


class CodifyUnavailable(Exception):
    """Raised when codify cannot be reached or is not configured."""


class CodifyClient:
    """Wraps a single shared httpx.AsyncClient for codify.cafe.

    Use as an async context manager so the connection pool is shared:

        async with CodifyClient() as client:
            result = await client.assess(card_json)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._subproject_id: int | None = self.settings.codify_subproject_id
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Domain": self.settings.codify_x_domain,
        }
        if self.settings.codify_token:
            headers["Authorization"] = f"Bearer {self.settings.codify_token}"
        self._client = httpx.AsyncClient(
            base_url=self.settings.codify_base_url,
            headers=headers,
            timeout=self.settings.codify_timeout_seconds,
        )

    async def __aenter__(self) -> "CodifyClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _ensure_enabled(self) -> None:
        if not self.settings.codify_enabled:
            raise CodifyUnavailable("codify disabled (SCOUTEATS_CODIFY_ENABLED=false)")
        if not self.settings.codify_token:
            raise CodifyUnavailable("codify token not configured")

    # -- core request with retry/backoff --------------------------------------

    async def _post(
        self, path: str, json: dict[str, Any], *, headers: dict[str, str] | None = None
    ) -> dict:
        last_exc: Exception | None = None
        retries = self.settings.request_retries
        for attempt in range(1, retries + 1):
            try:
                resp = await self._client.post(path, json=json, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - retry on any transport/HTTP error
                last_exc = exc
                logger.warning(
                    "Codify %s attempt %d/%d failed: %s", path, attempt, retries, exc
                )
                if attempt < retries:
                    await asyncio.sleep(attempt)  # linear backoff: 1s, 2s, 3s
        raise CodifyUnavailable(f"codify {path} failed: {last_exc}") from last_exc

    # -- subproject resolution ------------------------------------------------

    async def resolve_subproject(self) -> int:
        """Return the subproject id (settings override, else resolve + cache)."""
        self._ensure_enabled()
        if self._subproject_id is not None:
            return self._subproject_id
        body = await self._post(
            "/api/internal/resolve-subproject",
            {"domain": self.settings.codify_x_domain},
        )
        try:
            sub_id = int(body["data"]["subproject"]["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CodifyUnavailable(
                f"codify resolve-subproject returned unexpected body: {body!r}"
            ) from exc
        self._subproject_id = sub_id
        return sub_id

    # -- AI assessment --------------------------------------------------------

    async def assess(
        self, card_json: dict, *, idempotency_key: str | None = None
    ) -> dict:
        """Invoke the lease-takeover pipe and parse the result opaquely.

        Returns ``{"risk", "score", "rationale", "steps", "raw"}`` — any field may
        be absent/None; ``raw`` always carries the verbatim codify ``result``.
        """
        self._ensure_enabled()
        subproject_id = await self.resolve_subproject()
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        body = await self._post(
            "/api/pipes/invoke",
            {
                "pipe_name": self.settings.codify_pipe_name,
                "subproject_id": subproject_id,
                "domain": self.settings.codify_x_domain,
                "params": {
                    "task": "lease_takeover_plan",
                    "restaurant_data": card_json,
                },
            },
            headers=headers,
        )
        if not body.get("ok"):
            raise CodifyUnavailable(f"codify invoke not ok: {body!r}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise CodifyUnavailable(f"codify invoke missing result: {body!r}")

        risk = result.get("risk")
        if risk not in ("low", "medium", "high"):
            risk = None
        score = result.get("score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        steps = result.get("steps")
        if not isinstance(steps, list):
            steps = None
        return {
            "risk": risk,
            "score": score,
            "rationale": result.get("rationale"),
            "steps": steps,
            "raw": result,
        }
