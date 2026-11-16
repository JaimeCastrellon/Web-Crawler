import httpx
import yaml

from ivydata import cli
from ivydata.crawl.fetcher import Fetcher


def test_capture_reports_failures_continues_and_reuses_cache(tmp_path, monkeypatch, capsys):
    directory = tmp_path / "tests" / "fixtures"
    directory.mkdir(parents=True)
    entries = {
        name: f"https://school.example/{name}"
        for name in ("ok", "missing", "blocked", "timeout", "last")
    }
    (directory / "fixtures.yaml").write_text(yaml.safe_dump(entries, sort_keys=False))
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /blocked")
        if request.url.path == "/timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if request.url.path == "/missing":
            return httpx.Response(404, text="not found")
        return httpx.Response(200, content=b"<html>\xc3\xa9</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    instances = []

    def make(**kwargs):
        now = [0.0]

        def sleep(seconds):
            now[0] += seconds

        fetcher = Fetcher(**kwargs, client=client, clock=lambda: now[0], sleep=sleep)
        instances.append(fetcher)
        return fetcher

    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "Fetcher", make)
    with client:
        assert cli.main(["fixtures"]) == 0
        assert (directory / "ok.html").read_bytes() == b"<html>\xc3\xa9</html>"
        assert (directory / "last.html").exists()
        assert not (directory / "missing.html").exists()
        assert not (directory / "blocked.html").exists()
        output = capsys.readouterr().out
        assert all(value in output for value in ("name", "status", "bytes", "404", "ERROR"))
        assert entries["missing"] in output and entries["blocked"] in output
        assert cli.main(["fixtures"]) == 0
        assert calls.count("/ok") == calls.count("/missing") == calls.count("/robots.txt") == 1
        assert cli.main(["fixtures", "--refresh"]) == 0
        assert calls.count("/ok") == calls.count("/robots.txt") == 2
    assert not instances[0].refresh and instances[-1].refresh
