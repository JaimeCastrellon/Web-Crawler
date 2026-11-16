"""Score-level dataset from schedule pages (milestone v0.1-data).

Input: a schedule export — JSON produced by the crawler (browser or Python) with, for each
school, the schedule pages it fetched and the game rows found on them:

    {"exported_at": "...", "schools": {"yale": {"host": "yalebulldogs.com", "pages": [
        {"season": 2024, "slug": "2024", "url": "/sports/football/schedule/2024",
         "status": 200, "fetched_at": "...", "rows": [
            {"cls": "...home-game...", "gid": "18407", "date": "Oct 12 (Sat) Noon",
             "vs": "vs", "opp": "Dartmouth", "loc": "New Haven, Conn. ...",
             "res": "L, 43-44 OT", "conf": "Ivy *", "box": "/sports/football/stats/..."}]}]}}}

Output: games.csv, team_game_stats.csv (score columns + pre-game records; box-score stat
columns empty until the box-score pass), split folders, manifest and coverage report.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from ivydata.config import Config
from ivydata.normalize.teams import canonical_team_id, is_ivy
from ivydata.parse.boxscore import TEAM_STAT_FIELDS
from ivydata.parse.schedule import ScheduleRow

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

GAME_COLUMNS = [
    "game_id", "season", "date", "home_team", "away_team", "neutral_site", "venue",
    "home_pts", "away_pts",
    "home_q1", "home_q2", "home_q3", "home_q4", "home_ot",
    "away_q1", "away_q2", "away_q3", "away_q4", "away_ot",
    "num_ot", "ivy_game", "attendance", "status", "stats_level", "split",
    "primary_source", "sources", "sources_agree", "source_urls",
]  # fmt: skip

TEAM_COLUMNS = [
    "game_id", "season", "date", "split", "stats_level",
    "team", "opponent", "is_home", "neutral_site", "ivy_game",
    "points", "points_allowed", "result",
    "games_before", "wins_before", "losses_before", "ties_before",
    "ivy_wins_before", "ivy_losses_before",
    *TEAM_STAT_FIELDS,
]  # fmt: skip


# ---------------------------------------------------------------- row parsing


def parse_game_date(text: str, season: int) -> str | None:
    """'Oct 12 (Sat) Noon' + 2024 -> '2024-10-12'. January/February belong to season+1."""
    m = _DATE.match(text.strip())
    if not m or m.group(1).lower() not in MONTHS:
        return None
    month = MONTHS[m.group(1).lower()]
    year = season + 1 if month <= 2 else season
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
            for r in page.get("rows", []):
                d = parse_game_date(r.get("date", ""), page["season"])
                if d is None:
                    warnings.append(f"{url}: unparseable date {r.get('date')!r} ({r.get('opp')})")
                    continue
                res, pts, opp_pts, num_ot, status = parse_result(r.get("res", ""))
                box = r.get("box") or None
                rows.append(
                    ScheduleRow(
                        school=school_id,
                        season=page["season"],
                        date=d,
                        opponent_raw=r.get("opp", ""),
                        location=parse_location(r.get("cls", ""), r.get("vs", "")),
                        venue=r.get("loc") or None,
                        result=res,
                        points=pts,
                        opponent_points=opp_pts,
                        boxscore_url=(base + box) if box and box.startswith("/") else box,
                        page_url=url,
                        num_ot=num_ot,
                        status_text=status,
                        source_game_id=r.get("gid") or None,
                        conference_text=r.get("conf") or None,
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
                ScheduleRow(
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
                    num_ot=num_ot,
                    status_text=None,
                    conference_text="nonconf" if (e.get("nonconf") or "").strip() else None,
                )
            )
    return ExportParse(rows=rows, pages=pages, warnings=warnings)


# ---------------------------------------------------------------- merging


def make_game_id(date_iso: str, home: str, away: str, neutral: bool) -> str:
    d = date_iso.replace("-", "")
    if neutral:
        a, b = sorted([home, away])
        return f"{d}-{a}-vs-{b}"
    return f"{d}-{away}-at-{home}"


@dataclass
class _View:
    """One source's view of a game, oriented home/away."""

    row: ScheduleRow
    team: str
    opp: str

    @property
    def source(self) -> str:
        return "wikipedia" if "wikipedia.org" in self.row.page_url else "official"

    @property
    def label(self) -> str:
        return f"{self.source}:{self.team}"

    @property
    def home_away(self) -> tuple[str, str]:
        if self.row.location == "away":
            return self.opp, self.team
        if self.row.location == "neutral":
            return tuple(sorted([self.team, self.opp]))  # type: ignore[return-value]
        return self.team, self.opp

    def points_for(self, team: str) -> int | None:
        return self.row.points if team == self.team else self.row.opponent_points


def merge_schedule_rows(rows: list[ScheduleRow], config: Config) -> tuple[list[dict], list[str]]:
    """One game dict per real game. Copies of the same game from either school's official page
    or Wikipedia page are merged; official sites win over Wikipedia, disagreements are reported.

    Matching does not rely on opponent spelling: a school plays at most one game in any
    five-day window, so copies from the same school within two days are the same game, and an
    Ivy opponent's copy matches when it names this school within two days.
    """
    views: list[_View] = []
    for r in rows:
        opp = canonical_team_id(r.opponent_raw, config.team_aliases)
        if opp == r.school:
            continue  # scrimmage/intrasquad or a parsing slip
        views.append(_View(r, r.school, opp))

    parent = list(range(len(views)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    by_school: dict[str, list[int]] = defaultdict(list)
    for i, v in enumerate(views):
        by_school[v.team].append(i)
    window = timedelta(days=2)
    for idxs in by_school.values():
        idxs.sort(key=lambda i: views[i].row.date)
        for a, b in zip(idxs, idxs[1:], strict=False):
            da, db = (date.fromisoformat(views[k].row.date) for k in (a, b))
            if db - da <= window:
                union(a, b)
    for i, v in enumerate(views):
        if not is_ivy(v.opp):
            continue
        d = date.fromisoformat(v.row.date)
        for j in by_school.get(v.opp, []):
            w = views[j]
            if w.opp == v.team and abs(date.fromisoformat(w.row.date) - d) <= window:
                union(i, j)

    comps: dict[int, list[_View]] = defaultdict(list)
    for i, v in enumerate(views):
        comps[find(i)].append(v)

    games: list[dict] = []
    conflicts: list[str] = []
    for g in comps.values():
        games.append(_game_from_group(g, config, conflicts))
    games.sort(key=lambda x: (x["date"], x["game_id"]))

    seen: dict[str, int] = {}
    for gm in games:  # extremely rare: two games, same day, same pair
        n = seen.get(gm["game_id"], 0)
        seen[gm["game_id"]] = n + 1
        if n:
            gm["game_id"] += f"-{n + 1}"
    return games, conflicts


def _game_from_group(g: list[_View], config: Config, conflicts: list[str]) -> dict:
    # Prefer official over Wikipedia, played over unplayed; ties by school id.
    g = sorted(g, key=lambda v: (v.source != "official", v.row.points is None, v.team))
    primary = g[0]
    ref = primary.team
    opp = primary.opp
    if not is_ivy(opp):  # Wikipedia spells non-Ivy opponents consistently across schools
        opp = next((v.opp for v in g if v.source == "wikipedia" and v.team == ref), opp)
    # Wikipedia marks neutral sites (e.g. Harvard–Yale at Fenway) that official pages list as
    # home/away, so any copy saying "neutral" wins.
    neutral = any(v.row.location == "neutral" for v in g)
    if neutral:
        home, away = sorted([ref, opp])
    elif primary.row.location == "away":
        home, away = opp, ref
    else:
        home, away = ref, opp
    tag = f"{primary.row.date} {away}@{home}"

    def side(v: _View) -> str:  # where `ref` played, according to this copy
        if v.team == ref or v.row.location == "neutral":
            return v.row.location
        return {"home": "away", "away": "home"}[v.row.location]

    def pts(v: _View, team: str) -> int | None:  # points for `team` (ref or the other side)
        mine = v.team == ref
        return (
            (v.row.points if mine else v.row.opponent_points)
            if team == ref
            else (v.row.opponent_points if mine else v.row.points)
        )

    agree: bool | None = None
    if len(g) > 1:
        agree = True
        if len({v.row.date for v in g}) > 1:
            agree = False
            conflicts.append(
                f"date mismatch {tag}: " + ", ".join(f"{v.label}={v.row.date}" for v in g)
            )
        played = [v for v in g if v.row.points is not None]
        if len(played) > 1 and any(len({pts(v, t) for v in played}) > 1 for t in (ref, "_")):
            agree = False
            conflicts.append(
                f"score mismatch {tag}: "
                + ", ".join(f"{v.label}={pts(v, ref)}-{pts(v, '_')} ({ref} first)" for v in played)
            )
        sides = {side(v) for v in g if v.row.location != "neutral"}
        if len(sides) > 1:
            agree = False
            conflicts.append(
                f"home/away mismatch {tag}: " + ", ".join(f"{v.label}={side(v)}" for v in g)
            )

    season = primary.row.season
    played_views = [v for v in g if v.row.points is not None]
    num_ot = primary.row.num_ot or max((v.row.num_ot for v in played_views), default=0)
    if primary.row.points is not None:
        status = "final"
    else:
        text = next((v.row.status_text for v in g if v.row.status_text), None)
        past = date.fromisoformat(primary.row.date) < date.today()
        status = text or ("no_result" if past else "scheduled")
    box_urls = [v.row.boxscore_url for v in g if v.row.boxscore_url]
    return {
        "game_id": make_game_id(primary.row.date, home, away, neutral),
        "season": season,
        "date": primary.row.date,
        "home_team": home,
        "away_team": away,
        "neutral_site": neutral,
        "venue": next((v.row.venue for v in g if v.row.venue), None),
        "home_pts": pts(primary, ref) if home == ref else pts(primary, "_"),
        "away_pts": pts(primary, ref) if away == ref else pts(primary, "_"),
        "num_ot": num_ot,
        "ivy_game": is_ivy(home) and is_ivy(away),
        "status": status.lower(),
        "stats_level": "score_only",
        "split": config.splits.split_for(season),
        "primary_source": primary.label,
        "sources": "|".join(sorted({v.label for v in g})),
        "sources_agree": agree,
        "source_urls": "|".join(sorted({v.row.page_url for v in g} | set(box_urls))),
        "_boxscore_urls": sorted(set(box_urls)),
    }


# ---------------------------------------------------------------- team rows


def team_rows(games: list[dict]) -> list[dict]:
    """Two rows per game with pre-game records counted from earlier games only."""
    out: list[dict] = []
    for gm in games:
        for team, opp, is_home in (
            (gm["home_team"], gm["away_team"], True),
            (gm["away_team"], gm["home_team"], False),
        ):
            pts = gm["home_pts"] if is_home else gm["away_pts"]
            opp_pts = gm["away_pts"] if is_home else gm["home_pts"]
            result = None
            if pts is not None and opp_pts is not None:
                result = "W" if pts > opp_pts else "L" if pts < opp_pts else "T"
            out.append(
                {
                    "game_id": gm["game_id"],
                    "season": gm["season"],
                    "date": gm["date"],
                    "split": gm["split"],
                    "stats_level": gm["stats_level"],
                    "team": team,
                    "opponent": opp,
                    "is_home": is_home and not gm["neutral_site"],
                    "neutral_site": gm["neutral_site"],
                    "ivy_game": gm["ivy_game"],
                    "points": pts,
                    "points_allowed": opp_pts,
                    "result": result,
                }
            )
    out.sort(key=lambda r: (r["team"], r["date"], r["game_id"]))
    rec: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: dict.fromkeys(("g", "w", "l", "t", "iw", "il"), 0)
    )
    for r in out:
        c = rec[(r["team"], r["season"])]
        if not is_ivy(r["team"]):
            continue  # we only see non-Ivy teams' games vs Ivy opponents: records would mislead
        r.update(
            games_before=c["g"],
            wins_before=c["w"],
            losses_before=c["l"],
            ties_before=c["t"],
            ivy_wins_before=c["iw"],
            ivy_losses_before=c["il"],
        )
        if r["result"]:
            c["g"] += 1
            c[{"W": "w", "L": "l", "T": "t"}[r["result"]]] += 1
            if r["ivy_game"] and r["result"] in "WL":
                c["iw" if r["result"] == "W" else "il"] += 1
    out.sort(key=lambda r: (r["date"], r["game_id"], r["team"]))
    return out


# ---------------------------------------------------------------- output


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow([_fmt(r.get(c)) for c in columns])


def coverage(pages: list[dict], games: list[dict], config: Config) -> list[dict]:
    """Per (school, season): which source supplied the schedule and how many games we have."""
    best: dict[tuple[str, int, str], dict] = {}
    for p in pages:
        k = (p["school"], p["season"], p["kind"])
        if k not in best or p["games_found"] > best[k]["games_found"]:
            best[k] = p
    counts: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    for gm in games:
        for t in (gm["home_team"], gm["away_team"]):
            if is_ivy(t):
                c = counts[(t, gm["season"])]
                c[0] += 1
                c[1] += gm["home_pts"] is not None
                c[2] += bool(gm["_boxscore_urls"])
    out = []
    for s in config.schools:
        for season in config.splits.seasons():
            off = best.get((s.id, season, "schedule"))
            wiki = best.get((s.id, season, "wikipedia"))
            n, scored, boxed = counts.get((s.id, season), [0, 0, 0])
            if off and off["games_found"]:
                source, page = "official", off
            elif wiki and wiki["games_found"]:
                source, page = "wikipedia", wiki
            else:
                source, page = "", None
            if n == 0:
                level = "missing"
            elif boxed == n:
                level = "full"
            elif boxed:
                level = "partial"
            else:
                level = "score_only"
            out.append(
                {
                    "school": s.id,
                    "season": season,
                    "schedule_source": source,
                    "schedule_url": page["url"] if page else "",
                    "games_on_schedule": page["games_found"] if page else 0,
                    "games_in_dataset": n,
                    "games_with_scores": scored,
                    "boxscore_links": boxed,
                    "level": level,
                }
            )
    return out


def build_scores(
    official_exports: list[Path],
    wikipedia_export: Path | None,
    repo_root: Path,
    config: Config,
) -> dict:
    rows: list[ScheduleRow] = []
    pages: list[dict] = []
    warnings: list[str] = []
    for path in official_exports:
        parsed = rows_from_export(json.loads(path.read_text(encoding="utf-8")), config)
        rows += parsed.rows
        pages += parsed.pages
        warnings += parsed.warnings
    if wikipedia_export is not None:
        parsed = rows_from_wikipedia(json.loads(wikipedia_export.read_text(encoding="utf-8")))
        rows += parsed.rows
        pages += parsed.pages
        warnings += parsed.warnings

    games, conflicts = merge_schedule_rows(rows, config)
    teams = team_rows(games)

    proc = repo_root / "data" / "processed"
    write_csv(proc / "games.csv", games, GAME_COLUMNS)
    write_csv(proc / "team_game_stats.csv", teams, TEAM_COLUMNS)
    for split in config.splits.ranges:
        write_csv(
            proc / split / "games.csv", [g for g in games if g["split"] == split], GAME_COLUMNS
        )
        write_csv(
            proc / split / "team_game_stats.csv",
            [t for t in teams if t["split"] == split],
            TEAM_COLUMNS,
        )

    manifest_cols = ["url", "school", "season", "kind", "status", "fetched_at", "sha256",
                     "season_slug"]  # fmt: skip
    pages = sorted(pages, key=lambda p: (p["school"], p["season"], p["kind"], p["url"]))
    write_csv(repo_root / "data" / "manifest" / "urls.csv", pages, manifest_cols)

    cov = coverage(pages, games, config)
    write_csv(repo_root / "data" / "reports" / "coverage_report.csv", cov, list(cov[0].keys()))
    box = sorted({u for g in games for u in g["_boxscore_urls"]})
    (repo_root / "data" / "manifest" / "boxscore_urls.txt").write_text(
        "\n".join(box) + "\n", encoding="utf-8"
    )
    return {
        "games": games,
        "team_rows": teams,
        "conflicts": conflicts,
        "warnings": warnings,
        "coverage": cov,
        "boxscore_urls": len(box),
    }


def write_validation_report(result: dict, path: Path) -> None:
    games = result["games"]
    by_season: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for g in games:
        s = by_season[g["season"]]
        s["games"] += 1
        s["ivy"] += g["ivy_game"]
        s["final"] += g["status"] == "final"
        s["official"] += g["primary_source"].startswith("official")
        s["multi"] += g["sources_agree"] is not None
        s["disagree"] += g["sources_agree"] is False
    n_multi = sum(g["sources_agree"] is not None for g in games)
    n_dis = sum(g["sources_agree"] is False for g in games)
    lines = [
        "# Validation report",
        "",
        f"- Games: **{len(games)}**; team rows: **{len(result['team_rows'])}**",
        f"- Games with ≥2 copies: **{n_multi}**; copies disagree on **{n_dis}** (listed below)",
        f"- Parse warnings: **{len(result['warnings'])}**",
        "",
        "## Per season",
        "",
        "| season | split | games | Ivy games | final | official primary | ≥2 copies | disagree |",
        "|---|---|---|---|---|---|---|---|",
    ]
    splits = {g["season"]: g["split"] for g in games}
    for season in sorted(by_season):
        s = by_season[season]
        lines.append(
            f"| {season} | {splits[season]} | {s['games']} | {s['ivy']} | {s['final']} | "
            f"{s['official']} | {s['multi']} | {s['disagree']} |"
        )
    not_final = [g for g in games if g["status"] != "final"]
    lines += ["", "## Games without a final score", ""]
    lines += [f"- `{g['game_id']}` — {g['status']} ({g['sources']})" for g in not_final] or [
        "None."
    ]
    lines += [
        "",
        "## Source disagreements",
        "",
        "Official athletics-site values are used when present (`primary_source`). Each line lists",
        "every copy; for scores, the first-named team's points come first.",
        "",
    ]
    lines += [f"- {c}" for c in sorted(result["conflicts"])] or ["None."]
    if result["warnings"]:
        lines += ["", "## Parse warnings", ""] + [f"- {w}" for w in result["warnings"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
