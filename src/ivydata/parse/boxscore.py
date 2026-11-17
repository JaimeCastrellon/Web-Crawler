"""Box-score parser. Spec: docs/TASKS.md, Task 5.

Do NOT extract the W-L records printed in the page header — they are post-game
(AGENTS.md hard rule 4).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser, LexborNode

# Keys of ParsedBoxscore.game
GAME_FIELDS = [
    "date", "home_raw", "away_raw", "stadium", "city", "attendance",
    "home_q1", "home_q2", "home_q3", "home_q4", "home_ot", "home_pts",
    "away_q1", "away_q2", "away_q3", "away_q4", "away_ot", "away_pts",
    "num_ot",
]  # fmt: skip

# Keys of each dict in ParsedBoxscore.team_stats (plus "team_raw", "is_home")
TEAM_STAT_FIELDS = [
    "first_downs",
    "rush_att", "rush_yds", "rush_td",
    "pass_cmp", "pass_att", "pass_yds", "pass_td", "pass_int",
    "total_plays", "total_yds",
    "fumbles", "fumbles_lost",
    "penalties", "penalty_yds",
    "third_down_conv", "third_down_att",
    "fourth_down_conv", "fourth_down_att",
    "sacks_allowed", "sack_yds_lost",
    "punts", "punt_yds",
    "time_of_possession_s",
]  # fmt: skip


@dataclass
class ParsedBoxscore:
    page_url: str
    game: dict  # GAME_FIELDS; missing values are None
    team_stats: list[dict]  # exactly two dicts: TEAM_STAT_FIELDS + team_raw + is_home
    warnings: list[str] = field(default_factory=list)


def _text(node: LexborNode) -> str:
    long_name = node.css_first(".hide-on-small-down")
    return (long_name or node).text(separator=" ", strip=True)


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _warn(result: ParsedBoxscore, message: str, raw: str) -> None:
    result.warnings.append(f"{result.page_url}: {message}: {raw!r}")


def _numbers(value: str, count: int) -> list[int] | None:
    value = value.strip().replace("−", "-").replace("–", "-")
    patterns = {
        1: r"([+-]?\d[\d,]*)",
        2: r"([+-]?\d[\d,]*)\s*(?:-|of)\s*([+-]?\d[\d,]*)",
        3: r"([+-]?\d+)\s*-\s*([+-]?\d+)\s*-\s*([+-]?\d+)",
    }
    match = re.fullmatch(patterns[count], value, re.I)
    return [int(v.replace(",", "")) for v in match.groups()] if match else None


def _score(result: ParsedBoxscore, side: str, name: str, values: list[str]) -> None:
    result.game[f"{side}_raw"] = name or None
    stats = result.team_stats[side == "home"]
    stats["team_raw"] = name or None
    if len(values) < 5:
        _warn(result, "incomplete quarter scores", " ".join(values))
        return
    numbers = [_numbers(v, 1) for v in values]
    scores = [n[0] if n else None for n in numbers]
    for i in range(4):
        result.game[f"{side}_q{i + 1}"] = scores[i]
    overtime = scores[4:-1]
    result.game[f"{side}_ot"] = (
        sum(overtime) if overtime and all(n is not None for n in overtime) else None
    )
    result.game[f"{side}_pts"] = scores[-1]
    result.game["num_ot"] = len(overtime)
    if any(n is None for n in scores):
        _warn(result, "invalid quarter/final score", " ".join(values))
    elif sum(scores[:-1]) != scores[-1]:
        _warn(result, "quarter sum differs from final", f"{name}: {values}")


def _metadata(result: ParsedBoxscore, label: str, value: str) -> None:
    field = {
        "date": "date",
        "site": "city",
        "location": "city",
        "stadium": "stadium",
        "venue": "stadium",
        "attendance": "attendance",
    }.get(_key(label))
    if field is None:
        return
    value = value.strip()
    if field == "date":
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                result.game[field] = datetime.strptime(value, fmt).date().isoformat()
                return
            except ValueError:
                continue
        _warn(result, "invalid date", value)
    elif field == "attendance":
        parsed = _numbers(value, 1)
        if parsed:
            result.game[field] = parsed[0]
        elif value not in ("", "-", "--", "N/A"):
            _warn(result, "invalid attendance", value)
    else:
        result.game[field] = value or None


# Same labels appear in both legacy and modern Sidearm tables. Section context
# distinguishes rushing/passing net totals, first downs, and offensive plays.
_SECTION_FIELDS = {
    ("firstdowns", "total"): ("first_downs",),
    ("rushing", "totalnet"): ("rush_yds",),
    ("rushing", "attempts"): ("rush_att",),
    ("rushing", "rushingtds"): ("rush_td",),
    ("passing", "totalnet"): ("pass_yds",),
    ("passing", "compattint"): ("pass_cmp", "pass_att", "pass_int"),
    ("passing", "tds"): ("pass_td",),
    ("totaloffense", "yards"): ("total_yds",),
    ("totaloffense", "plays"): ("total_plays",),
    ("totaloffense", "fumbleslost"): ("fumbles", "fumbles_lost"),
    ("totaloffense", "penaltiesyds"): ("penalties", "penalty_yds"),
    ("punting", "puntsyds"): ("punts", "punt_yds"),
    ("miscellaneous", "posstime"): ("time_of_possession_s",),
    ("miscellaneous", "3rddownconv"): ("third_down_conv", "third_down_att"),
    ("miscellaneous", "4thdownconversions"): ("fourth_down_conv", "fourth_down_att"),
    ("miscellaneous", "sackstotalyds"): ("sacks_allowed", "sack_yds_lost"),
}
_PRE_FIELDS = {
    "firstdowns": ("first_downs",),
    "netyardsrushing": ("rush_yds",),
    "rushingattempts": ("rush_att",),
    "rushingtouchdowns": ("rush_td",),
    "netyardspassing": ("pass_yds",),
    "completionsattemptsint": ("pass_cmp", "pass_att", "pass_int"),
    "passescompleted": ("pass_cmp",),
    "passesattempted": ("pass_att",),
    "hadintercepted": ("pass_int",),
    "passingtouchdowns": ("pass_td",),
    "totaloffenseyards": ("total_yds",),
    "totalnetyards": ("total_yds",),
    "totaloffenseplays": ("total_plays",),
    "totaloffensiveplays": ("total_plays",),
    "fumblesnumberlost": ("fumbles", "fumbles_lost"),
    "penaltiesnumberyards": ("penalties", "penalty_yds"),
    "puntsyards": ("punts", "punt_yds"),
    "numberofpuntsyards": ("punts", "punt_yds"),
    "possessiontime": ("time_of_possession_s",),
    "thirddownconversions": ("third_down_conv", "third_down_att"),
    "fourthdownconversions": ("fourth_down_conv", "fourth_down_att"),
    "sacksbynumberyards": ("sacks_allowed", "sack_yds_lost"),
    "sacksallowed": ("sacks_allowed", "sack_yds_lost"),
}


def _stat(
    result: ParsedBoxscore,
    fields: tuple[str, ...],
    values: list[str],
    order: tuple[int, int],
    reverse: bool = False,
) -> None:
    for column, value in enumerate(values):
        if value.strip() in ("", "-", "--", "N/A"):
            continue
        if fields == ("time_of_possession_s",):
            match = re.fullmatch(r"(\d+):(\d{2})", value.strip())
            parsed = [int(match[1]) * 60 + int(match[2])] if match and int(match[2]) < 60 else None
        else:
            parsed = _numbers(value, len(fields))
        if parsed is None:
            _warn(result, f"invalid {'/'.join(fields)}", value)
            continue
        target = order[column]
        if reverse:
            target = 1 - target
        for field_name, number in zip(fields, parsed, strict=True):
            result.team_stats[target][field_name] = number


def _table_stats(result: ParsedBoxscore, table: LexborNode) -> None:
    order = (0, 1)
    headers = table.css("thead th")
    if len(headers) == 3 and headers[1].attributes.get("id") == "home-team":
        order = (1, 0)
    section = ""
    for row in table.css("tbody tr"):
        cells = row.css("th,td")
        sections = {key[0] for key in _SECTION_FIELDS} | {"kickoffs", "returns"}
        if len(cells) == 1 and _key(_text(cells[0])) in sections:
            section = _key(_text(cells[0]))
            continue
        if not cells:
            continue
        label = _key(_text(cells[0]))
        fields = _SECTION_FIELDS.get((section, label))
        # Older Sidearm uses '4th. Down Conv.' instead of 'Conversions'.
        if section == "miscellaneous" and label == "4thdownconv":
            fields = ("fourth_down_conv", "fourth_down_att")
        if fields and len(cells) != 3:
            _warn(result, "malformed team-statistics row", row.text(separator=" ", strip=True))
        elif fields:
            _stat(
                result,
                fields,
                [_text(c) for c in cells[1:]],
                order,
                reverse=fields[0] == "sacks_allowed",
            )


def _preformatted(result: ParsedBoxscore, blocks: list[LexborNode]) -> bool:
    found_scores = False
    found_stats = False
    for block in blocks:
        text = block.text()
        if not found_scores:
            scores = re.findall(r"^\s*(\S[^\n]*?)\.{2,}\s+((?:\d+\s+){4,})-\s*(\d+)", text, re.M)
            if len(scores) == 2:
                for side, (name, quarters, final) in zip(("away", "home"), scores, strict=True):
                    _score(result, side, name.strip(), quarters.split() + [final])
                found_scores = True
        for match in re.finditer(
            r"\b(Date|Site|Stadium|Attendance):\s*(.*?)(?=\s{2,}\w[^\n]*?:|\n|$)", text
        ):
            _metadata(result, match[1], match[2])
        if not found_stats and "team statistics" in text.lower():
            found_stats = True
            for line in text.splitlines():
                columns = re.split(r"\s{2,}", line.strip())
                label = _key(columns[0].rstrip("."))
                fields = _PRE_FIELDS.get(label)
                if fields and len(columns) != 3:
                    _warn(result, "malformed team-statistics row", line)
                elif fields:
                    _stat(
                        result, fields, columns[1:], (0, 1), reverse=label == "sacksbynumberyards"
                    )
    return found_stats


def _modern_sides(tree: LexborHTMLParser, result: ParsedBoxscore) -> None:
    """Modern tables put the tenant school last, even when it plays away.

    Read only the named home/visiting team identities from the JSON reference
    graph. Printed records and individual leaders are never extracted.
    """
    node = tree.css_first("script#__NUXT_DATA__")
    if node is None:
        return
    try:
        data = json.loads(node.text())
        if not isinstance(data, list):
            return

        def resolve(index: int):
            if type(index) is not int or not 0 <= index < len(data):
                raise ValueError("invalid state reference")
            return data[index]

        declarations = []
        for entry in data:
            if not isinstance(entry, dict) or not {
                "thisTeamIsHomeTeam",
                "homeTeam",
                "visitingTeam",
            }.issubset(entry):
                continue
            home = resolve(resolve(entry["homeTeam"])["name"])
            away = resolve(resolve(entry["visitingTeam"])["name"])
            if not isinstance(home, str) or not isinstance(away, str):
                raise ValueError("invalid home/visiting team names")
            declarations.append((home.strip().casefold(), away.strip().casefold()))
        if not declarations:
            return
        if len(set(declarations)) != 1:
            raise ValueError("conflicting home/visiting team declarations")
        home, away = declarations[0]
        current_home = (result.game["home_raw"] or "").strip().casefold()
        current_away = (result.game["away_raw"] or "").strip().casefold()
        if (home, away) == (current_home, current_away):
            return
        if (home, away) != (current_away, current_home):
            raise ValueError("structured team names disagree with line score")
        for key in GAME_FIELDS:
            if key.startswith("home_"):
                other = "away_" + key[5:]
                result.game[key], result.game[other] = result.game[other], result.game[key]
        result.team_stats.reverse()
        for index, stats in enumerate(result.team_stats):
            stats["is_home"] = bool(index)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        _warn(result, "unrecognized modern home/away state", str(exc))


def _overtime_detail(tree: LexborHTMLParser, result: ParsedBoxscore) -> None:
    # Older Sidearm line scores combine all extra sessions in one OT column.
    # Explicit period notes in this game's play-by-play are stronger evidence.
    periods = []
    for node in tree.css("#play-by-play"):
        for match in re.finditer(r"\b(\d+)(?:st|nd|rd|th)?\s*(?:overtime|OT)\b", node.text(), re.I):
            if 1 <= int(match[1]) <= 20:
                periods.append(int(match[1]))
    current = result.game["num_ot"]
    if periods:
        result.game["num_ot"] = max([current or 0, *periods])
    result._aggregate_ot = current == 1 and not periods


def parse_boxscore(html: str, page_url: str) -> ParsedBoxscore:
    """Parse Sidearm tables or archived text reports without reading header records.

    Legacy away/home follow line-score order; modern explicit team identities
    override tenant-first/last display order, independent of the hosting school.
    Missing fields remain None; malformed data is retained through URL warnings.
    """
    result = ParsedBoxscore(
        page_url,
        dict.fromkeys(GAME_FIELDS),
        [
            dict.fromkeys(TEAM_STAT_FIELDS) | {"team_raw": None, "is_home": home}
            for home in (False, True)
        ],
    )
    tree = LexborHTMLParser(html)
    score_found = False
    stats_found = False
    for table in tree.css("table"):
        caption = table.css_first("caption")
        headers = table.css("thead th")
        names = [_key(_text(h)) for h in headers]
        score_table = caption is not None and _key(caption.text()) == "teamscorebyquarter"
        score_table |= bool(names and names[0] == "team" and names[-1] in ("total", "f", "score"))
        if score_table and not score_found:
            rows = table.css("tbody tr")
            if len(rows) == 2:
                for side, row in zip(("away", "home"), rows, strict=True):
                    cells = row.css("th,td")
                    if cells:
                        _score(result, side, _text(cells[0]), [_text(c) for c in cells[1:]])
                score_found = True
        if not stats_found and (
            (caption is not None and _key(caption.text()) == "teamstatistics")
            or (len(headers) == 3 and "First Downs" in table.text())
        ):
            _table_stats(result, table)
            stats_found = True
    if not score_found:
        stats_found = _preformatted(result, tree.css("pre")) or stats_found
    for node in tree.css("dt"):
        sibling = node.next
        while sibling is not None and sibling.tag == "-text":
            sibling = sibling.next
        if sibling is not None and sibling.tag == "dd":
            _metadata(result, node.text(), _text(sibling))
    for node in tree.css(".game-information div"):
        spans = node.css("span")
        if len(spans) == 2:
            _metadata(result, spans[0].text(), spans[1].text())
    _modern_sides(tree, result)
    _overtime_detail(tree, result)
    if result.game["away_raw"] is None or result.game["home_raw"] is None:
        _warn(result, "missing/unrecognized line score", tree.text(separator=" ", strip=True)[:300])
    if not stats_found:
        _warn(
            result,
            "missing/unrecognized team statistics",
            tree.text(separator=" ", strip=True)[:300],
        )
    if result.game["date"] is None:
        _warn(result, "missing game date", "")
    return result
