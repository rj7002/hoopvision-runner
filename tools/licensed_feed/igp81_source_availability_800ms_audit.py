#!/usr/bin/env python3
"""Reproducible 81-game SDK-availability denominator at 10 Hz.
Source present: an original native player record AND ball record within 800ms
of the strict NBA clock+ten lineup S1 grid timestamp. Do not reinterpret
companion events/pose absence as player+ball source absence. Exact conditional
coverage requires per-scene intersection with the complete-11 mask; report
a rigorous interval until that check exists.
"""
import argparse,bisect,collections,hashlib,json
from pathlib import Path
BASE=Path("gamepulse/fusion")
QA=BASE/"qa/igp_v32"
def require(x,s):
    if not x:raise ValueError(s)
def load(p):return json.loads(p.read_bytes())
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(root):
    from igp81_new10_guarded_p2b_shadow_audit_v1 import raw_reference, EXTRA, NEW10
    from igp_native_scene_season_68_benchmark_v1 import load_game
    from igp_g4_post36_official_ten_evidence_v1 import paired_windows
    from igp_68_live_play_tracking_qa_v1 import LIVE,official_event_pair_segments,clip_to_official_windows,segment_at
    root=Path(root)
    old=load(root/QA/"igp_v32_71game_source_vacancy_priority_inventory_v1.json")
    gate=load(root/QA/"igp81_full_native_source_promotion_gate_run_41231284682.json")
    require(old["games"]==71 and old["counts"]["grid_total"]==1159651,"71_S1_SOURCE_DRIFT")
    require(gate["eligible_full81_10hz_source_grade_samples"]==1340811
            and gate["eligible_full81_10hz_complete_samples"]==1171507,"81_RELEASE_SOURCE_DRIFT")
    meta,files=raw_reference(root)
    totals=collections.Counter()
    records={}
    for gid in sorted(NEW10):
        pbpp=root/EXTRA/"games"/(gid+".json")
        require(sh(pbpp)==meta[gid]["normalized_sha256"],"OFFICIAL_PBP_SHA_DRIFT:"+gid)
        pbp=load(pbpp)
        box=json.loads(files["boxscore_"+gid+".json"])
        frames,manifest,originalsha=load_game(root,gid)
        require(manifest["original_archive_part_count_verified"]==13,"NATIVE_SDK_SOURCE_INCOMPLETE:"+gid)
        windows,_,_=paired_windows(pbp,box)
        segs=clip_to_official_windows(official_event_pair_segments(pbp["actions"])[0],windows)
        starts=[s[0] for s in segs]
        ts=[t for t,_ in frames]
        actor=[0];ball=[0]
        for _,pos in frames:
            actor.append(actor[-1]+int(any(k!="ball" for k in pos)))
            ball.append(ball[-1]+int("ball" in pos))
        c=collections.Counter()
        for wi,(lo,hi,_,roster) in enumerate(windows):
            require(len(set(roster))==10,"OFFICIAL_TEN_INVALID")
            for t in range(((lo+99)//100)*100,hi+1,100):
                seg=segment_at(t,segs,starts)
                if seg is None or seg[2]!=LIVE:continue
                require(seg[4]==wi,"S1_LIVE_WINDOW_CONFLICT")
                i=bisect.bisect_left(ts,t-800);j=bisect.bisect_right(ts,t+800,i)
                has_actor=actor[j]>actor[i];has_ball=ball[j]>ball[i]
                c["s1_grid"]+=1
                c["no_player"]+=not has_actor
                c["no_ball"]+=not has_ball
                c["no_player_or_ball"]+=not(has_actor and has_ball)
                c["neither_player_nor_ball"]+=not(has_actor or has_ball)
        qa=load(root/QA/("igp81_new10_guarded_shadow_"+gid+".json"))["games"][gid]["counts"]
        require(c["s1_grid"]==qa["strict_S1_10hz_samples"],"S1_NEW10_DENOMINATOR_DRIFT:"+gid)
        c["complete_ten_ball"]=qa["union_guarded_plus_baseline_complete"]
        records[gid]={"counts":dict(c),"original_native_SHA256":originalsha}
        totals.update(c)
        print("IGP81_NEW10_SOURCE_AVAILABILITY",gid,c["s1_grid"],c["no_player_or_ball"],flush=True)
    oldc=old["counts"]
    unavailable71=(oldc["grid_no_player_source_near_800ms"]+
        oldc["grid_no_ball_source_near_800ms"]-
        oldc["grid_no_player_and_no_ball_source_near_800ms"])
    unavailable=unavailable71+totals["no_player_or_ball"]
    grid=gate["eligible_full81_10hz_source_grade_samples"]
    complete=gate["eligible_full81_10hz_complete_samples"]
    require(oldc["grid_total"]+totals["s1_grid"]==grid,"GRID_81_NOT_CONSERVED")
    available=grid-unavailable
    result={"schema":"igp81.original-native-sdk-proximity-800ms-source-availability.v1",
      "games":81,"cadence_hz":10,
      "definition":"At least one raw player and raw ball within +/-800ms of official S1 tick",
      "source_proximity_is_not_ten_players_observed":True,
      "original81_strict_s1_ticks":grid,"source_grade_complete_11_ticks":complete,
      "unconditional_coverage_pct":round(100*complete/grid,5),
      "source_unavailable_800ms_ticks":unavailable,
      "source_available_800ms_ticks":available,
      "source_adjusted_exact_rate_unknown_without_complete_mask_intersection":True,
      "conditional_lower_bound_pct":round(100*max(0,complete-unavailable)/available,5),
      "conditional_upper_bound_pct":round(100*min(available,complete)/available,5),
      "original71_unavailable":unavailable71,
      "original10_unavailable":totals["no_player_or_ball"],
      "new10":records,
      "independent_video_physical_truth_certified":False}
    out=root/QA/"igp81_10hz_sdk_source_availability_800ms_v1.json"
    data=(json.dumps(result,sort_keys=True,indent=2)+"\n").encode()
    if out.exists():require(out.read_bytes()==data,"ORIGINAL_SOURCE_AVAILABILITY_QA_DRIFT")
    else:out.write_bytes(data)
    print("IGP81_SOURCE_ADJUSTED_10HZ",json.dumps({
      k:result[k] for k in ("unconditional_coverage_pct","source_unavailable_800ms_ticks",
        "source_available_800ms_ticks","conditional_lower_bound_pct",
        "conditional_upper_bound_pct")},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    run(p.parse_args().root)
