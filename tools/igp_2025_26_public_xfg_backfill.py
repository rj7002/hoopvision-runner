#!/usr/bin/env python3
"""Recover the NBA's public 2025-26 shot-quality source for archived game IDs.

This source-only utility does not assign defenders or reconstruct positions.
Raw response rows and detailed QA are written to a private destination by the
calling workflow; only aggregate counts may be logged publicly.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import io
import json
import math
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

URL = "https://stats.gleague.nba.com/stats/shotqualityvideologs"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
}


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def shooter_manifest(archive: zipfile.ZipFile, game: dict) -> tuple[dict[str, int], int, set[tuple[int, str]]]:
    member = next((m for m in game["members"] if m["path"].endswith("/stats.jsonl.gz")), None)
    if member is None:
        raise ValueError("STATS_SOURCE_MISSING")
    # The compressed original member, not a reconstructed stats snapshot, is verified.
    blob = archive.read(member["path"])
    if hashlib.sha256(blob).hexdigest() != member["sha256"]:
        raise ValueError("STATS_MEMBER_SHA_MISMATCH")
    fga: dict[str, int] = {}
    pbp = 0
    pbp_keys: set[tuple[int, str]] = set()
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            event = str(row.get("event") or "")
            if event == "PlayByPlay#show":
                pbp += 1
                md = row.get("metadata") or {}
                action = md.get("id")
                actor = md.get("personId")
                if str(action or "").isdigit() and str(actor or "").isdigit():
                    pbp_keys.add((int(action), str(actor)))
            if not event.startswith("PlayerStats") or not event.endswith("#show"):
                continue
            md = row.get("metadata") or {}
            pid = md.get("personId")
            if not str(pid or "").isdigit():
                continue
            try:
                count = int(md.get("fga") or 0)
            except (ValueError, TypeError):
                continue
            if count > fga.get(str(pid), 0):
                fga[str(pid)] = count
    if not fga or not pbp:
        raise ValueError("ARCHIVE_SHOOTER_MANIFEST_EMPTY")
    return {p: n for p, n in fga.items() if n > 0}, pbp, pbp_keys


def fetch_pair(gid: str, pid: str, attempts: int = 5) -> tuple[str, str, dict | None, str | None]:
    query = urllib.parse.urlencode({"GameID": gid, "PlayerID": pid})
    last_error = "UNKNOWN"
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(URL + "?" + query, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=35) as response:
                if response.status != 200:
                    raise ValueError("HTTP_STATUS")
                data = json.load(response)
            if (not isinstance(data, dict) or str(data.get("gameId") or "").zfill(10) != gid
                    or str(data.get("playerId")) != pid or not isinstance(data.get("shotList"), list)):
                raise ValueError("SOURCE_IDENTITY_OR_SHOTLIST_MISMATCH")
            return gid, pid, data, None
        except urllib.error.HTTPError as exc:
            last_error = "HTTP_" + str(exc.code)
        except (urllib.error.URLError, TimeoutError):
            last_error = "NETWORK_TIMEOUT_OR_URL"
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(min(8.0, 0.7 * 2**attempt))
    return gid, pid, None, last_error


def run(index_path: pathlib.Path, shard_path: pathlib.Path, out: pathlib.Path,
        workers: int, max_games: int = 0) -> dict:
    index = json.loads(index_path.read_text())
    if index["source_zip_sha256"] != "2450b2fafb66698b39a89592c6ac3767c7ba0c3e4581b1a65042041e0f7ea0b0":
        raise ValueError("HISTORICAL_ARCHIVE_SOURCE_CHANGED")
    shard = next((s for s in index["shards"] if s["name"] == shard_path.name), None)
    if shard is None or shard_path.stat().st_size != shard["bytes"] or digest(shard_path) != shard["sha256"]:
        raise ValueError("HISTORICAL_SHARD_SOURCE_CHANGED")
    gids = [g for g in shard["game_ids"] if index["games"][g]["tracking"]]
    if max_games:
        gids = gids[:max_games]
    if not gids:
        raise ValueError("NO_TRACKING_GAMES_IN_SHARD")
    pergame: dict[str, dict] = {}
    pbp_identity: dict[str, set[tuple[int, str]]] = {}
    with zipfile.ZipFile(shard_path) as archive:
        for gid in gids:
            players, pbp, keys = shooter_manifest(archive, index["games"][gid])
            pergame[gid] = {"archived_pbp_events": pbp, "manifest_player_fga": players,
                            "tracking_rows": index["games"][gid]["tracking"]["rows"]}
            pbp_identity[gid] = keys
    pairs = [(g, p) for g in gids for p in sorted(pergame[g]["manifest_player_fga"], key=int)]
    result: list[tuple[str, str, dict | None, str | None]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for item in pool.map(lambda x: fetch_pair(*x), pairs):
            result.append(item)
    shots = []
    failed = []
    counts = collections.Counter()
    observed_keys = set()
    for gid, pid, response, error in result:
        if response is None:
            failed.append({"game_id": gid, "player_id": pid, "error_class": error})
            continue
        entries = response["shotList"]
        reported = response.get("shots")
        if isinstance(reported, (int, float)) and reported < len(entries):
            raise ValueError("PUBLIC_SHOTLIST_EXCEEDS_REPORTED_FGA")
        counts["successful_player_games"] += 1
        counts["public_shot_rows"] += len(entries)
        pergame[gid].setdefault("source_player_games", 0)
        pergame[gid]["source_player_games"] += 1
        pergame[gid].setdefault("published_shot_rows", 0)
        pergame[gid]["published_shot_rows"] += len(entries)
        for shot in entries:
            if not isinstance(shot, dict):
                raise ValueError("PUBLIC_SHOT_ROW_INVALID")
            event = shot.get("eventNum")
            sid = str(shot.get("playerId") or pid)
            if not str(event or "").isdigit() or sid != pid:
                raise ValueError("PUBLIC_SHOT_IDENTITY_DRIFT")
            key = (gid, int(event), pid)
            if key in observed_keys:
                raise ValueError("PUBLIC_SHOT_EVENT_DUPLICATE")
            observed_keys.add(key)
            if (int(event), pid) in pbp_identity[gid]:
                counts["exact_archived_pbp_actor_action"] += 1
                pergame[gid].setdefault("exact_archived_pbp_actor_action", 0)
                pergame[gid]["exact_archived_pbp_actor_action"] += 1
            quality = shot.get("shotQuality")
            try:
                q = float(quality)
            except (TypeError, ValueError):
                q = math.nan
            if math.isfinite(q) and 0 <= q <= 1:
                counts["nonnull_xfg"] += 1
            shots.append({"game_id": gid, "player_id": int(pid), "event_num": int(event),
                          "source_shot": shot, "source_player_game": {
                              "shots": reported, "avgShotQuality": response.get("avgShotQuality"),
                              "avgDefenderBallDistance": response.get("avgDefenderBallDistance")}})
    out.mkdir(parents=True, exist_ok=True)
    shot_path = out / ("nba-xfg-" + shard_path.stem + ".jsonl.gz")
    with shot_path.open("wb") as sink:
        with gzip.GzipFile(fileobj=sink, mode="wb", mtime=0, filename="") as stream:
            for row in sorted(shots, key=lambda r: (r["game_id"], r["event_num"], r["player_id"])):
                stream.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
    qa = {"schema": "igp.2025-26.public-nba-xfg-shard.v1", "source": URL,
          "source_index_sha256": digest(index_path), "source_shard_sha256": digest(shard_path),
          "games": len(gids), "game_ids": gids, "player_game_requests": len(pairs),
          "counts": dict(counts), "failed_player_games": failed, "per_game": pergame,
          "shot_rows_path": shot_path.name, "shot_rows_sha256": digest(shot_path),
          "source_shot_quality_not_defender_causal_effect": True,
          "source_player_game_defender_distance_not_shot_level": True}
    qa_path = out / ("nba-xfg-" + shard_path.stem + "-qa.json")
    qa_path.write_text(json.dumps(qa, sort_keys=True, indent=2) + "\n")
    return qa


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=pathlib.Path, required=True)
    ap.add_argument("--shard", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-games", type=int, default=0)
    args = ap.parse_args()
    if not 1 <= args.workers <= 3 or not 0 <= args.max_games <= 677:
        raise SystemExit("BOUNDED_PUBLIC_SOURCE_WORKLOAD_REQUIRED")
    qa = run(args.index, args.shard, args.out, args.workers, args.max_games)
    print("IGP_HISTORICAL_XFG_SOURCE_SHARD", json.dumps({"games": qa["games"],
          "requests": qa["player_game_requests"], "successful": qa["counts"].get("successful_player_games", 0),
          "shot_rows": qa["counts"].get("public_shot_rows", 0),
          "exact_archived_pbp_actor_action": qa["counts"].get("exact_archived_pbp_actor_action", 0),
          "nonnull_xfg": qa["counts"].get("nonnull_xfg", 0),
          "failures": len(qa["failed_player_games"])}, sort_keys=True))
