import csv
import json
from hashlib import sha1
from pathlib import Path

import httpx
import pytest

from ivydata import cli
from ivydata.config import load_config
from ivydata.crawl import discover
from ivydata.crawl.fetcher import Fetcher, FetchResult, RobotsDisallowed
from ivydata.crawl.pages import challenge_provider, has_schedule_games

FIXTURES = Path(__file__).parent / "fixtures"
SCHEDULE = '<li class="sidearm-schedule-game">Sep 18 vs Yale</li>'
BOX = "https://yalebulldogs.com/sports/football/stats/2004/penn/boxscore/10166"


def test_schedule_candidates_follow_config_and_school_order():
    config = load_config()
    assert discover.schedule_url_candidates(config, config.school("cornell"), 2004) == [
        "https://cornellbigred.com/sports/football/schedule/2004-05",
        "https://cornellbigred.com/sports/football/schedule/2004",
    ]
    assert discover.schedule_url_candidates(config, config.school("yale"), 1999)[1].endswith(
        "/1999-00"
    )


@pytest.mark.parametrize(
    "name,school,count,first,last",
    [
        ("schedule_yale_2025", "yale", 12, "19308", "19875"),
        ("schedule_yale_2004", "yale", 9, "10161", "10170"),
        ("schedule_brown_2025_excerpt", "brown", 2, None, None),
    ],
)
def test_extract_real_schedule_fixtures(name, school, count, first, last):
    config = load_config()
    html = (FIXTURES / f"{name}.html").read_text()
    url = config.school(school).base_url + "/sports/football/schedule/2025"
    links = discover.find_boxscore_links(html, url, config.boxscore_regex)
    assert has_schedule_games(html)
    assert len(links) == count and len(set(links)) == count
    assert all(
        link.startswith(config.school(school).base_url + "/sports/football/stats/")
        for link in links
    )
    if first:
        assert links[0].endswith("/" + first) and links[-1].endswith("/" + last)


def test_links_relative_absolute_fragments_and_non_football():
    config = load_config()
    html = f'''<a href="{BOX}#stats">a</a><a href="{BOX}">duplicate</a>
      <a href="//other.example/sports/football/stats/2025/yale/boxscore/2">other</a>
      <a href="/sports/basketball/stats/2025/yale/boxscore/3">wrong sport</a>
      <a href="javascript:alert(1)">bad scheme</a><a>no href</a>
      <a href="/sports/football/stats/2025/yale/boxscore/not-a-number">bad id</a>'''
    links = discover.find_boxscore_links(html, "https://yalebulldogs.com", config.boxscore_regex)
    assert links == [BOX, "https://other.example/sports/football/stats/2025/yale/boxscore/2"]


def test_page_checks_allow_monitoring_on_populated_sports_pages():
    script = '<script src="/_Incapsula_Resource?monitor"></script>'
    assert challenge_provider(script) == "Incapsula"
    for content in [
        SCHEDULE,
        '<div class="s-game-card">Brown vs Penn</div>',
        '<article class="box-score"><table><tr><td>Yale 31</td></tr></table></article>',
        '<article class="sidearm-story-template">Football recap</article>',
    ]:
        assert challenge_provider(script + content) is None
    assert not has_schedule_games('<li class="sidearm-schedule-game"></li>')
    assert not has_schedule_games("<nav>Football schedule</nav>")
    assert not has_schedule_games(script)


@pytest.fixture
def fake_crawl(tmp_path, monkeypatch):
    instances = []
    monkeypatch.setattr(discover, "REPO_ROOT", tmp_path)

    def install(responses, interrupt_url=None):
        class FakeFetcher:
            def __init__(self, **kwargs):
                self.options = kwargs
                self.calls = []
                self.closed = False
                instances.append(self)

            def get(self, url):
                self.calls.append(url)
                if url == interrupt_url:
                    raise KeyboardInterrupt
                response = responses[url]
                if isinstance(response, Exception):
                    raise response
                status, html = response
                path = tmp_path / (sha1(url.encode()).hexdigest() + ".html")
                path.write_text(html)
                return FetchResult(url, status, path, "a" * 64, True, "2026-11-16T20:00:00+00:00")

            def close(self):
                self.closed = True

        monkeypatch.setattr(discover, "Fetcher", FakeFetcher)
        return instances

    return tmp_path, install


def read_rows(root, name):
    with (root / "data" / name).open() as stream:
        return list(csv.DictReader(stream))


def test_crawl_fallback_manifest_skip_2020_and_cli(fake_crawl, monkeypatch):
    root, install = fake_crawl
    config = load_config()
    urls = discover.schedule_url_candidates(config, config.school("yale"), 2004)
    responses = {
        urls[0]: (404, "missing"),
        urls[1]: (200, SCHEDULE + f'<a href="{BOX}">Box</a>'),
        BOX: (200, "valid boxscore"),
    }
    instances = install(responses)
    assert cli.main(["crawl", "--schools", "yale", "--seasons", "2004,2020", "--refresh"]) == 0
    f = instances[-1]
    assert f.calls == [*urls, BOX] and f.closed
    assert f.options["refresh"] and f.options["min_delay_seconds"] == config.crawl.min_delay_seconds
    rows = read_rows(root, "manifest/urls.csv")
    indexed = {r["url"]: r for r in rows}
    assert len(rows) == 3 and indexed[urls[0]]["status"] == "404"
    assert indexed[urls[1]]["season_slug"] == indexed[BOX]["season_slug"] == "2004-05"
    before = (root / "data/manifest/urls.csv").read_bytes()
    discover.crawl(config, schools=["yale"], seasons=[2004, 2020])
    assert (root / "data/manifest/urls.csv").read_bytes() == before
    assert all(r["season"] == "2004" for r in rows)


@pytest.mark.parametrize(
    "first",
    [
        (200, "no games here"),
        (200, '<script src="/_Incapsula_Resource"></script>'),
        RobotsDisallowed("not allowed"),
        httpx.ReadTimeout("timed out"),
    ],
)
def test_unusable_schedule_falls_back_and_persists_error(fake_crawl, first, caplog):
    root, install = fake_crawl
    config = load_config()
    urls = discover.schedule_url_candidates(config, config.school("yale"), 2004)
    install({urls[0]: first, urls[1]: (200, SCHEDULE)})
    discover.crawl(config, schools=["yale"], seasons=[2004])
    errors = read_rows(root, "reports/crawl_errors.csv")
    assert len(errors) == 1 and errors[0]["url"] == urls[0] and errors[0]["error"]
    assert urls[0] in caplog.text


def test_boxscore_failure_continues_and_success_clears_old_error(fake_crawl):
    root, install = fake_crawl
    config = load_config()
    url = discover.schedule_url_candidates(config, config.school("yale"), 2004)[0]
    other = BOX.replace("10166", "10167")
    html = SCHEDULE + f'<a href="{BOX}">one</a><a href="{other}">two</a>'
    instances = install({url: (200, html), BOX: httpx.ReadTimeout("timeout"), other: (200, "ok")})
    discover.crawl(config, schools=["yale"], seasons=[2004])
    assert instances[-1].calls == [url, BOX, other]
    assert read_rows(root, "reports/crawl_errors.csv")[0]["url"] == BOX
    install({url: (200, html), BOX: (200, "ok"), other: (200, "ok")})
    discover.crawl(config, schools=["yale"], seasons=[2004])
    assert read_rows(root, "reports/crawl_errors.csv") == []


def test_interrupt_saves_progress_and_closes_client(fake_crawl):
    root, install = fake_crawl
    config = load_config()
    url = discover.schedule_url_candidates(config, config.school("yale"), 2004)[0]
    instances = install({url: (200, SCHEDULE + f'<a href="{BOX}">Box</a>')}, interrupt_url=BOX)
    with pytest.raises(KeyboardInterrupt):
        discover.crawl(config, schools=["yale"], seasons=[2004])
    assert instances[-1].closed
    assert read_rows(root, "manifest/urls.csv")[0]["url"] == url


def test_robots_provenance_reuses_cache_without_request(fake_crawl):
    root, install = fake_crawl
    config = load_config()
    url = discover.schedule_url_candidates(config, config.school("yale"), 2004)[0]
    robots = "https://yalebulldogs.com/robots.txt"
    stem = sha1(robots.encode()).hexdigest()
    cache = root / "data/raw/yalebulldogs.com"
    cache.mkdir(parents=True)
    (cache / f"{stem}.html").write_text("User-agent: *\nAllow: /")
    (cache / f"{stem}.json").write_text(
        json.dumps(
            {
                "url": robots,
                "status": 200,
                "sha256": "b" * 64,
                "fetched_at": "2026-11-16T20:00:00+00:00",
            }
        )
    )
    instances = install({url: (200, SCHEDULE)})
    discover.crawl(config, schools=["yale"], seasons=[2004])
    assert instances[-1].calls == [url]
    rows = read_rows(root, "manifest/urls.csv")
    assert {r["kind"] for r in rows} == {"schedule", "robots"}
    assert next(r for r in rows if r["kind"] == "robots")["url"] == robots


def test_unknown_school_fails_before_fetcher(fake_crawl):
    _, install = fake_crawl
    instances = install({})
    with pytest.raises(ValueError, match="unknown schools"):
        discover.crawl(load_config(), schools=["unknown"])
    assert instances == []


def test_real_fetcher_crawl_resume_is_offline_and_byte_identical(tmp_path, monkeypatch):
    config = load_config()
    urls = discover.schedule_url_candidates(config, config.school("yale"), 2004)
    calls = []
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    def handler(request):
        url = str(request.url)
        calls.append((url, now[0]))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\nCrawl-delay: 7")
        if url == urls[0]:
            return httpx.Response(404, text="missing")
        if url == urls[1]:
            return httpx.Response(200, text=SCHEDULE + f'<a href="{BOX}">Box</a>')
        assert url == BOX
        return httpx.Response(200, text="boxscore")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:

        def factory(**kwargs):
            return Fetcher(**kwargs, client=client, clock=lambda: now[0], sleep=sleep)

        monkeypatch.setattr(discover, "Fetcher", factory)
        monkeypatch.setattr(discover, "REPO_ROOT", tmp_path)
        discover.crawl(config, schools=["yale"], seasons=[2004])
        assert [url for url, _ in calls] == ["https://yalebulldogs.com/robots.txt", *urls, BOX]
        assert [timestamp for _, timestamp in calls] == [0, 7, 14, 21]
        before = {str(path): path.read_bytes() for path in (tmp_path / "data").rglob("*.csv")}
        discover.crawl(config, schools=["yale"], seasons=[2004])
        assert len(calls) == 4
        assert {
            str(path): path.read_bytes() for path in (tmp_path / "data").rglob("*.csv")
        } == before
