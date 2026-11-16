"""Polite, cached HTTP fetching. ALL network access in this project goes through here.

Spec: docs/TASKS.md, Task 1. Rules: AGENTS.md "Hard rules" 2 and 3.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1, sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

import httpx
from protego import Protego

from ivydata.config import load_config

logger = logging.getLogger(__name__)


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
        min_delay_seconds: float | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        refresh: bool = False,
        client: httpx.Client | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if min_delay_seconds is None:
            min_delay_seconds = load_config().crawl.min_delay_seconds
        if not math.isfinite(min_delay_seconds) or min_delay_seconds < 3:
            raise ValueError("min_delay_seconds must be finite and >= 3")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent
        self.min_delay_seconds = min_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.refresh = refresh
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client()
        self._clock = clock if clock is not None else time.monotonic
        self._sleep = sleep if sleep is not None else time.sleep
        self._robots: dict[str, Protego] = {}
        self._delays: dict[str, float] = {}
        self._last_request: dict[str, float] = {}
        # Also serialize callers using the same instance from different threads.
        self._lock = RLock()

    def get(self, url: str) -> FetchResult:
        """Return the cached response, or fetch politely and cache it.

        Raises RobotsDisallowed if robots.txt forbids the URL. A 404 is returned as a
        FetchResult with status 404, not raised. 429/5xx are retried with backoff.
        """
        with self._lock:
            return self._fetch(url, obey_robots=httpx.URL(url).path != "/robots.txt")

    def _paths(self, url: str) -> tuple[Path, Path]:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise ValueError(f"expected an HTTP(S) URL: {url}")
        directory = self.cache_dir / parsed.host
        stem = sha1(url.encode("utf-8")).hexdigest()
        return directory / f"{stem}.html", directory / f"{stem}.json"

    def _cached(self, url: str) -> tuple[FetchResult, str | None] | None:
        body, sidecar = self._paths(url)
        if sidecar.with_suffix(".json.pending").exists():
            logger.warning("Recovering interrupted cache save for %s", url)
            self._publish_pending(url)
        if self.refresh or not (body.exists() or sidecar.exists()):
            return None
        if not (body.exists() and sidecar.exists()):
            logger.warning("Incomplete cache entry for %s; retrying unfinished download", url)
            return None
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Incomplete cache metadata for %s; retrying unfinished download", url)
            return None
        if metadata["url"] != url or sha256(body.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"invalid cache for {url}; use --refresh to replace it")
        return (
            FetchResult(
                url, metadata["status"], body, metadata["sha256"], True, metadata["fetched_at"]
            ),
            metadata.get("location"),
        )

    def _write_atomic(self, path: Path, content: bytes) -> None:
        with NamedTemporaryFile(
            dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(content)
                stream.flush()
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _publish_pending(self, url: str) -> None:
        body, sidecar = self._paths(url)
        pending_body = body.with_suffix(".html.pending")
        pending_metadata = sidecar.with_suffix(".json.pending")
        metadata = json.loads(pending_metadata.read_text(encoding="utf-8"))
        # The body may already have moved when a previous publication was interrupted.
        source = pending_body if pending_body.exists() else body
        if metadata["url"] != url or sha256(source.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"invalid pending cache for {url}; refusing to publish it")
        if pending_body.exists():
            pending_body.replace(body)
        pending_metadata.replace(sidecar)

    def _store(
        self, url: str, status: int, content: bytes, location: str | None = None
    ) -> FetchResult:
        body, sidecar = self._paths(url)
        body.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256(content).hexdigest()
        fetched_at = datetime.now(UTC).isoformat()
        metadata = {"url": url, "status": status, "fetched_at": fetched_at, "sha256": digest}
        if location is not None:
            metadata["location"] = location
        self._write_atomic(body.with_suffix(".html.pending"), content)
        # Publishing this complete sidecar marks the pair ready for recovery after restart.
        self._write_atomic(
            sidecar.with_suffix(".json.pending"),
            (json.dumps(metadata, indent=2) + "\n").encode("utf-8"),
        )
        self._publish_pending(url)
        return FetchResult(url, status, body, digest, False, fetched_at)

    def _authorize(self, url: str) -> None:
        parsed = httpx.URL(url)
        origin = str(parsed.copy_with(path="/robots.txt", query=None, fragment=None))
        host = parsed.host
        if origin not in self._robots:
            result = self._fetch(origin, obey_robots=False)
            if 200 <= result.status < 300:
                rules = result.text()
            elif result.status in {404, 410}:
                rules = ""
            else:
                # A failed robots lookup is never permission to crawl.
                raise RobotsDisallowed(
                    f"cannot establish robots permission: {origin} (HTTP {result.status})"
                )
            parser = Protego.parse(rules)
            self._robots[origin] = parser
            delay = parser.crawl_delay(self.user_agent) or 0
            self._delays[host] = max(self._delays.get(host, self.min_delay_seconds), delay)
        if not self._robots[origin].can_fetch(url, self.user_agent):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

    def _fetch(self, url: str, *, obey_robots: bool, redirects: int = 0) -> FetchResult:
        if redirects > 20:
            raise httpx.TooManyRedirects(f"too many redirects for {url}")
        cached = self._cached(url)
        if cached is not None:
            result, location = cached
        else:
            if obey_robots:
                self._authorize(url)
            host = httpx.URL(url).host
            for attempt in range(self.max_retries + 1):
                delay = self._delays.get(host, self.min_delay_seconds)
                if host in self._last_request:
                    wait = delay - (self._clock() - self._last_request[host])
                    if wait > 0:
                        self._sleep(wait)
                self._last_request[host] = self._clock()
                response = self._client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                )
                location = response.headers.get("location")
                result = self._store(url, response.status_code, response.content, location)
                if response.status_code != 429 and not 500 <= response.status_code < 600:
                    break
                if attempt < self.max_retries:
                    self._sleep(2**attempt)
        if result.status in {301, 302, 303, 307, 308} and location:
            target = str(httpx.URL(url).join(location))
            final = self._fetch(target, obey_robots=obey_robots, redirects=redirects + 1)
            assert final.path is not None
            return self._store(url, final.status, final.path.read_bytes())
        return result

    def close(self) -> None:
        """Close an internally created client; injected clients belong to the caller."""
        if self._owns_client:
            self._client.close()
