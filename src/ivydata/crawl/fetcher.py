"""Polite, cached HTTP fetching. ALL network access in this project goes through here.

Spec: docs/TASKS.md, Task 1. Rules: AGENTS.md "Hard rules" 2 and 3.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx


class RobotsDisallowed(Exception):
    """The URL is disallowed by the host's robots.txt for our User-Agent."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    path: Path | None  # cached body on disk (None if no body was stored)
    sha256: str | None
    from_cache: bool
    fetched_at: str  # ISO-8601 UTC

    def text(self) -> str:
        if self.path is None:
            raise ValueError(f"no body cached for {self.url}")
        return self.path.read_text(encoding="utf-8", errors="replace")


class Fetcher:
    """Fetch URLs one at a time per host, >= min_delay_seconds apart, honoring robots.txt,
    caching every response under ``cache_dir/<host>/<sha1(url)>.html`` (+ ``.json`` sidecar).

    ``client``, ``clock`` and ``sleep`` are injectable so tests run with
    ``httpx.MockTransport`` and a fake clock — no real network, no real waiting.
    """

    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        min_delay_seconds: float = 3.0,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        refresh: bool = False,
        client: httpx.Client | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        raise NotImplementedError("Task 1")

    def get(self, url: str) -> FetchResult:
        """Return the cached response, or fetch politely and cache it.

        Raises RobotsDisallowed if robots.txt forbids the URL. A 404 is returned as a
        FetchResult with status 404, not raised. 429/5xx are retried with backoff.
        """
        raise NotImplementedError("Task 1")

    def close(self) -> None:
        raise NotImplementedError("Task 1")
