#!/usr/bin/env python3
"""Deterministic QA: historical L0 vs Full107-native, shot-quality and defender shards.

This script accepts only source-index metadata and private per-shard QA receipts.
It deliberately cannot inspect licensed player XYZ or certify physical accuracy.
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import re

EXPECTED_NATIVE_FRAMES = 19_440_900
EXPECTED_TRACKING_GAMES = 666
SHARD_RX = re.compile(r"shard-(\d{3})-qa\.json$")
SCHEMA = "igp.historical-full107-cross-season-acceptance.v1"

def inspect(root: Path) -> dict:
    index = json.loads((root / "source" / "nba-2025-26-source-index.json").read_text())
    source = {x["name"]: x for x in index["shards"]}
    if len(source) != 15:
        raise ValueError("SOURCE_SHARD_COUNT_DRIFT")
    expected = {gid: g for gid, g in index["games"].items() if g.get("tracking")}
    if len(expected) != EXPECTED_TRACKING_GAMES:
        raise ValueError("SOURCE_TRACKING_GAME_COUNT_DRIFT")
    if index["total_tracking_games_verified"] != EXPECTED_TRACKING_GAMES:
        raise ValueError("SOURCE_INDEX_POPULATION_CONTRADICTION")
    if sum(int(g["tracking"]["rows"]) for g in expected.values()) != EXPECTED_NATIVE_FRAMES:
        raise ValueError("SOURCE_NATIVE_ROW_COUNT_DRIFT")

    receipt = {
        "schema": SCHEMA, "season": "2025-26",
        "source_games": len(expected), "source_shards": len(source),
        "source_native_frames": EXPECTED_NATIVE_FRAMES,
        "source_original_immutable": True,
        "source_lineup_grade": "PROVISIONAL_NOT_OFFICIAL",
        "physical_accuracy_certified": False,
        "status": "NOT_PROMOTED",
        "layers": {},
    }

    patterns = {
        "native": ("native", "full107-native-nba-2025-26-shard-*-qa.json"),
        "xfg": ("xfg", "nba-xfg-nba-2025-26-shard-*-qa.json"),
        "defender": ("defender", "defender-xyz-nba-2025-26-shard-*-qa.json")
    }
    records = {}
    for layer, (folder, pattern) in patterns.items():
        found = {}
        games = set()
        sums = collections.Counter()
        gaps = 0
        for path in sorted((root / folder).glob(pattern)):
            m = SHARD_RX.search(path.name)
            if not m:
                raise ValueError("UNEXPECTED_SHARD_QA_NAME:" + path.name)
            shard_number = m.group(1)
            shard_name = f"nba-2025-26-shard-{shard_number}.zip"
            if shard_name not in source or shard_number in found:
                raise ValueError("UNEXPECTED_OR_DUPLICATE_SHARD:" + path.name)
            q = json.loads(path.read_text())
            if q.get("source_shard_sha256") != source[shard_name]["sha256"]:
                raise ValueError("SHA_MISMATCH:" + path.name)
            if layer == "native":
                if q.get("original_source_immutable") is not True:
                    raise ValueError("SOURCE_MUTATION_ASSERTION_MISSING")
                if q.get("model_module") != "igp_native_scene_model_v2":
                    raise ValueError("NOT_FULL107_NATIVE")
                if q.get("qa_grade") != "HISTORICAL_NATIVE_FULL107_RESEARCH_SOURCE_PROVISIONAL":
                    raise ValueError("UNKNOWN_NATIVE_RESEARCH_GRADE")
                if any(item.get("source_lineup_grade") !=
                       "SOURCE_PROVISIONAL_NOT_INDEPENDENT_OFFICIAL_TEN"
                       for item in q.get("per_game", {}).values()):
                    raise ValueError("UNKNOWN_PER_GAME_LINEUP_EVIDENCE_GRADE")
            gp = q.get("per_game", {})
            allowed = set(source[shard_name]["game_ids"]) & set(expected)
            if len(gp) != q.get("games") or not set(gp) <= allowed:
                raise ValueError("GAME_SCOPE_DRIFT:" + path.name)
            if games & set(gp):
                raise ValueError("DUPLICATE_GAME_ACROSS_SHARDS:" + path.name)
            games.update(gp)
            c = q.get("counts", {})
            if layer == "native":
                for gid, item in gp.items():
                    expected_frames = int(expected[gid]["tracking"]["rows"])
                    if item.get("native_source_denominator") != expected_frames:
                        raise ValueError("PER_GAME_FRAME_CENSUS_DRIFT:" + gid)
                    if item.get("counts", {}).get("source_native_frames") != expected_frames:
                        raise ValueError("PER_GAME_SOURCE_ROWS_DRIFT:" + gid)
                if sum(item["counts"]["source_native_frames"] for item in gp.values()) != c.get("source_native_frames"):
                    raise ValueError("SHARD_NATIVE_TOTAL_CONFLICT:" + path.name)
                if c.get("native_engine_complete_ten_ball", 0) > c.get("source_native_frames", 0):
                    raise ValueError("NATIVE_SCENE_COUNT_EXCEEDS_SOURCE")
            elif layer == "xfg":
                if q.get("games") != len(gp):
                    raise ValueError("XFG_GAME_COUNT_CONTRADICTION")
                if not q.get("shot_rows_sha256"):
                    raise ValueError("XFG_SHOT_SOURCE_HASH_ABSENT")
                gaps += len(q.get("failed_player_games") or [])
            elif layer == "defender":
                if q.get("source_direct_vs_reconstructed") != "DIRECT_ARCHIVED_ONLY":
                    raise ValueError("DEFENDER_SOURCE_GRADE_CHANGED_WITHOUT_VALIDATION")
                if not q.get("shot_rows_sha256"):
                    raise ValueError("DEFENDER_SHOT_HASH_ABSENT")
                if q.get("primary_defender_is_not_causal_effect") is not True:
                    raise ValueError("UNVERIFIED_CAUSAL_DEFENDER_CLAIM")
            for key, value in c.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    sums[key] += value
            found[shard_number] = q
        present = sorted(found)
        missing = [f"{n:03d}" for n in range(1, 16) if f"{n:03d}" not in found]
        all_games = not missing and games == set(expected)
        receipt["layers"][layer] = {
            "shards_saved": len(present), "shards_missing": missing,
            "games_with_qa": len(games),
            "full_source_game_coverage": all_games,
            "counts": dict(sorted(sums.items())),
        }
        if layer == "xfg":
            receipt["layers"][layer]["failed_source_shooter_game_requests"] = gaps
        records[layer] = found

    aligned, misaligned = [], []
    for n, d in sorted(records["defender"].items()):
        x = records["xfg"].get(n)
        if x is None:
            continue
        if d["shot_rows_sha256"] != x["shot_rows_sha256"] or d["source_shard_sha256"] != x["source_shard_sha256"]:
            # A known one-game historical defender pilot (e.g. shard 001)
            # cannot be represented as a complete source-matched shard.
            # Report it without suppressing the other independently valid layers.
            misaligned.append(n)
            continue
        if d.get("counts", {}).get("shot_rows", 0) > x.get("counts", {}).get("public_shot_rows", 0):
            raise ValueError("DEFENDER_SHOT_COUNT_EXCEEDS_SOURCE:" + n)
        aligned.append(n)
    receipt["cross_layer_source_aligned_defender_shards"] = len(aligned)
    receipt["cross_layer_defender_source_ready_for_full_reduction"] = len(aligned) == 15
    receipt["cross_layer_mismatched_defender_shards"] = misaligned
    a, b, c = (receipt["layers"][k] for k in ("native", "xfg", "defender"))
    receipt["all_archive_shards_reconstructed"] = a["full_source_game_coverage"] and a["counts"].get("source_native_frames") == EXPECTED_NATIVE_FRAMES
    receipt["all_xfg_source_shards_accounted_for"] = b["full_source_game_coverage"]
    receipt["all_defender_source_shards_accounted_for"] = c["full_source_game_coverage"] and len(aligned) == 15
    receipt["status"] = (
        "SOURCE_AND_DERIVED_COHORT_RECONCILED_RESEARCH_ONLY"
        if all((receipt["all_archive_shards_reconstructed"], receipt["all_xfg_source_shards_accounted_for"], receipt["all_defender_source_shards_accounted_for"]))
        else "PARTIAL_NOT_PROMOTED"
    )
    receipt["production_acceptance_blockers"] = (
        ["Independent masked player XY/ball 3D holdouts not certified",
         "Source-provisional historical lineups not independently official-certified",
         "Historical defender proxy is not a Blueprint causal contest label"]
        + ([f"Unresolved published-xFG shooter-game requests: {b['failed_source_shooter_game_requests']}"]
           if b.get("failed_source_shooter_game_requests") else [])
    )
    return receipt

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = inspect(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    summary = {
        "status": result["status"],
        "native_shards": result["layers"]["native"]["shards_saved"],
        "native_games": result["layers"]["native"]["games_with_qa"],
        "native_frames": result["layers"]["native"]["counts"].get("source_native_frames", 0),
        "xfg_shards": result["layers"]["xfg"]["shards_saved"],
        "defender_shards": result["layers"]["defender"]["shards_saved"],
        "source_aligned_defender_shards": result["cross_layer_source_aligned_defender_shards"],
        "missing_xfg_shooter_game_requests": result["layers"]["xfg"]["failed_source_shooter_game_requests"],
        "production_accepted": False
    }
    print("IGP_HISTORICAL_FULL107_CROSS_SEASON_RECEIPT", json.dumps(summary, sort_keys=True))

if __name__ == "__main__":
    main()
