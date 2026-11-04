#!/usr/bin/env python3
"""Preserve a publicly distributed NBA Game Pulse ZIP as independently verifiable private-release shards.

This is public-source format handling, not a tracking reconstruction or a certified
on-court identity/possession classifier. Original members are copied byte-for-byte.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

GAME_RE = re.compile(r"(?<![0-9])(00[0-9]{8})(?![0-9])")
TRACKING_SUFFIX = "/tracking.jsonl.gz"
SOURCE_URL = "https://downloads.neilball.org/NBA-2025-26-Available-Tracking.zip"
EXPECTED_PREFIX = "00225"

def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def tracking_qa(archive: zipfile.ZipFile, item: zipfile.ZipInfo, game_id: str) -> dict:
    stats = dict(rows=0, direct_ball_rows=0, provider_ten_ball_rows=0,
                 duplicate_timestamps=0, timestamp_reversals=0, missing_quality_rows=0)
    prior = None
    with archive.open(item) as outer:
        with gzip.GzipFile(fileobj=outer, mode="rb") as unpack:
            for line in unpack:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("game_id") != game_id:
                    raise ValueError("NORMALIZED_GAME_ID_MISMATCH")
                t = row.get("timestamp_ms")
                if not isinstance(t, int):
                    raise ValueError("NORMALIZED_TIMESTAMP_NOT_INTEGER")
                if prior is not None:
                    if t < prior:
                        stats["timestamp_reversals"] += 1
                    elif t == prior:
                        stats["duplicate_timestamps"] += 1
                prior = t
                stats["rows"] += 1
                if row.get("ball") is not None:
                    stats["direct_ball_rows"] += 1
                q = row.get("quality")
                if not isinstance(q, dict):
                    stats["missing_quality_rows"] += 1
                elif q.get("all_ten_and_ball_observed") is True:
                    stats["provider_ten_ball_rows"] += 1
    if stats["timestamp_reversals"]:
        raise ValueError("NONMONOTONIC_NORMALIZED_SOURCE")
    return stats

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-shard-mib", type=int, default=350)
    ap.add_argument("--expected-size", type=int, default=0)
    args = ap.parse_args()
    if args.expected_size and args.archive.stat().st_size != args.expected_size:
        raise ValueError("SOURCE_BYTE_COUNT_CHANGED")
    args.output.mkdir(parents=True, exist_ok=True)
    source_sha = sha(args.archive)
    max_bytes = args.max_shard_mib * 1024 * 1024
    if not 50 * 1024 * 1024 <= max_bytes <= 1500 * 1024 * 1024:
        raise ValueError("INVALID_SHARD_SIZE")
    groups: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    with zipfile.ZipFile(args.archive) as source:
        infos = [x for x in source.infolist() if not x.is_dir()]
        paths = [x.filename for x in infos]
        if len(paths) != len(set(paths)):
            raise ValueError("DUPLICATE_ARCHIVE_MEMBER_NAMES")
        if not infos:
            raise ValueError("EMPTY_ARCHIVE")
        for item in infos:
            if item.filename.startswith("/") or ".." in Path(item.filename).parts or "\\" in item.filename:
                raise ValueError("UNSAFE_SOURCE_MEMBER_NAME")
            m = GAME_RE.search(item.filename)
            game_id = m.group(1) if m else "_collection"
            groups[game_id].append(item)
        tracking_game_ids = {
            game for game, items in groups.items()
            if game != "_collection" and any(x.filename.endswith(TRACKING_SUFFIX) for x in items)
        }
        if not tracking_game_ids:
            raise ValueError("NO_NORMALIZED_GAME_TRACKING_FOUND")
        invalid = [g for g in tracking_game_ids if not g.startswith(EXPECTED_PREFIX)]
        if invalid:
            raise ValueError("NON_2025_26_REGULAR_SEASON_ID_IN_NORMALIZED_TRACKING")
        index = {
            "schema": "igp.public-source-historical-gamepulse-archive.v1",
            "source": SOURCE_URL,
            "source_zip_bytes": args.archive.stat().st_size,
            "source_zip_sha256": source_sha,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "season": "2025-26",
            "not_current_season_full107": True,
            "native_source_observation_policy": "as_supplied_no_interpolation",
            "ten_ball_definition": "publisher_quality_flag_not_independently_identity_certified",
            "physical_possession_boundaries_certified": 0,
            "expected_games_with_tracking": len(tracking_game_ids),
            "games": {},
            "collection_members": [],
            "shards": [],
        }
        shard_num, part_size = 0, 0
        output_zip = None
        output_path = None
        shard_items = 0
        shard_games = []
        copied = set()

        def close_shard() -> None:
            nonlocal output_zip, output_path, part_size, shard_items, shard_games
            if output_zip is None:
                return
            output_zip.close()
            index["shards"].append({
                "name": output_path.name,
                "sha256": sha(output_path),
                "bytes": output_path.stat().st_size,
                "members": shard_items,
                "game_ids": sorted(set(shard_games)),
            })
            output_zip = None
            output_path = None
            part_size = 0
            shard_items = 0
            shard_games = []

        for group_name in sorted(groups):
            members = sorted(groups[group_name], key=lambda x: x.filename)
            group_size = sum(x.file_size + len(x.filename.encode()) + 256 for x in members)
            if group_size > 1700 * 1024 * 1024:
                raise ValueError("GROUP_EXCEEDS_RELEASE_ASSET_LIMIT")
            if output_zip is not None and part_size + group_size > max_bytes:
                close_shard()
            if output_zip is None:
                shard_num += 1
                output_path = args.output / ("nba-2025-26-shard-%03d.zip" % shard_num)
                output_zip = zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True)
            game_meta = {"members": [], "tracking": None, "shard": output_path.name}
            if group_name != "_collection":
                index["games"][group_name] = game_meta
                shard_games.append(group_name)
            for item in members:
                digest = hashlib.sha256()
                with source.open(item, "r") as read_stream:
                    with output_zip.open(item.filename, "w", force_zip64=True) as write_stream:
                        while True:
                            data = read_stream.read(4 * 1024 * 1024)
                            if not data:
                                break
                            digest.update(data)
                            write_stream.write(data)
                copied.add(item.filename)
                row = {"path": item.filename, "bytes": item.file_size,
                       "crc32": "%08x" % item.CRC, "sha256": digest.hexdigest(),
                       "shard": output_path.name}
                if group_name == "_collection":
                    index["collection_members"].append(row)
                else:
                    game_meta["members"].append(row)
                    if item.filename.endswith(TRACKING_SUFFIX):
                        if game_meta["tracking"] is not None:
                            raise ValueError("MULTIPLE_TRACKING_FILES_FOR_GAME")
                        game_meta["tracking"] = tracking_qa(source, item, group_name)
                shard_items += 1
                part_size += item.file_size + len(item.filename.encode()) + 256
        close_shard()
    if copied != set(paths):
        raise ValueError("ARCHIVE_MEMBERS_LOST")
    for game_id in tracking_game_ids:
        t = index["games"][game_id]["tracking"]
        if t is None or t["rows"] < 1:
            raise ValueError("NORMALIZED_GAME_HAS_NO_FRAMES")
    index["total_original_members_copied"] = len(copied)
    index["total_games_indexed"] = len(index["games"])
    index["total_tracking_games_verified"] = len(tracking_game_ids)
    index["total_normalized_rows"] = sum(index["games"][g]["tracking"]["rows"] for g in tracking_game_ids)
    index["total_provider_ten_ball_rows"] = sum(index["games"][g]["tracking"]["provider_ten_ball_rows"] for g in tracking_game_ids)
    index["original_zip_outer_bytes_preserved"] = False
    index["all_original_zip_member_payload_bytes_preserved"] = True
    index["release_state"] = "PREPARED_NOT_YET_UPLOADED"
    output_index = args.output / "nba-2025-26-source-index.json"
    output_index.write_text(json.dumps(index, sort_keys=True, indent=2) + "\n")
    print("IGP_ARCHIVE_L0_MEMBER_SHA_VERIFIED",
          "games", index["total_tracking_games_verified"],
          "frames", index["total_normalized_rows"],
          "shards", len(index["shards"]),
          "members", len(copied),
          "source_sha256", source_sha)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
