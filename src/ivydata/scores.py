"""Offline adapters for factual schedule exports proposed in PR #13.

Source-specific parsing lives here. Merging, pre-game records, schema, splits,
cache checks and publication all delegate to the canonical build pipeline.
No HTTP client or wall-clock date is used by these adapters.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ivydata.config import Config
from ivydata.parse.schedule import ScheduleRow


@dataclass
class ExportScheduleRow(ScheduleRow):
    """Extra source-result/provenance metadata without changing the parser contract."""

    num_ot: int | None = None
    status_text: str | None = None
    source_game_id: str | None = None
    conference_text: str | None = None
    source_kind: str = "official_export"
    original_date: str | None = None


MONTHS = {
    m: i
    for i, ms in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in ms
}

_DATE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})\b")
_RESULT = re.compile(r"^([WLT])\s*,?\s*(\d+)\s*-\s*(\d+)\s*(.*)$")
_OT = re.compile(r"(\d*)\s*OT", re.I)

# ---------------------------------------------------------------- row parsing


def parse_game_date(text: str, season: int) -> str | None:
    """'Oct 12 (Sat) Noon' + 2024 -> '2024-10-12'. January/February belong to season+1."""
    m = _DATE.match(text.strip())
    if not m or m.group(1).lower() not in MONTHS:
        return None
    month = MONTHS[m.group(1).lower()]
    year = season + 1 if month <= 3 else season
    try:
        return date(year, month, int(m.group(2))).isoformat()
    except ValueError:
        return None


def parse_result(text: str) -> tuple[str | None, int | None, int | None, int, str | None]:
    """'L, 43-44 OT' -> ('L', 43, 44, 1, None). Scores are from the page owner's side.
    Non-results ('Canceled', '') -> (None, None, None, 0, status_text)."""
    t = " ".join(text.split())
    m = _RESULT.match(t)
    if not m:
        return None, None, None, 0, (t or None)
    rest = m.group(4)
    num_ot = 0
    ot = _OT.search(rest)
    if ot:
        num_ot = int(ot.group(1)) if ot.group(1) else 1
    return m.group(1), int(m.group(2)), int(m.group(3)), num_ot, None


def parse_location(cls: str, vs: str) -> str:
    c = cls.lower()
    if "neutral" in c:
        return "neutral"
    if "away-game" in c:
        return "away"
    if "home-game" in c:
        return "home"
    return "away" if vs.strip().lower() in ("at", "@") else "home"


@dataclass
class ExportParse:
    rows: list[ScheduleRow]
    pages: list[dict]  # manifest rows
    warnings: list[str] = field(default_factory=list)


def rows_from_export(export: dict, config: Config) -> ExportParse:
    """Rows from an athletics-site (Sidearm) schedule export."""
    rows: list[ScheduleRow] = []
    pages: list[dict] = []
    warnings: list[str] = []
    for school_id, payload in sorted(export["schools"].items()):
        base = config.school(school_id).base_url
        for page in payload["pages"]:
            url = base + page["url"]
            pages.append(
                {
                    "url": url,
                    "school": school_id,
                    "season": page["season"],
                    "kind": "schedule",
                    "status": page.get("status", ""),
                    "fetched_at": page.get("fetched_at", ""),
                    "sha256": "",
                    "season_slug": page.get("slug", ""),
                    "games_found": len(page.get("rows", [])),
                }
            )
            if page.get("status") != 200:
                warnings.append(f"{url}: export HTTP {page.get('status')}; rows excluded")
                continue
            for r in page.get("rows", []):
                d = parse_game_date(r.get("date", ""), page["season"])
                if d is None:
                    warnings.append(f"{url}: unparseable date {r.get('date')!r} ({r.get('opp')})")
                    continue
                raw_result = r.get("res", "")
                res, pts, opp_pts, num_ot, status = parse_result(raw_result)
                if (
                    raw_result.strip()
                    and res is None
                    and not re.search(
                        r"cancel|postpon|suspend|scheduled|\bTBA\b|\bTBD\b", raw_result, re.I
                    )
                ):
                    warnings.append(f"{url}: unrecognized result {raw_result!r} ({r.get('opp')})")
                opponent = r.get("opp", "")
                if opponent.strip().casefold() == "the game" and school_id in ("yale", "harvard"):
                    opponent = "Harvard" if school_id == "yale" else "Yale"
                box = r.get("box") or None
                rows.append(
                    ExportScheduleRow(
                        school=school_id,
                        season=page["season"],
                        date=d,
                        opponent_raw=opponent,
                        location=parse_location(r.get("cls", ""), r.get("vs", "")),
                        venue=r.get("loc") or None,
                        result=res,
                        points=pts,
                        opponent_points=opp_pts,
                        boxscore_url=(base + box) if box and box.startswith("/") else box,
                        page_url=url,
                        num_ot=num_ot if num_ot > 0 else None,
                        status_text=status,
                        source_game_id=r.get("gid") or None,
                        conference_text=r.get("conf") or None,
                        source_kind="official_export",
                    )
                )
    return ExportParse(rows=rows, pages=pages, warnings=warnings)


# ---------------------------------------------------------------- Wikipedia fallback

_WIKILINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_CFB_LINK = re.compile(r"\{\{\s*cfb link\s*\|([^}]*)\}\}", re.I)
_TAGS = re.compile(r"<[^>]*>")
_TEMPLATE = re.compile(r"\{\{([^{}|]*)((?:\|[^{}]*)?)\}\}")
_KEEP_FIRST_ARG = {"tooltip", "nowrap", "small", "abbr", "nobr", "sort", "abbrlink"}
_DASHES = {"ndash": "–", "mdash": "—", "snd": " – ", "spaced ndash": " – "}


def clean_wikitext(v: str) -> str:
    def cfb(m: re.Match) -> str:
        params = dict(kv.split("=", 1) for kv in m.group(1).split("|") if "=" in kv)
        title = params.get("title") or params.get("team", "")
        return title.strip()

    v = _CFB_LINK.sub(cfb, v)
    v = _WIKILINK.sub(lambda m: m.group(1), v)

    def template(m: re.Match) -> str:
        name = m.group(1).strip().lower()
        args = [a for a in m.group(2).split("|")[1:] if "=" not in a]
        if name in _DASHES:
            return _DASHES[name]
        if name in _KEEP_FIRST_ARG and args:
            return args[0]
        return ""

    for _ in range(3):  # nested templates, innermost first
        v = _TEMPLATE.sub(template, v)
    v = _TAGS.sub("", v)
    v = v.replace("&nbsp;", " ")
    return " ".join(v.split()).strip()


_POS_RESULT = re.compile(
    r"(?:^|\|)\s*([WLT])\s+(\d+)\s*(?:[-–]|&ndash;|\{\{\s*ndash\s*\}\}|\s)\s*(\d+)([^|]*)"
)


_TIME = re.compile(r"^\d{1,2}(:\d\d)?\s*[ap]\.?m\.?|^(noon|tba|tbd)$", re.I)


def _positional_entry(raw: str) -> dict:
    """Re-read an old positional {{CFB schedule}} row ('date | [time] | [@/vs.] | opponent |
    stadium | city | [tv] | result | attendance'), where optional columns may be blank."""
    vals = [v.strip() for v in raw.split(" | ")]
    e: dict = {"date": vals[0], "_raw": raw}
    marker = ""
    for i, v in enumerate(vals[1:], start=1):
        low = v.lower()
        if low in ("@", "at"):
            marker = "away"
        elif low in ("vs.", "vs", "n"):
            marker = "neutral"
        elif v and not _TIME.match(v) and re.search(r"[A-Za-z]", clean_wikitext(v)):
            if re.match(r"^(?:@|at\b)\s*", v, re.I):
                marker = "away"
                v = re.sub(r"^(?:@|at\b)\s*", "", v, flags=re.I)
            e["opponent"] = v
            e["site_stadium"] = vals[i + 1] if i + 1 < len(vals) else ""
            e["site_cityst"] = vals[i + 2] if i + 2 < len(vals) else ""
            break
    if marker == "away":
        e["away"] = "y"
    elif marker == "neutral":
        e["neutral"] = "y"
    if "<ncg>" in e.get("opponent", "").lower():
        e["nonconf"] = "y"
    return e


def _wiki_result(e: dict) -> tuple[str | None, int | None, int | None, int]:
    if not e.get("w/l") and e.get("_raw"):  # positional row whose score didn't parse in-page
        m = _POS_RESULT.search(e["_raw"])
        if m:
            e = {**e, "w/l": m.group(1), "score": f"{m.group(2)}–{m.group(3)}{m.group(4)}"}
    wl = (e.get("w/l") or "").strip().lower()[:1].upper() or None
    m = re.match(r"^\s*(\d+)\s*[-–]\s*(\d+)(.*)$", clean_wikitext(e.get("score", "")))
    if not m or wl not in ("W", "L", "T"):
        return None, None, None, 0
    a, b = int(m.group(1)), int(m.group(2))
    hi, lo = max(a, b), min(a, b)
    pts, opp = {"W": (hi, lo), "L": (lo, hi), "T": (a, b)}[wl]
    ot_text = " ".join([m.group(3), e.get("ot", ""), e.get("overtime", "")])
    ot = _OT.search(ot_text)
    num_ot = (int(ot.group(1)) if ot.group(1) else 1) if ot else 0
    return wl, pts, opp, num_ot


def rows_from_wikipedia(export: dict) -> ExportParse:
    """Rows from Wikipedia team-season pages ({{CFB schedule entry}} templates or the older
    positional {{CFB schedule}} rows), used where the official site is not crawlable."""
    rows: list[ScheduleRow] = []
    pages: list[dict] = []
    warnings: list[str] = []
    for page in export["pages"]:
        pages.append(
            {
                "url": page["url"],
                "school": page["school"],
                "season": page["season"],
                "kind": "wikipedia",
                "status": 200 if page.get("exists") else 404,
                "fetched_at": page.get("fetched_at", ""),
                "sha256": f"revid:{page.get('revid', '')}",
                "season_slug": "",
                "games_found": len(page.get("entries", [])),
            }
        )
        if not page.get("exists"):
            warnings.append(f"{page['url']}: missing exported Wikipedia page; rows excluded")
            continue
        for e in page.get("entries", []):
            if e.get("_format") == "positional" and e.get("_raw"):
                e = {
                    **_positional_entry(e["_raw"]),
                    "w/l": e.get("w/l") or "",
                    "score": e.get("score") or "",
                    "ot": e.get("ot", ""),
                }
            d = parse_game_date(clean_wikitext(e.get("date", "")), page["season"])
            if d is None:
                warnings.append(f"{page['url']}: unparseable date {e.get('date')!r}")
                continue
            opp = clean_wikitext(e.get("opponent", ""))
            if not opp:
                warnings.append(f"{page['url']}: no opponent on {d}")
                continue
            wl, pts, opp_pts, num_ot = _wiki_result(e)
            loc = (
                "neutral"
                if (e.get("neutral") or "").strip()
                else ("away" if (e.get("away") or "").strip() else "home")
            )
            venue = ", ".join(
                x for x in (clean_wikitext(e.get("site_stadium", "")),
                            clean_wikitext(e.get("site_cityst", ""))) if x
            )  # fmt: skip
            rows.append(
                ExportScheduleRow(
                    school=page["school"],
                    season=page["season"],
                    date=d,
                    opponent_raw=opp,
                    location=loc,
                    venue=venue or None,
                    result=wl,
                    points=pts,
                    opponent_points=opp_pts,
                    boxscore_url=None,
                    page_url=page["url"],
                    num_ot=num_ot if num_ot > 0 else None,
                    status_text=None,
                    conference_text="nonconf" if (e.get("nonconf") or "").strip() else None,
                    source_kind="wikipedia",
                )
            )
    return ExportParse(rows=rows, pages=pages, warnings=warnings)


SOURCE_COLUMNS = [
    "url",
    "school",
    "season",
    "kind",
    "status",
    "fetched_at",
    "revision_id",
    "export_path",
    "export_sha256",
    "payload_sha256",
    "games_found",
]


def load_score_exports(paths: list[Path], config: Config) -> ExportParse:
    """Read saved factual row exports, with file/payload checksums and explicit provenance."""
    from hashlib import sha256

    combined = ExportParse([], [])
    allowed = set(config.splits.seasons())
    for path in sorted(paths):
        content = path.read_bytes()
        export = json.loads(content)
        parsed = (
            rows_from_export(export, config) if "schools" in export else rows_from_wikipedia(export)
        )
        for row in parsed.rows:
            config.school(row.school)
            if row.season in allowed:
                combined.rows.append(row)
        combined.warnings.extend(parsed.warnings)
        raw_pages = (
            [p for school in export["schools"].values() for p in school["pages"]]
            if "schools" in export
            else export["pages"]
        )
        for page, payload in zip(parsed.pages, raw_pages, strict=True):
            if int(page["season"]) not in allowed:
                continue
            combined.pages.append(
                {
                    "url": page["url"],
                    "school": page["school"],
                    "season": page["season"],
                    "kind": "official_export" if "schools" in export else "wikipedia",
                    "status": page["status"],
                    "fetched_at": page["fetched_at"],
                    "revision_id": payload.get("revid", ""),
                    "export_path": (
                        f"data/sources/{path.name}"
                        if path.parent.name == "sources" and path.parent.parent.name == "data"
                        else str(path.resolve())
                    ),
                    "export_sha256": sha256(content).hexdigest(),
                    "payload_sha256": sha256(
                        json.dumps(
                            payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                    "games_found": page["games_found"],
                }
            )
    # One reviewed error lies outside the standard one-day merge tolerance.
    # Apply it only when the supplied official Penn export corroborates the
    # corrected date; keep the original date for source-agreement reporting.
    target = "https://en.wikipedia.org/wiki/2001_Dartmouth_Big_Green_football_team"
    evidence = "https://pennathletics.com/sports/football/schedule/2001"
    corroborated = any(
        r.page_url == evidence
        and r.date == "2001-09-29"
        and r.opponent_raw.casefold().startswith("dartmouth")
        for r in combined.rows
    )
    if corroborated:
        for row in combined.rows:
            if (
                row.page_url == target
                and row.date == "2001-09-27"
                and row.opponent_raw.casefold() == "penn"
            ):
                row.original_date = row.date
                row.date = "2001-09-29"
                combined.warnings.append(
                    f"{target}: reviewed date correction 2001-09-27 -> 2001-09-29; "
                    f"corroborated by {evidence}; original disagreement retained"
                )
    return combined


def default_export_paths(directory: Path) -> list[Path]:
    """Discover only the documented legacy-export filenames, not arbitrary cache files."""
    names = [
        "ivy_official_cornell.json",
        "ivy_official_penn.json",
        "ivy_official_yale.json",
        "ivy_wikipedia_schedules.json",
    ]
    return [directory / name for name in names if (directory / name).exists()]


def build_scores(
    official_exports: list[Path], wikipedia_export: Path | None, repo_root: Path, config: Config
) -> dict:
    """Compatibility entry point: use the shared build, merge, records, and CSV schemas."""
    from ivydata.build import _build

    paths = [*official_exports, *([wikipedia_export] if wikipedia_export is not None else [])]
    parsed = load_score_exports(paths, config)
    return _build(repo_root / "data/raw", repo_root / "data/processed", config, parsed)


def make_game_id(date_iso: str, home: str, away: str, neutral: bool) -> str:
    """Compatibility alias for the canonical game-id implementation."""
    from ivydata.normalize.merge import make_game_id as canonical

    return canonical(date_iso, home, away, neutral)
