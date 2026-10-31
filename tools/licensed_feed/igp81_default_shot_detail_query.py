#!/usr/bin/env python3
"""SHA-verified official NBA shot detail query across 81 preserved games.

Original SDK, Blueprint, frozen 56 shot ledgers and NBA PBP remain immutable.
A complete FGA row may legitimately have null provider biomechanics/Blueprint.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json
from pathlib import Path

BASE=Path("gamepulse/fusion")
INDEX=BASE/"materialized/igp_2026_27_unified_season_v3/shot_biomechanics_all81_v1/index.json"
REG=BASE/"qa/igp_v32/igp81_unified_native_possession_tracking_registry_run_41231284682.json"
RECON=BASE/"qa/igp_v32/igp81_official_pbp_blueprint_semantic_reconciliation_v1.json"
QA=BASE/"qa/igp_v32/igp81_shot_detail_default_route_81game_qa_v1.json"
def require(ok,msg):
    if not ok:raise ValueError(msg)
def load(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect(root,gid,idx):
    require(gid in idx["games"],"SHOT_GAME_NOT_IN_81:"+gid)
    meta=idx["games"][gid]
    path=root/meta["shot_ledger_path"]
    require(path.is_file() and digest(path)==meta["shot_ledger_sha256"],
            "ORIGINAL_OFFICIAL_FGA_LEDGER_SHA_CHANGED:"+gid)
    rows=[json.loads(x) for x in gzip.decompress(path.read_bytes()).splitlines() if x.strip()]
    require(len(rows)==meta["official_FGA"],"ORIGINAL_FGA_TOTAL_CHANGED:"+gid)
    stats=collections.Counter();seen=set()
    for row in rows:
        aid=row.get("nba_action_number")
        require(type(aid)==int and aid not in seen and row.get("game_id")==gid,
                "FGA_ACTION_NOT_UNIQUE:"+gid)
        seen.add(aid)
        action=row.get("nba_official_shot_event",{})
        require(action.get("nba_action_number")==aid
                and action.get("action_type") in ("2pt","3pt"),
                "PBP_CANONICAL_FGA_MISMATCH:"+gid)
        require(row.get("nba_pbp_normalized_source_sha256")==meta["official_PBP_SHA256"],
                "PBP_FGA_LEDGER_ORIGINAL_SHA_MISMATCH:"+gid)
        stats["blueprint"]+=int(row.get("published_blueprint") is not None)
        stats["advanced"]+=int(row.get("published_advanced_companion") is not None)
        stats["xfg"]+=int(row.get("best_published_xfg_probability") is not None)
        require(row.get("actual_shot_release_UTC_independently_verified") is False and
          row.get("original_29_joint_60hz_pose_trajectories_available") is False,
          "NOT_VIDEO_CERTIFIED_OR_NOT_RAW_29JOINT:"+gid)
    expected=meta["shot_identity_join_counts"]
    require(stats["blueprint"]==expected.get("blueprint_matched",0) and
            stats["advanced"]==expected.get("advanced_matched",0) and
            stats["xfg"]==expected.get("any_published_xfg",0),
            "SOURCE_SHOT_FEATURE_COUNT_MISMATCH:"+gid)
    return rows,dict(stats)

def query(root,game_id,action_number=None,offset=0,limit=20):
    root=Path(root)
    require(type(game_id)==str and len(game_id)==10 and game_id.isdigit(),
            "EXACT_GAME_ID_REQUIRED")
    require((action_number is None or (type(action_number)==int and action_number>0))
            and type(offset)==int and 0<=offset and type(limit)==int and 1<=limit<=100,
            "BOUNDED_OFFICIAL_SHOT_QUERY_REQUIRED")
    index=load(root/INDEX)
    require(index.get("official_games")==81 and len(index.get("games",{}))==81,
            "NOT_81_GAME_SOURCE_INDEX")
    rows,stats=inspect(root,game_id,index)
    if action_number is not None:
        rows=[r for r in rows if r["nba_action_number"]==action_number]
        require(len(rows)==1,"OFFICIAL_FGA_ACTION_NOT_FOUND")
    return {"schema":"igp81.default-engine-source-graded-official-FGA-detail.v1",
      "game_id":game_id,"source_detail_layer":str(INDEX),
      "tracking_engine_id":"IGP32_P2B_GUARDED_NBA81_FULL_SOURCE_QA_10HZ_20261101",
      "official_fga_game":index["games"][game_id]["official_FGA"],
      "source_feature_counts":stats,
      "selected":len(rows),"offset":offset,"limit":limit,
      "rows":rows[offset:offset+limit],
      "source_missing_features_null_not_synthesized":True,
      "source_29_joint_pose_certified":False,
      "physical_release_video_certified":False}

def audit(root):
    root=Path(root);index=load(root/INDEX);reg=load(root/REG);recon=load(root/RECON)
    require(index.get("official_games")==81 and reg["counts"]["games"]==81
            and len(index["games"])==81 and set(index["games"])==set(reg["games"]),
            "81_GAME_REGISTRY_LEDGER_SET_DRIFT")
    require(recon.get("ten_new_games_official_action_sequences_and_times_identical") is True
            and recon.get("prior_blueprint_9221_accepted_shot_records_match_current") is True,
            "PBP_OR_BLUEPRINT_RECONCILIATION_NOT_ACCEPTED")
    totals=collections.Counter();rows={}
    for gid in sorted(index["games"]):
        official,features=inspect(root,gid,index)
        row={"official_FGA":len(official),**features,
          "original_ledger_sha256":index["games"][gid]["shot_ledger_sha256"],
          "source_grade":index["games"][gid]["source_grade"]}
        rows[gid]=row
        totals["official_fga"]+=len(official)
        totals.update(features)
        print("IGP81_SHOT_SOURCE_AUDIT",gid,len(official),features["advanced"],flush=True)
    for k,v in {"official_fga":"official_fga","blueprint":"blueprint_matched",
                "advanced":"advanced_matched","xfg":"any_published_xfg"}.items():
        require(totals[k]==index["totals"][v],"81_GAME_SHOT_AGGREGATE_MISMATCH:"+k)
    out={"schema":"igp81.default-query-81-game-shot-source-integrity.v1",
       "game_count":81,"shot_index_path":str(INDEX),
       "shot_index_sha256":digest(root/INDEX),
       "official_native81_registry_sha256":digest(root/REG),
       "original_56_shot_ledgers_unchanged":True,
       "additive_25_shot_ledgers":25,
       "missing_features_preserved_as_null":True,
       "independent_video_accuracy_certified":False,
       "raw_29_joint_60hz_pose_certified":False,
       "totals":dict(totals),"games":rows}
    path=root/QA;path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode()
    if path.exists():require(path.read_bytes()==raw,"SHA_QA_RECEIPT_CHANGED")
    else:path.write_bytes(raw)
    print("IGP81_FULL_SHOT_QUERY_QA_ACCEPTED",json.dumps(out["totals"],sort_keys=True),flush=True)
    return out
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--audit",action="store_true")
    p.add_argument("--game-id")
    p.add_argument("--action-number",type=int)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--limit",type=int,default=20)
    a=p.parse_args()
    print(json.dumps(audit(a.root) if a.audit else
         query(a.root,a.game_id,a.action_number,a.offset,a.limit),sort_keys=True))
