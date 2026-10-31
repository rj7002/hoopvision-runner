#!/usr/bin/env python3
"""81-game original-source-grade detail-layer release (no licensed data on public runner).
Reuses accepted 56-game shot partitions unchanged; creates additive 25-game
official-FGA + NBA Blueprint + original SDK ShotDetails ledgers. Full raw
Blueprint and companion event responses remain at their immutable source paths.
No raw 29-joint pose, physical release timestamp, exact position or custody
is inferred from aggregate provider features.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json
from pathlib import Path

BASE=Path("gamepulse/fusion")
REG=BASE/"qa/igp_v32/igp81_unified_native_possession_tracking_registry_run_41231284682.json"
OLD=BASE/"qa/igp_progress_20261029/igp_all56_advanced_companion_biomechanics_v2.json"
OLD_BP=BASE/"qa/igp_progress_20261029/igp_blueprint_official_56_source_qa.json"
OUT=BASE/"materialized/igp_2026_27_unified_season_v3/shot_biomechanics_all81_v1"
BP=Path("data/extensions/nba_blueprint_2026_27/games")
EV=BASE/"evidence"
OLD_QA=BASE/"qa/igp_progress_20261029"

def check(ok,msg):
    if not ok: raise ValueError(msg)
def load(p): return json.loads(p.read_bytes())
def digest(raw): return hashlib.sha256(raw).hexdigest()
def filehash(p): return digest(p.read_bytes())
def write_once(p,raw):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():check(p.read_bytes()==raw,"EXISTING_DETAILED_LAYER_SHA_DRIFT:"+str(p))
    else:p.write_bytes(raw)
def jsonbytes(obj):return (json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()
def gziprows(rows):
    import io
    b=io.BytesIO()
    with gzip.GzipFile(fileobj=b,mode="wb",filename="",mtime=0,compresslevel=9) as o:
        for row in rows:
            o.write((json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode())
    return b.getvalue()
def cint(v):
    if type(v)==int and v>0:return v
    if isinstance(v,str) and v.isdecimal() and int(v)>0:return int(v)
    return None
def deep_metadata(e):
    queue=[e];scanned=0
    while queue and scanned<48:
        d=queue.pop(0);scanned+=1
        if not isinstance(d,dict):continue
        if all(x in d for x in ("playId","playerId","expFieldGoalPct")) and (
                isinstance(d.get("features"),dict) or "shotReleaseInfo" in d):return d
        for name in ("metadata","payload","data","message","event"):
            v=d.get(name)
            if isinstance(v,dict):queue.append(v)
    return None
def event_kind(ev):
    if not isinstance(ev,dict):return "UNKNOWN"
    for k in ("type","eventType","name","action"):
        v=ev.get(k)
        if isinstance(v,str) and "#" in v:return v
    raw=json.dumps(ev,ensure_ascii=False,separators=(",",":"))
    matches=[k for k in ("ShotDetails#show","Time#show","OnCourt#show",
         "RawLeverage#show","Leverage#show","Insight#show","Alert#show",
         "HighlightVideo#show","CourtMeta#show") if '"'+k+'"' in raw]
    check(len(matches)<=1,"AMBIGUOUS_COMPANION_ORIGINAL_EVENT_TYPE")
    return matches[0] if matches else "UNKNOWN"
def get_source(root,gid):
    d=root/EV/("companion_sdk_original_"+gid)
    source=d/"sdk_observed_original.json"
    receipts=[d/"sdk_original_receipt.json",
              root/OLD_QA/("igp_companion_sdk_authorized_source_"+gid+"_20261029.json")]
    receipt=next((p for p in receipts if p.is_file()),None)
    if receipt is None:
        check(not source.exists(),"ORIGINAL_COMPANION_WITHOUT_SHA_RECEIPT:"+gid)
        return {"status":"MISSING_ORIGINAL_AUTHORIZED_CAPTURE","events":0,
                "sha256":None,"shotdetails":0,"event_types":{}},None
    r=load(receipt);check(r.get("game_id")==gid,"COMPANION_CROSS_GAME")
    if r.get("status")!="FULL_EVENT_RESPONSE_OBSERVED":
        check(not source.exists(),"SOURCE_EXISTS_WITH_NONFULL_RECEIPT:"+gid)
        return {"status":r.get("status"),"events":0,"sha256":None,
                "shotdetails":0,"event_types":{}},None
    check(source.is_file(),"MISSING_COMPANION_ORIGINAL_BODY:"+gid)
    raw=source.read_bytes()
    check(digest(raw)==r["original_body_sha256"] and len(raw)==r["original_body_bytes"],
          "ORIGINAL_COMPANION_BODY_SHA_OR_SIZE_DRIFT:"+gid)
    events=json.loads(raw)
    check(isinstance(events,list) and len(events)==r["original_body_event_count"],
          "COMPANION_SOURCE_COUNT_DRIFT:"+gid)
    counts=collections.Counter(event_kind(e) for e in events)
    check(counts["ShotDetails#show"]==r["original_body_shot_details_count"],
          "COMPANION_SOURCE_SHOT_DETAILS_DRIFT:"+gid)
    return {"status":"FULL_EVENT_RESPONSE_SHA_VERIFIED",
            "events":len(events),"sha256":digest(raw),
            "original_path":str((EV/("companion_sdk_original_"+gid)/"sdk_observed_original.json")),
            "shotdetails":counts["ShotDetails#show"],"event_types":dict(counts)},events

def make_new(gid,pbp,blue,events,official_sha,bp_sha,comp_sha):
    allactions={a["nba_action_number"]:a for a in pbp["actions"]}
    fga=[a for a in pbp["actions"] if a["action_type"] in ("2pt","3pt")]
    check(len({a["nba_action_number"] for a in fga})==len(fga),"DUPLICATE_OFFICIAL_FGA_ACTION")
    src_shots=blue["shot_difficulty"]["shotDifficulty"]
    by_bp=collections.defaultdict(list)
    for i,s in enumerate(src_shots):
        if type(s.get("ngssEventId"))==int:by_bp[s["ngssEventId"]].append((i,s))
    by_cp=collections.defaultdict(list);unknown_cp=0
    for i,e in enumerate(events or []):
        if event_kind(e)!="ShotDetails#show":continue
        meta=deep_metadata(e)
        if not isinstance(meta,dict): unknown_cp+=1;continue
        action=cint(meta.get("playId"));player=cint(meta.get("playerId"))
        v=meta.get("expFieldGoalPct")
        if action is None or player is None or type(v) not in (int,float) or not 0<=v<=1 or not isinstance(meta.get("features"),dict):
            unknown_cp+=1;continue
        by_cp[action].append((i,e,meta,player))
    rows=[];counts=collections.Counter();matched_bp=set();matched_cp=set()
    for a in fga:
        n=a["nba_action_number"]
        bp_hits=[(i,s) for i,s in by_bp[n] if s.get("shotType")==a["action_type"]
                and s.get("period")==a["period"] and
                str((s.get("shooter") or {}).get("playerId"))==str(a["person_id"])]
        bp_payload=None
        if len(bp_hits)==1:
            i,s=bp_hits[0];matched_bp.add(i)
            x=s.get("expFieldGoalPct")
            check(x is None or (type(x) in (int,float) and 0<=x<=1),
                  "BLUEPRINT_XFG_OUT_OF_RANGE:"+gid)
            bp_payload={"source_raw_record_number":i,"source_original_report_sha256":bp_sha,
                "published":s,"xfg_probability":x,"features_exact_raw":s.get("attributes"),
                "shot_releasetime_source_quality":"PUBLISHED_FIELD_NOT_VIDEO_CERTIFIED",
                "raw_body_joint_29_xyz_60hz_present":False}
            bp_grade="MATCHED_OFFICIAL_ACTION_SHOOTER_TYPE_PERIOD"
            counts["blueprint_matched"]+=1
        else:
            bp_grade=("NOT_IN_PUBLISHED_BLUEPRINT" if not by_bp[n] else
                      "QUARANTINED_DUPLICATE_MATCH" if len(bp_hits)>1 else
                      "QUARANTINED_SHOOTER_PERIOD_OR_SHOT_TYPE")
        cp_hits=[z for z in by_cp[n] if z[3]==a["person_id"] and
                 (z[2].get("period") is None or z[2].get("period")==a["period"])]
        advanced=None
        if len(cp_hits)==1:
            i,e,m,_=cp_hits[0];matched_cp.add(i)
            release=m.get("shotReleaseInfo")
            check(release is None or isinstance(release,dict),"INVALID_ORIGINAL_RELEASE")
            advanced={"source_event_index":i,"source_original_full_companion_response_sha256":comp_sha,
                      "source_event_uuid":e.get("uuid") or e.get("id"),
                      "source_biomechanics_features":m["features"],
                      "source_defensive_info":m.get("defensiveInfo"),
                      "source_shot_release_info":release,
                      "source_xfg_probability":m["expFieldGoalPct"],
                      "release_time_observation_grade":(
                          "RELEASE_TIME_NOT_OBSERVED_WINDOW_CENSORED"
                          if not isinstance(release,dict) or release.get("shotReleaseTime") is None
                          else "ORIGINAL_PUBLISHED_RELEASE_PARAMETER_NOT_VIDEO_CERTIFIED"),
                      "raw_joint_xyz_29_at_60Hz_present":False,
                      "source_30feature_fields":len(m["features"])}
            cp_grade="MATCHED_ORIGINAL_SHOTDETAILS_ACTION_SHOOTER_PERIOD"
            counts["advanced_matched"]+=1
        else:
            cp_grade=("NOT_IN_CAPTURED_COMPANION_SOURCE" if not by_cp[n]
                      else "QUARANTINED_COMPANION_IDENTITY_AMBIGUITY")
        best=(bp_payload["xfg_probability"] if bp_payload else None)
        origin="BLUEPRINT" if best is not None else None
        if best is None and advanced is not None:
            best=advanced["source_xfg_probability"];origin="ORIGINAL_COMPANION_SHOTDETAILS"
        if best is not None:counts["any_published_xfg"]+=1
        rows.append({"schema":"integrated-pulse.official-shot-with-biomechanics.v1",
           "game_id":gid,"nba_action_number":n,"nba_official_shot_event":a,
           "nba_pbp_normalized_source_sha256":official_sha,
           "blueprint_join_grade":bp_grade,"published_blueprint":bp_payload,
           "advanced_companion_join_grade":cp_grade,"published_advanced_companion":advanced,
           "best_published_xfg_probability":best,"best_published_xfg_origin":origin,
           "source_xfg_values_are_separate_models_not_necessarily_identical":True,
           "biomechanics_source_completeness_grade":(
               "ENGINEERED_30_FEATURES_ONLY_NOT_JOINT_POSE" if advanced else
               "BLUEPRINT_SHORT_FEATURES_ONLY" if bp_payload else
               "NO_PUBLISHED_SHOT_BIOMECHANICS"),
           "actual_shot_release_UTC_independently_verified":False,
           "original_29_joint_60hz_pose_trajectories_available":False})
    counts["official_fga"]=len(rows)
    counts["blueprint_source_shots"]=len(src_shots)
    counts["blueprint_source_quarantined"]=len(src_shots)-len(matched_bp)
    counts["companion_source_shots"]=sum(len(v) for v in by_cp.values())+unknown_cp
    counts["companion_source_quarantined"]=counts["companion_source_shots"]-len(matched_cp)
    check(len(rows)==counts["official_fga"],"OFFICIAL_FGA_LOST")
    return rows,dict(counts)

def main(root):
    reg=load(root/REG);games=reg["games"]
    check(len(games)==reg["counts"]["games"]==81,"81_GAME_REGISTRY_DRIFT")
    old=load(root/OLD);oldbp=load(root/OLD_BP)
    original=set(old["games"])
    check(len(original)==56 and original==set(oldbp["games"]) and original<=set(games),
          "FROZEN56_COHORT_INVALID")
    prior_fga=0;per={};total=collections.Counter()
    for gid,entry in sorted(games.items()):
        official=root/BASE/"official_pbp_timing/games"/(gid+".json")
        check(official.is_file() and filehash(official)==entry["nba_official_PBP_SHA256"],
              "CANONICAL_OFFICIAL_PBP_SHA_MISMATCH:"+gid)
        pbp=load(official);check(pbp.get("game_id")==gid and pbp.get("official_final"),
                             "NOT_FINAL_PBP:"+gid)
        fga=sum(a["action_type"] in ("2pt","3pt") for a in pbp["actions"])
        bpfile=root/BP/gid/"blueprint_report_raw.json"
        check(bpfile.is_file(),"MISSING_ORIGINAL_BLUEPRINT:"+gid)
        bpsha=filehash(bpfile);bp=load(bpfile)
        check(str(bp["game_header"]["gameId"])==gid,"BLUEPRINT_WRONG_GAME")
        check(bp["game_header"].get("gameStatus")==3,"BLUEPRINT_NOT_FINAL")
        check(isinstance(bp["shot_difficulty"]["shotDifficulty"],list),
              "ORIGINAL_BLUEPRINT_MISSING_SHOTS:"+gid)
        mods={k:("list" if isinstance(v,list) else "dict" if isinstance(v,dict) else "other")
              for k,v in bp.items() if k not in ("game_header",)}
        cp,events=get_source(root,gid)
        check(not (events is None and cp["sha256"]),"COMPANION_INDEX_INVALID")
        if gid in original:
            q=old["games"][gid];b=oldbp["games"][gid]
            check(q["official_fga"]==fga==b["official_field_goal_actions"],
                  "FROZEN_FGA_DRIFT:"+gid)
            check(bpsha==b["blueprint_original_report_sha256"],"FROZEN_BLUEPRINT_SHA_DRIFT")
            ledger=root/q["path"]
            check(ledger.is_file() and filehash(ledger)==q["source_sha256"],
                  "FROZEN56_SHOT_LEDGER_CHANGED:"+gid)
            counts={"official_fga":fga,
               "blueprint_matched":q["counts"].get("official_shots_with_identity_matched_Blueprint",0),
               "advanced_matched":q["counts"].get("official_shots_with_advanced_features",0),
               "any_published_xfg":q["counts"].get("official_shots_with_any_published_xfg",0)}
            path=q["path"];sh=q["source_sha256"];origin="UNCHANGED_ACCEPTED_56"
            prior_fga+=fga
        else:
            rows,counts=make_new(gid,pbp,bp,events,entry["nba_official_PBP_SHA256"],bpsha,cp["sha256"])
            dest=root/OUT/(gid+".jsonl.gz")
            raw=gziprows(rows);write_once(dest,raw)
            path=str(dest.relative_to(root));sh=digest(raw);origin="ADDITIVE_NEW25_SHA_GRADED"
        total["official_fga"]+=fga
        total["source_blueprint_shot_rows"]+=len(bp["shot_difficulty"]["shotDifficulty"])
        total["blueprint_matched"]+=counts["blueprint_matched"]
        total["advanced_matched"]+=counts["advanced_matched"]
        total["any_published_xfg"]+=counts["any_published_xfg"]
        total["companion_events"]+=cp["events"]
        total["companion_shotdetails"]+=cp["shotdetails"]
        total["games_with_full_blueprint"]+=1
        total["games_with_full_companion"]+=int(cp["status"]=="FULL_EVENT_RESPONSE_SHA_VERIFIED")
        total["new25_games"]+=int(gid not in original)
        per[gid]={"source_grade":origin,"official_FGA":fga,
            "official_PBP_SHA256":entry["nba_official_PBP_SHA256"],
            "blueprint_original_source_path":str(BP/gid/"blueprint_report_raw.json"),
            "blueprint_original_SHA256":bpsha,
            "blueprint_report_modules_present":mods,
            "blueprint_reported_missing_modules":bp.get("missingModules"),
            "blueprint_published_shot_rows":len(bp["shot_difficulty"]["shotDifficulty"]),
            "original_companion":cp,
            "shot_ledger_path":path,"shot_ledger_sha256":sh,
            "shot_identity_join_counts":counts,
            "tracking_source_manifest_path":entry["native_original_manifest_path"],
            "tracking_original_manifest_sha256":entry["native_original_manifest_sha256"],
            "original_29_joint_60Hz_pose_certified":False,
            "physical_release_and_ball_custody_certified":False}
    check(total["new25_games"]==25 and prior_fga==old["original_official_field_goals"],
          "FROZEN56_FGA_OR_NEW25_DENOMINATOR_DRIFT")
    check(total["blueprint_matched"]<=total["official_fga"] and
          total["advanced_matched"]<=total["official_fga"],"SOURCE_COUNTS_OUT_OF_RANGE")
    index={"schema":"igp81.all-original-detail-layers-source-grade.v1",
           "official_games":81,"original_frozen_56_shot_ledgers_unchanged":True,
           "additive_new25_official_shot_ledgers":25,
           "source_blueprint_all_modules_indexed":True,
           "source_companion_full_original_events_sha_verified":True,
           "published_30feature_biomechanics_not_raw_29joint_pose":True,
           "NBA_official_PBP_canonical":True,
           "original_tracking_native_manifest_SHA_preserved":True,
           "missing_source_features_are_null_not_imputed":True,
           "physical_possessions_video_release_and_pose_uncertified":True,
           "totals":dict(total),"games":per}
    write_once(root/OUT/"index.json",jsonbytes(index))
    summary={"status":"SOURCE_GRADED_ADDITIVE_81_DETAIL_LAYER_INDEX",
       "games":81,"frozen_56":56,"new_partitions":25,
       "blueprint":total["games_with_full_blueprint"],
       "full_companion_source":total["games_with_full_companion"],
       "official_fga":total["official_fga"],
       "blueprint_shots_exact":total["blueprint_matched"],
       "provider_30feature_shots_exact":total["advanced_matched"],
       "shots_published_xfg":total["any_published_xfg"],
       "uncertified_29joint_pose_games":81}
    print("IGP81_DETAIL_SOURCE_GRADE",json.dumps(summary,sort_keys=True),flush=True)
    return summary
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--root",type=Path,required=True)
    main(a.parse_args().root)
