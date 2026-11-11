#!/usr/bin/env python3
"""Official NBA 2026-27 COMPLETE defender/offender matchup season collector.

Public free-CPU GitHub workflow executes the script with a private-104-only
write token. All original API response bytes live in a private, SHA-verified,
versioned release. Only aggregate QA is written to public CI logs.

Never mix this NBA per-matchup feed with Blueprint shot-level nearest defenders,
the two Blueprint featured defensive spotlights, or modeled tracking assignments.
"""
from __future__ import annotations

import base64
import collections
import concurrent.futures
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

REPO = "timeedmonds-maker/104"
SEASON_START = dt.date(2026, 10, 20)
BLUEPRINT_BASE = "data/extensions/nba_blueprint_2026_27/matchups"
SEASON_PATH = BLUEPRINT_BASE + "/season_to_date"
LATEST_TAG = "nba-2026-27-defensive-matchups-latest"
WORK = pathlib.Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "official-matchups-2026-27"
WORK.mkdir(exist_ok=True, parents=True)
SOURCE_HOST = "https://stats.gleague.nba.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
FIELDS = [
    "matchupMinutes", "matchupMinutesSort", "partialPossessions",
    "percentageDefenderTotalTime", "percentageOffensiveTotalTime",
    "percentageTotalTimeBothOn", "switchesOn", "playerPoints", "teamPoints",
    "matchupAssists", "matchupPotentialAssists", "matchupTurnovers",
    "matchupBlocks", "matchupFieldGoalsMade", "matchupFieldGoalsAttempted",
    "matchupFieldGoalsPercentage", "matchupThreePointersMade",
    "matchupThreePointersAttempted", "matchupThreePointersPercentage",
    "helpBlocks", "helpFieldGoalsMade", "helpFieldGoalsAttempted",
    "helpFieldGoalsPercentage", "matchupFreeThrowsMade",
    "matchupFreeThrowsAttempted", "shootingFouls",
]
COLS = [
    "nba_game_id", "defense_team_id", "defense_team_abbr",
    "offense_team_id", "offense_team_abbr", "defender_player_id",
    "defender_player_name", "offensive_player_id", "offensive_player_name",
    *FIELDS, "source", "source_response_sha256", "source_format",
    "legacy_player_fg_points", "legacy_team_fg_points",
]


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def api(path: str, data: dict | None = None, verb: str = "GET"):
    argv = ["gh", "api", "-X", verb, path]
    if data is not None:
        argv += ["--input", "-"]
    result = subprocess.run(
        argv, input=json.dumps(data, ensure_ascii=False) if data is not None else None,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
    )
    if result.returncode:
        raise RuntimeError(f"PRIVATE_GITHUB_API_{verb}_FAILED: {path}: "
                           + result.stderr[-400:])
    return json.loads(result.stdout)


def gh(*args: str, must=True):
    result = subprocess.run(
        ["gh", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=100,
    )
    if must and result.returncode:
        raise RuntimeError("PRIVATE_GH_ACTION_FAILED " + " ".join(args[:3])
                           + ": " + result.stderr[-400:])
    return result


def http_json(url: str, *, attempts=3, timeout=20):
    error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=HEADERS), timeout=timeout,
            ) as response:
                raw = response.read(3_000_001)
            if not raw or len(raw) > 3_000_000:
                raise ValueError("BAD_RESPONSE_SIZE")
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError("NOT_A_JSON_OBJECT")
            return raw, obj
        except (OSError, TimeoutError, ValueError, urllib.error.HTTPError,
                urllib.error.URLError, json.JSONDecodeError) as exc:
            error = ("HTTP_" + str(exc.code)) if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            if attempt + 1 != attempts:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError("NBA_API_UNAVAILABLE_" + str(error))


def inventory(as_of: dt.date):
    final = {}
    pending = {}
    daily = []
    day = SEASON_START
    while day <= as_of:
        date_string = day.isoformat()
        url = SOURCE_HOST + "/stats/scoreboardv3?" + urllib.parse.urlencode(
            {"GameDate": date_string, "LeagueID": "00"})
        raw, obj = http_json(url, attempts=4)
        games = (obj.get("scoreboard") or {}).get("games")
        if not isinstance(games, list):
            raise ValueError("OFFICIAL_SCOREBOARD_SCHEMA_MISSING_" + date_string)
        game_count = 0
        for game in games:
            gid = str(game.get("gameId", ""))
            if not re.fullmatch(r"00226\d{5}", gid):
                continue
            status = game.get("gameStatus")
            if status not in (1, 2, 3):
                raise ValueError("INVALID_SCOREBOARD_GAME_STATUS_" + gid)
            record = {
                "game_id": gid, "date_us": date_string, "status": status,
                "home": (game.get("homeTeam") or {}).get("teamTricode"),
                "away": (game.get("awayTeam") or {}).get("teamTricode"),
            }
            if not record["home"] or not record["away"] or record["home"] == record["away"]:
                raise ValueError("INCOMPLETE_SCOREBOARD_TEAMS_" + gid)
            if gid in final or gid in pending:
                raise ValueError("DUPLICATE_SCHEDULE_GAME_" + gid)
            (final if status == 3 else pending)[gid] = record
            game_count += 1
        daily.append({
            "us_date": date_string,
            "source_sha256": sha(raw),
            "regular_season_games": game_count,
            "final_games": sum(x.get("gameStatus") == 3
                               for x in games
                               if re.fullmatch(r"00226\d{5}", str(x.get("gameId", "")))),
        })
        day += dt.timedelta(days=1)
    if not final:
        raise ValueError("NO_FINAL_NBA_GAMES_IN_OFFICIAL_SEASON")
    return final, pending, daily


def normalize(gid: str, payload: dict, source_sha: str):
    legacy = (payload.get("payload") or {}).get("defensiveBoxScore")
    if isinstance(legacy, list) and legacy:
        return normalize_legacy(gid, payload, source_sha)
    root = payload.get("boxScoreMatchups")
    if not isinstance(root, dict) or str(root.get("gameId")) != gid:
        raise ValueError("INVALID_MATCHUP_GAME_OR_SCHEMA_" + gid)
    home, away = root.get("homeTeam"), root.get("awayTeam")
    if not all(isinstance(t, dict) and isinstance(t.get("players"), list)
               for t in (home, away)):
        raise ValueError("INVALID_MATCHUP_PLAYER_ROSTER_" + gid)
    if (int(root["homeTeamId"]) != int(home["teamId"])
        or int(root["awayTeamId"]) != int(away["teamId"])
        or int(home["teamId"]) == int(away["teamId"])):
        raise ValueError("INVALID_MATCHUP_TEAM_IDS_" + gid)
    rows, seen = [], set()
    for offense, defense in ((home, away), (away, home)):
        for attacker in offense["players"]:
            oid = attacker.get("personId")
            pairs = attacker.get("matchups")
            if oid is None or not isinstance(pairs, list):
                raise ValueError("INVALID_OFFENSIVE_PLAYER_" + gid)
            for defender in pairs:
                did, st = defender.get("personId"), defender.get("statistics")
                if did is None or did == oid or not isinstance(st, dict):
                    raise ValueError("INVALID_MATCHUP_DEFENDER_" + gid)
                if any(k not in st for k in FIELDS):
                    raise ValueError("MISSING_MATCHUP_STAT_FIELDS_" + gid)
                key = (gid, int(did), int(oid))
                if key in seen:
                    raise ValueError("DUPLICATE_MATCHUP_PAIR_" + gid)
                seen.add(key)
                stamp = st["matchupMinutes"]
                if not isinstance(stamp, str) or not re.fullmatch(r"\d+:\d{2}", stamp):
                    raise ValueError("INVALID_MATCHUP_CLOCK_" + gid)
                m, s = map(int, stamp.split(":"))
                if s > 59 or abs(m*60+s-float(st["matchupMinutesSort"])) > 1.51:
                    raise ValueError("INVALID_MATCHUP_TIME_SECONDS_" + gid)
                if (st["matchupFieldGoalsMade"] > st["matchupFieldGoalsAttempted"] or
                    st["matchupThreePointersMade"] > st["matchupThreePointersAttempted"] or
                    st["matchupFreeThrowsMade"] > st["matchupFreeThrowsAttempted"]):
                    raise ValueError("INVALID_MATCHUP_SHOOTING_" + gid)
                def n(p):
                    return " ".join(x for x in (p.get("firstName"), p.get("familyName")) if x).strip() or p.get("nameI","")
                rows.append({
                    "nba_game_id": gid,
                    "defense_team_id": defense["teamId"],
                    "defense_team_abbr": defense["teamTricode"],
                    "offense_team_id": offense["teamId"],
                    "offense_team_abbr": offense["teamTricode"],
                    "defender_player_id": did,
                    "defender_player_name": n(defender),
                    "offensive_player_id": oid,
                    "offensive_player_name": n(attacker),
                    **{k: st[k] for k in FIELDS},
                    "source": "nba_official_boxscorematchupsv3",
                    "source_response_sha256": source_sha,
                    "source_format": "BoxScoreMatchupsV3",
                    "legacy_player_fg_points": None,
                    "legacy_team_fg_points": None,
                })
    if not rows:
        raise ValueError("OFFICIAL_MATCHUP_ROWS_EMPTY_" + gid)
    rows.sort(key=lambda r: (int(r["defense_team_id"]), int(r["defender_player_id"]),
                             int(r["offensive_player_id"])))
    return rows


def normalize_legacy(gid: str, payload: dict, source_sha: str):
    """Preserve legacy-only fields, never invent missing V3 possession/FT stats."""
    p = payload.get("payload") or {}
    if p.get("gameId") not in (None, gid):
        raise ValueError("WRONG_LEGACY_MATCHUP_GAME_" + gid)
    items = p.get("defensiveBoxScore")
    if not isinstance(items, list) or not items:
        raise ValueError("EMPTY_LEGACY_MATCHUPS_" + gid)
    out, seen = [], set()
    for rec in items:
        if not isinstance(rec, dict):
            raise ValueError("INVALID_LEGACY_MATCHUP_ROW_" + gid)
        needed = ("defTeamId", "defTeamAbbreviation", "offTeamId",
                  "offTeamAbbreviation", "defPlayerId", "offPlayerId",
                  "matchupTime", "fieldGoalMakes", "fieldGoalAttempts",
                  "threePointMakes", "threePointAttempts",
                  "fieldGoalPercentage", "threePointPercentage",
                  "playerPointsOffFieldGoals", "teamPointsOffFieldGoals", "assists")
        if any(k not in rec for k in needed):
            raise ValueError("MISSING_LEGACY_SOURCE_FIELDS_" + gid)
        did, oid = rec["defPlayerId"], rec["offPlayerId"]
        key = (gid, int(did), int(oid))
        if key in seen:
            raise ValueError("DUPLICATE_LEGACY_PAIR_" + gid)
        seen.add(key)
        if int(rec["defTeamId"]) == int(rec["offTeamId"]):
            raise ValueError("LEGACY_SAME_TEAM_" + gid)
        stamp = rec["matchupTime"]
        if not isinstance(stamp, str) or not re.fullmatch(r"\d+:\d{2}", stamp):
            raise ValueError("LEGACY_CLOCK_INVALID_" + gid)
        if (rec["fieldGoalMakes"] > rec["fieldGoalAttempts"]
            or rec["threePointMakes"] > rec["threePointAttempts"]):
            raise ValueError("LEGACY_FIELD_GOAL_COUNTS_INVALID_" + gid)
        row = {k: None for k in COLS}
        row.update({
            "nba_game_id": gid,
            "defense_team_id": rec["defTeamId"],
            "defense_team_abbr": rec["defTeamAbbreviation"],
            "offense_team_id": rec["offTeamId"],
            "offense_team_abbr": rec["offTeamAbbreviation"],
            "defender_player_id": did,
            "defender_player_name": rec.get("defPlayerName"),
            "offensive_player_id": oid,
            "offensive_player_name": rec.get("offPlayerName"),
            "matchupMinutes": stamp,
            # No source-observed fine-grained fractional-possession,
            # switches, total points, free throws or seconds-sort fields.
            "matchupAssists": rec["assists"],
            "matchupFieldGoalsMade": rec["fieldGoalMakes"],
            "matchupFieldGoalsAttempted": rec["fieldGoalAttempts"],
            "matchupFieldGoalsPercentage": rec["fieldGoalPercentage"],
            "matchupThreePointersMade": rec["threePointMakes"],
            "matchupThreePointersAttempted": rec["threePointAttempts"],
            "matchupThreePointersPercentage": rec["threePointPercentage"],
            "legacy_player_fg_points": rec["playerPointsOffFieldGoals"],
            "legacy_team_fg_points": rec["teamPointsOffFieldGoals"],
            "source": "nba_official_defensiveboxscore_legacy",
            "source_response_sha256": source_sha,
            "source_format": "defensiveboxscore_legacy",
        })
        out.append(row)
    out.sort(key=lambda r: (int(r["defense_team_id"]),
                            int(r["defender_player_id"]),
                            int(r["offensive_player_id"])))
    return out


def fetch_one(gid: str, fixture: dict):
    # Prefer full V3; fallback to official legacy only where V3 is empty.
    # Keep each distinct source format and unsupported fields clearly marked.
    errors = []
    for endpoint in ("boxscorematchupsv3", "defensiveboxscore"):
        url = SOURCE_HOST + "/stats/" + endpoint + "?" + urllib.parse.urlencode({"GameID": gid})
        try:
            raw, obj = http_json(url, attempts=4, timeout=19)
            rows = normalize(gid, obj, sha(raw))
            teams = {r["defense_team_abbr"] for r in rows} | {r["offense_team_abbr"] for r in rows}
            if {fixture["home"], fixture["away"]} != teams:
                raise ValueError("MATCHUP_SCOREBOARD_TEAM_DISAGREEMENT_" + gid)
            return gid, {
                "game_id": gid, "source_url": url,
                "source_sha256": sha(raw),
                "source_format": rows[0]["source_format"],
                "raw_base64": base64.b64encode(raw).decode("ascii"),
            }, len(rows), None
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            errors.append(endpoint + "_" + type(exc).__name__ + ":" + str(exc)[:95])
    return gid, None, 0, ";".join(errors)

def load_cache():
    path = WORK / "nba-2026-27-defensive-matchups-raw.jsonl.gz"
    get = gh("release", "download", LATEST_TAG, "--repo", REPO,
             "--pattern", path.name, "--dir", str(WORK), must=False)
    if get.returncode:
        return {}
    cache = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            gid = rec["game_id"]
            raw = base64.b64decode(rec["raw_base64"], validate=True)
            if sha(raw) != rec["source_sha256"]:
                raise ValueError("PREVIOUS_PRIVATE_RAW_SOURCE_SHA_CHANGED_" + gid)
            normalize(gid, json.loads(raw), sha(raw))
            if gid in cache:
                raise ValueError("DUPLICATED_PRIVATE_PRIOR_GAME_" + gid)
            cache[gid] = rec
    print("PRIVATE_PREVIOUS_SOURCE_BACKFILL_CACHE_GAMES", len(cache), flush=True)
    return cache


def write_archive(cache: dict):
    path = WORK / "nba-2026-27-defensive-matchups-raw.jsonl.gz"
    with path.open("wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as g:
            for gid, rec in sorted(cache.items()):
                g.write((json.dumps(rec, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")) + "\n").encode("utf-8"))
    return path


def materialize(cache, finals, pending, dates, errors, end_date):
    rows, per_game = [], []
    for gid in sorted(cache):
        rec = cache[gid]
        original = base64.b64decode(rec["raw_base64"], validate=True)
        if sha(original) != rec["source_sha256"]:
            raise ValueError("SOURCE_SHA_ERROR_" + gid)
        data = json.loads(original)
        normalized = normalize(gid, data, sha(original))
        rows.extend(normalized)
        per_game.append({
            "game_id": gid, "pair_rows": len(normalized),
            "source_sha256": rec["source_sha256"],
            "source_url": rec["source_url"],
        })
    rows.sort(key=lambda r: (r["nba_game_id"], int(r["defense_team_id"]),
                             int(r["defender_player_id"]), int(r["offensive_player_id"])))
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_data = buf.getvalue().encode("utf-8")
    output = WORK / "defender_offender_matchups.csv"
    output.write_bytes(csv_data)
    missing = sorted(set(finals) - set(cache))
    source_formats = {gid: rec.get("source_format", "BoxScoreMatchupsV3")
                      for gid, rec in cache.items()}
    fallback_games = sorted(gid for gid, fmt in source_formats.items()
                            if fmt == "defensiveboxscore_legacy")
    # Never count scheduled/live games as missing final games.
    qa = {
        "schema": "nba-official-matchups-2026-27.full-season.v2",
        "source_endpoint": SOURCE_HOST + "/stats/boxscorematchupsv3?GameID=<game_id>",
        "source_inventory_endpoint": SOURCE_HOST + "/stats/scoreboardv3",
        "season": "2026-27", "season_start_us": SEASON_START.isoformat(),
        "through_us_date": end_date.isoformat(),
        "status": ("COMPLETE_WITH_OFFICIAL_LEGACY_FALLBACK" if fallback_games else "COMPLETE")
                  if not missing else "INCOMPLETE_RETRY_PENDING",
        "official_completed_games": len(finals),
        "official_nonfinal_games": len(pending),
        "source_verified_games": len(per_game),
        "source_missing_final_games": len(missing),
        "missing_final_game_ids": missing,
        "official_matchup_pairs": len(rows),
        "v3_source_games": len(cache) - len(fallback_games),
        "official_legacy_fallback_games": len(fallback_games),
        "official_legacy_fallback_game_ids": fallback_games,
        "legacy_only_fields_null_not_fabricated": True,
        "csv_sha256": sha(csv_data),
        "all_original_responses_retained_in_private_sha_archive": True,
        "original_blueprint_and_xyz_unchanged": True,
        "matchups_not_blueprint_nearest_shot_defender": True,
        "matchups_not_blueprint_two_featured_spotlights": True,
        "no_modeled_matchup_values": True,
        "date_inventory_sha": sha(json.dumps(dates, sort_keys=True,
                                              separators=(",", ":")).encode()),
        "dates": dates, "games": per_game, "failures": errors,
        "live_or_scheduled_game_ids": sorted(pending),
    }
    qa_file = WORK / "matchups_qa.json"
    qa_file.write_text(json.dumps(qa, sort_keys=True, indent=2,
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    return qa, output, qa_file


def publish_release(archive, csv_file, qa_file, manifest):
    hashid = sha(archive.read_bytes())[:12]
    # Immutable evidence snapshot and a rolling latest cache for incremental
    # future games; all assets remain exclusively in PRIVATE 104 Releases.
    snapshot = f"nba-2026-27-matchups-{manifest['through_us_date']}-{hashid}"
    for tag, snapshot_mode in ((snapshot, True), (LATEST_TAG, False)):
        exists = gh("release", "view", tag, "--repo", REPO, must=False).returncode == 0
        if not exists:
            gh("release", "create", tag, "--repo", REPO, "--target", "main",
               "--title", "NBA 2026-27 source-verified defensive matchups"
                          + (" immutable snapshot" if snapshot_mode else " latest"),
               "--notes", "Original NBA BoxScoreMatchupsV3 public-source responses."
                          " Private original SHA-verified data; these are per matchup"
                          " allocations, not physically certified per-shot defender IDs.")
        if not (exists and snapshot_mode):
            gh("release", "upload", tag, str(archive), str(csv_file), str(qa_file),
               "--repo", REPO, "--clobber")
    return snapshot


def put_private_database(csv_file, qa_file, release_tag, qa):
    # One atomic Git tree/commit to PRIVATE 104 with optimistic fast-forward.
    # Avoid cloning this large private repository or relying on blocked private
    # Actions. The release holds all raw source bytes; the CSV is queryable.
    targets = {
        SEASON_PATH + "/defender_offender_matchups.csv": csv_file,
        SEASON_PATH + "/matchups_qa.json": qa_file,
    }
    pointer = WORK / "matchup_release_pointer.json"
    pointer.write_text(json.dumps({
        "schema": "nba-2026-27-matchup-source-pointer.v1",
        "immutable_source_private_release": release_tag,
        "latest_source_private_release": LATEST_TAG,
        "official_completed_games": qa["official_completed_games"],
        "source_verified_games": qa["source_verified_games"],
        "matchup_pair_rows": qa["official_matchup_pairs"],
        "original_archive_private_only": True,
        "status": qa["status"],
        "table_path": SEASON_PATH + "/defender_offender_matchups.csv",
        "qa_path": SEASON_PATH + "/matchups_qa.json",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    targets[SEASON_PATH + "/matchup_release_pointer.json"] = pointer
    blobs = {}
    for path, file_path in targets.items():
        blob = api("repos/" + REPO + "/git/blobs",
                   {"content": file_path.read_text(encoding="utf-8"),
                    "encoding": "utf-8"}, "POST")
        blobs[path] = blob["sha"]
    for attempt in range(4):
        head = api("repos/" + REPO + "/git/ref/heads/main")["object"]["sha"]
        tree_sha = api("repos/" + REPO + "/git/commits/" + head)["tree"]["sha"]
        tree = api("repos/" + REPO + "/git/trees", {
            "base_tree": tree_sha,
            "tree": [{"path": path, "mode": "100644", "type": "blob",
                      "sha": blob} for path, blob in sorted(blobs.items())],
        }, "POST")
        commit = api("repos/" + REPO + "/git/commits", {
            "message": "Ingest official 2026-27 NBA defensive matchups: "
                       + str(qa["source_verified_games"]) + " final games, "
                       + str(qa["official_matchup_pairs"]) + " pair rows",
            "tree": tree["sha"], "parents": [head],
        }, "POST")
        # Avoid force. Recompute tree against latest head on write conflicts.
        try:
            api("repos/" + REPO + "/git/refs/heads/main",
                {"sha": commit["sha"], "force": False}, "PATCH")
            return commit["sha"]
        except RuntimeError:
            if attempt == 3:
                raise
            time.sleep(2)
    raise RuntimeError("PRIVATE_ATOMIC_DATABASE_PUBLISH_FAILED")


def main():
    end = dt.date.fromisoformat(os.environ.get(
        "NBA_MATCHUP_THROUGH_US_DATE",
        dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
    ))
    if end < SEASON_START or end > dt.datetime.now(ZoneInfo("America/New_York")).date():
        raise ValueError("INVALID_FUTURE_OR_PRESEASON_DATE")
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("REQUIRED_PRIVATE_104_RELEASE_TOKEN_NOT_CONNECTED")
    private = api("repos/" + REPO)
    if not private.get("private"):
        raise RuntimeError("EXPECTED_PRIVATE_104_GITHUB_REPOSITORY")
    finals, pending, dates = inventory(end)
    cache = load_cache()
    cache = {gid: rec for gid, rec in cache.items() if gid in finals}
    targets = [(gid, record) for gid, record in sorted(finals.items())
               if gid not in cache]
    print("OFFICIAL_SEASON_INVENTORY",
          json.dumps({"through_us": end.isoformat(), "final": len(finals),
                      "nonfinal": len(pending), "cached": len(cache),
                      "to_fetch": len(targets), "days": len(dates)}, sort_keys=True),
          flush=True)
    failures = []
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda item: fetch_one(*item), targets))
        for gid, source, nrows, error in results:
            if error:
                failures.append({"game_id": gid, "error": error})
            else:
                cache[gid] = source
    archive = write_archive(cache)
    qa, table, qa_file = materialize(cache, finals, pending, dates, failures, end)
    # Fast-fail if most sources were blocked: preserve QA as a local log summary
    # but don't replace a good database with a broadly broken collection.
    if len(cache) < max(1, len(finals)//2):
        raise RuntimeError("SOURCE_BACKFILL_WIDESPREAD_FAILURE_NO_DATABASE_OVERWRITE")
    tag = publish_release(archive, table, qa_file, qa)
    commit = put_private_database(table, qa_file, tag, qa)
    print("PRIVATE_SEASON_MATCHUP_SOURCE_ACCEPTANCE", json.dumps({
        "through_us": qa["through_us_date"],
        "official_completed_games": qa["official_completed_games"],
        "verified_games": qa["source_verified_games"],
        "missing_games": qa["source_missing_final_games"],
        "pair_rows": qa["official_matchup_pairs"],
        "source_archive_sha256": sha(archive.read_bytes()),
        "season_csv_sha256": qa["csv_sha256"],
        "immutable_release": tag,
        "private_104_commit": commit,
        "source_status": qa["status"],
        "official_legacy_fallback_games": qa["official_legacy_fallback_games"],
        "error_types": dict(collections.Counter(
            err["error"].split(":")[0] for err in failures)),
    }, sort_keys=True), flush=True)
    if qa["source_missing_final_games"]:
        # Retries remain scheduled; expose incomplete status rather than
        # falsely claiming the dataset has all completed NBA games.
        print("PARTIAL_SOURCE_COVERAGE_RETRY_REQUIRED", len(failures), flush=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
