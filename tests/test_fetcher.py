import json
from datetime import datetime
from hashlib import sha1, sha256
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ivydata.crawl.fetcher import Fetcher, RobotsDisallowed

UA = "ivy-football-data/0.1 (+https://github.com/JaimeCastrellon/Web-Crawler)"
BASE = "https://school.example"


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


@pytest.fixture
def setup_fetcher(tmp_path):
    clients = []

    def make(handler=None, robots="User-agent: *\nAllow: /", **kwargs):
        clock = FakeClock()
        calls = []

        def transport(request):
            calls.append((str(request.url), clock.now, request.headers["user-agent"]))
            if request.url.path == "/robots.txt":
                if isinstance(robots, int):
                    return httpx.Response(robots)
                return httpx.Response(200, text=robots)
            return handler(request) if handler else httpx.Response(200, content=b"<html>ok</html>")

        client = httpx.Client(transport=httpx.MockTransport(transport), follow_redirects=True)
        clients.append(client)
        fetcher = Fetcher(
            tmp_path, UA, client=client, clock=clock.clock, sleep=clock.sleep, **kwargs
        )
        return SimpleNamespace(fetcher=fetcher, calls=calls, clock=clock, client=client)

    yield make
    for client in clients:
        client.close()


def test_cache_integrity_metadata_and_restart(setup_fetcher, tmp_path):
    s = setup_fetcher()
    result = s.fetcher.get(BASE + "/page")
    assert result.status == 200 and not result.from_cache
    assert result.text() == "<html>ok</html>"
    filename = f"{sha1(result.url.encode()).hexdigest()}.html"
    assert result.path == tmp_path / "school.example" / filename
    metadata = json.loads(result.path.with_suffix(".json").read_text())
    assert metadata == {
        "url": result.url,
        "status": 200,
        "fetched_at": result.fetched_at,
        "sha256": sha256(result.path.read_bytes()).hexdigest(),
    }
    assert datetime.fromisoformat(result.fetched_at).utcoffset().total_seconds() == 0
    assert s.fetcher.get(result.url).from_cache
    assert len(s.calls) == 2  # robots and page only
    restarted = setup_fetcher()
    assert restarted.fetcher.get(result.url).from_cache
    assert restarted.calls == []
    restarted.fetcher.get(BASE + "/second")
    assert [c[0] for c in restarted.calls] == [BASE + "/second"]  # robots also cached


def test_spacing_includes_robots_and_uses_configured_agent(setup_fetcher):
    s = setup_fetcher()
    s.fetcher.get(BASE + "/one")
    s.fetcher.get(BASE + "/two")
    s.fetcher.get("https://other.example/page")
    assert [t for url, t, _ in s.calls if url.startswith(BASE)] == [0, 3, 6]
    assert all(agent == UA for _, _, agent in s.calls)


def test_larger_crawl_delay_and_specific_agent(setup_fetcher):
    s = setup_fetcher(
        robots="User-agent: *\nCrawl-delay: 4\n\n"
        "User-agent: ivy-football-data\nCrawl-delay: 7.5\nAllow: /"
    )
    s.fetcher.get(BASE + "/one")
    s.fetcher.get(BASE + "/two")
    assert [t for _, t, _ in s.calls] == [0, 7.5, 15]


def test_robots_wildcards_and_allow_precedence(setup_fetcher):
    s = setup_fetcher(robots="User-agent: *\nDisallow: /private/*\nAllow: /private/public$")
    with pytest.raises(RobotsDisallowed, match="disallows"):
        s.fetcher.get(BASE + "/private/secret")
    assert len(s.calls) == 1
    assert s.fetcher.get(BASE + "/private/public").status == 200


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_then_success(setup_fetcher, status):
    responses = iter([status, 200])
    s = setup_fetcher(handler=lambda r: httpx.Response(next(responses)))
    assert s.fetcher.get(BASE + "/page").status == 200
    assert [t for _, t, _ in s.calls] == [0, 3, 6]


def test_retry_exhaustion_backoff_and_cached_error(setup_fetcher):
    s = setup_fetcher(handler=lambda r: httpx.Response(503))
    result = s.fetcher.get(BASE + "/page")
    assert result.status == 503
    assert [t for _, t, _ in s.calls] == [0, 3, 6, 9, 13]
    assert s.fetcher.get(result.url).from_cache
    assert len(s.calls) == 5


def test_404_is_returned_and_cached(setup_fetcher):
    s = setup_fetcher(handler=lambda r: httpx.Response(404, text="missing"))
    result = s.fetcher.get(BASE + "/missing")
    assert result.status == 404 and result.text() == "missing"
    assert s.fetcher.get(result.url).from_cache


def test_refresh_replaces_page_and_robots(setup_fetcher):
    original = setup_fetcher()
    original.fetcher.get(BASE + "/page")
    refreshed = setup_fetcher(refresh=True, handler=lambda r: httpx.Response(200, text="new"))
    result = refreshed.fetcher.get(BASE + "/page")
    assert not result.from_cache and result.text() == "new"
    assert len(refreshed.calls) == 2


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_unavailable_robots_fails_closed(setup_fetcher, status):
    s = setup_fetcher(robots=status)
    with pytest.raises(RobotsDisallowed, match="cannot establish"):
        s.fetcher.get(BASE + "/page")
    assert all(url.endswith("/robots.txt") for url, _, _ in s.calls)


@pytest.mark.parametrize("status", [404, 410])
def test_missing_robots_allows_pages(setup_fetcher, status):
    s = setup_fetcher(robots=status)
    assert s.fetcher.get(BASE + "/page").status == 200


def test_redirect_target_checks_robots_before_request(setup_fetcher):
    s = setup_fetcher(
        handler=lambda r: httpx.Response(
            302, headers={"location": "https://other.example/private"}
        ),
        robots="User-agent: *\nDisallow: /private",
    )
    with pytest.raises(RobotsDisallowed):
        s.fetcher.get(BASE + "/page")
    assert [url for url, _, _ in s.calls] == [
        BASE + "/robots.txt",
        BASE + "/page",
        "https://other.example/robots.txt",
    ]


def test_redirect_spacing_and_cached_final_body(setup_fetcher):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/end"})
        return httpx.Response(200, text="final")

    s = setup_fetcher(handler=handler)
    result = s.fetcher.get(BASE + "/start")
    assert result.url == BASE + "/start" and result.status == 200 and result.text() == "final"
    assert [t for _, t, _ in s.calls] == [0, 3, 6]
    assert s.fetcher.get(result.url).from_cache
    assert len(s.calls) == 3


def test_config_default_and_delay_floor(setup_fetcher, monkeypatch):
    monkeypatch.setattr(
        "ivydata.crawl.fetcher.load_config",
        lambda: SimpleNamespace(crawl=SimpleNamespace(min_delay_seconds=9)),
    )
    s = setup_fetcher()
    s.fetcher.get(BASE + "/page")
    assert s.calls[-1][1] == 9
    for invalid in (2, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="min_delay_seconds"):
            setup_fetcher(min_delay_seconds=invalid)


def test_corrupt_cache_fails_without_network(setup_fetcher):
    s = setup_fetcher()
    result = s.fetcher.get(BASE + "/page")
    result.path.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="invalid cache"):
        s.fetcher.get(result.url)
    assert len(s.calls) == 2


def test_close_ownership(setup_fetcher, tmp_path):
    s = setup_fetcher()
    s.fetcher.close()
    assert not s.client.is_closed
    fetcher = Fetcher(tmp_path, UA)
    fetcher.close()
    assert fetcher._client.is_closed


def test_direct_robots_fetch_is_not_requested_twice(setup_fetcher):
    s = setup_fetcher()
    assert s.fetcher.get(BASE + "/robots.txt").status == 200
    assert len(s.calls) == 1


def test_redirect_loop_is_bounded(setup_fetcher):
    s = setup_fetcher(handler=lambda r: httpx.Response(302, headers={"location": "/loop"}))
    with pytest.raises(httpx.TooManyRedirects):
        s.fetcher.get(BASE + "/loop")
    assert len(s.calls) == 2


@pytest.mark.parametrize("phase", [".html.pending", ".json.pending", ".html", ".json"])
@pytest.mark.parametrize("refreshing", [False, True])
def test_interrupted_save_recovers_after_restart(setup_fetcher, monkeypatch, phase, refreshing):
    original = setup_fetcher(handler=lambda r: httpx.Response(200, text="old"))
    url = BASE + "/page"
    original.fetcher.get(BASE + "/robots.txt")
    if refreshing:
        original.fetcher.get(url)
    interrupted = setup_fetcher(
        refresh=refreshing, handler=lambda r: httpx.Response(200, text="new")
    )
    stem = sha1(url.encode()).hexdigest()
    replace = Path.replace

    def interrupt(self, target):
        if Path(target).name == stem + phase:
            raise InterruptedError("simulated interrupted publication")
        return replace(self, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", interrupt)
        with pytest.raises(InterruptedError):
            interrupted.fetcher.get(url)
    restarted = setup_fetcher(handler=lambda r: httpx.Response(200, text="retried"))
    result = restarted.fetcher.get(url)
    ready = phase in {".html", ".json"}
    assert result.text() == ("new" if ready else "old" if refreshing else "retried")
    assert result.from_cache == (ready or refreshing)
    assert [call[0] for call in restarted.calls] == ([] if ready or refreshing else [url])
    assert restarted.fetcher.get(url).from_cache


@pytest.mark.parametrize("incomplete", ["body", "metadata", "truncated_metadata"])
def test_old_incomplete_cache_retries_only_unfinished_url(setup_fetcher, caplog, incomplete):
    original = setup_fetcher()
    result = original.fetcher.get(BASE + "/page")
    body = result.path
    metadata = body.with_suffix(".json")
    if incomplete == "body":
        metadata.unlink()
    elif incomplete == "metadata":
        body.unlink()
    else:
        metadata.write_text('{"url":')
    restarted = setup_fetcher()
    assert restarted.fetcher.get(result.url).status == 200
    assert [call[0] for call in restarted.calls] == [result.url]
    assert result.url in caplog.text and "unfinished download" in caplog.text
