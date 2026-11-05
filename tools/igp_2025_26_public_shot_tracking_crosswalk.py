#!/usr/bin/env python3
"""Source-preserving event-key and UTC lookup across public historical NBA feeds.

No inferred positions, defender labels, release times or physical possessions.
All shot-level rows and source pointers are retained only in private storage.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import gzip
import hashlib
import io
import json
import pathlib
import zipfile


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda: fp.read(4 * 1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def gzlines(blob: bytes):
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as fp:
        for line in fp:
            if line.strip():
                yield json.loads(line)


def archive_member(archive: zipfile.ZipFile, game: dict, suffix: str) -> bytes:
    member = next((m for m in game["members"] if m["path"].endswith("/" + suffix)), None)
    if member is None:
        raise ValueError("ARCHIVE_MEMBER_MISSING:" + suffix)
    blob = archive.read(member["path"])
    if hashlib.sha256(blob).hexdigest() != member["sha256"]:
        raise ValueError("ARCHIVE_MEMBER_SHA_DRIFT:" + suffix)
    return blob


def source_pbp(archive: zipfile.ZipFile, game: dict):
    actions = {}
    for row in gzlines(archive_member(archive, game, "stats.jsonl.gz")):
        if row.get("event") != "PlayByPlay#show":
            continue
        md = row.get("metadata") or {}
        action = md.get("id")
        player = md.get("personId")
        if not str(action or "").isdigit() or not str(player or "").isdigit():
            continue
        key = (int(action), int(player))
        # Repeated source event observations are expected. The latest observed
        # source revision wins, while divergent values remain a QA count.
        actions[key] = row
    return actions


def source_nearest_frames(archive: zipfile.ZipFile, game: dict,
                          targets: list[int | None]) -> dict[int, dict]:
    valid = sorted((t, i) for i, t in enumerate(targets) if isinstance(t, int) and t > 0)
    if not valid:
        return {}
    times = [t for t, _ in valid]
    closest: dict[int, tuple[tuple[int, int], dict]] = {}
    for row in gzlines(archive_member(archive, game, "tracking.jsonl.gz")):
        t = row.get("timestamp_ms")
        if type(t) is not int:
            continue
        at = bisect.bisect_left(times, t)
        for k in (at - 1, at):
            if not 0 <= k < len(valid):
                continue
            shot_t, i = valid[k]
            delta = t - shot_t
            if abs(delta) > 2000:
                continue
            grade = row.get("quality") or {}
            candidate = {
                "source_frame_timestamp_ms": t,
                "delta_from_pbp_event_ms": delta,
                "source_frame_quality": grade,
                "observed_home_players": len(row.get("home_players") or []),
                "observed_away_players": len(row.get("away_players") or []),
                "original_ball_present": row.get("ball") is not None,
                "original_tracking_pointer_not_shot_release": True,
            }
            rank = (abs(delta), t)
            if i not in closest or rank < closest[i][0]:
                closest[i] = (rank, candidate)
    return {i: v[1] for i, v in closest.items()}


def run(index_path: pathlib.Path, source_path: pathlib.Path, shots_path: pathlib.Path,
        shot_qa_path: pathlib.Path, out: pathlib.Path):
    index = json.loads(index_path.read_text())
    source_shard = next((x for x in index["shards"] if x["name"] == source_path.name), None)
    assert source_shard and sha(source_path) == source_shard["sha256"]
    shot_qa = json.loads(shot_qa_path.read_text())
    assert shot_qa["source_shard_sha256"] == source_shard["sha256"]
    assert shot_qa["shot_rows_sha256"] == sha(shots_path)
    by_game = collections.defaultdict(list)
    with gzip.open(shots_path, "rt") as fp:
        for line in fp:
            if line.strip():
                r = json.loads(line)
                assert r["game_id"] in source_shard["game_ids"]
                by_game[r["game_id"]].append(r)
    qa = collections.Counter()
    pergame = {}
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / ("shot-tracking-" + source_path.stem + ".jsonl.gz")
    with zipfile.ZipFile(source_path) as archive, ledger_path.open("wb") as sink:
        with gzip.GzipFile(fileobj=sink, mode="wb", mtime=0, filename="") as compressed:
            for gid in sorted(g for g in source_shard["game_ids"] if index["games"][g]["tracking"]):
                game = index["games"][gid]
                source_actions = source_pbp(archive, game)
                shots = by_game[gid]
                pbp_rows = [source_actions.get((r["event_num"], r["player_id"])) for r in shots]
                times = [r.get("timestamp") if r else None for r in pbp_rows]
                frames = source_nearest_frames(archive, game, times)
                counts = collections.Counter()
                for i, xfg in enumerate(shots):
                    pbp = pbp_rows[i]
                    frame = frames.get(i)
                    counts["shot_rows"] += 1
                    counts["exact_pbp_identity"] += int(pbp is not None)
                    counts["source_frame_within_250ms"] += int(frame is not None and abs(frame["delta_from_pbp_event_ms"]) <= 250)
                    counts["source_frame_within_1000ms"] += int(frame is not None and abs(frame["delta_from_pbp_event_ms"]) <= 1000)
                    counts["source_frame_provider_ten_ball_250ms"] += int(
                        frame is not None and abs(frame["delta_from_pbp_event_ms"]) <= 250
                        and frame["source_frame_quality"].get("all_ten_and_ball_observed") is True)
                    result = {
                        "game_id": gid,
                        "event_num": xfg["event_num"],
                        "shooter_id": xfg["player_id"],
                        "source_nba_shot_quality": xfg["source_shot"],
                        "source_nba_player_game_context": xfg["source_player_game"],
                        "archived_stats_pbp_event": pbp,
                        "original_nearest_tracking_source_pointer": frame,
                        "original_tracking_shard": source_path.name,
                        "event_clock_not_release_time": True,
                        "defender_identity_not_assigned": True,
                    }
                    compressed.write((json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode())
                qa.update(counts)
                pergame[gid] = dict(counts)
    receipt = {
        "schema": "igp.historical-xfg-archived-tracking-source-crosswalk.v1",
        "source_shard_sha256": source_shard["sha256"],
        "xfg_shot_rows_sha256": shot_qa["shot_rows_sha256"],
        "ledger_sha256": sha(ledger_path),
        "ledger_name": ledger_path.name,
        "games": len(pergame),
        "counts": dict(qa),
        "per_game": pergame,
        "source_event_clock_not_shot_release": True,
        "defender_identity_not_assigned": True,
    }
    qa_path = out / ("shot-tracking-" + source_path.stem + "-qa.json")
    qa_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print("HISTORICAL_SHOT_TRACKING_SOURCE_CROSSWALK", json.dumps({
        "games": receipt["games"], "counts": receipt["counts"]}, sort_keys=True))
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=pathlib.Path, required=True)
    p.add_argument("--source-shard", type=pathlib.Path, required=True)
    p.add_argument("--xfg-shots", type=pathlib.Path, required=True)
    p.add_argument("--xfg-qa", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    a = p.parse_args()
    run(a.index, a.source_shard, a.xfg_shots, a.xfg_qa, a.out)
