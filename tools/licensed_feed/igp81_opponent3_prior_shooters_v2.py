#!/usr/bin/env python3
"""FULL81 historical shooter-selection extension (private-side data, aggregate outputs).

2015+ season histories are NOT assumed: this V2 uses one immutable public CSV
mirror of official NBA 2025-26 regular season 3PM/3PA plus original private
FULL81 NBA PBP. It estimates shooter composition, not causal shot deterrence.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,math,random,statistics
from pathlib import Path
from igp81_opponent3_luck_source_audit_v1 import audit as full81,pct,q,check
PRIOR_BLOB_SHA="2981602d588393a26bdd8f6321a2da91c016283a"
PRIOR_COMMIT="f785bb34415b2bf4c80614dcfa4a305cc9969ee5"
SEED=81120261102
TAU=75.0
def loadprior(file):
    raw=file.read_bytes()
    sh=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
    check(sh==PRIOR_BLOB_SHA,"PREVIOUS_SEASON_PUBLIC_SOURCE_BLOB_SHA_DRIFT")
    rows=list(csv.DictReader(raw.decode("utf8-sig").splitlines()))
    lookup={};sM=sN=0
    for r in rows:
        check(r["season"]=="2025-26" and r["season_type"]=="Regular Season",
          "WRONG_PREVIOUS_SEASON")
        pid=int(r["player_id"]);n=int(r["three_point_attempted"]);m=int(r["three_point_made"])
        check(0<=m<=n,"INVALID_PRIOR_3PT")
        check(pid not in lookup,"DUPLICATE_PRIOR_NBA_ID")
        lookup[pid]={"id":pid,"name":r["player_name"],"a":n,"m":m,
                 "raw":m/n if n else None}
        sN+=n;sM+=m
    check(len(lookup)>=400 and sN>=50000 and .30<=sM/sN<=.40,
          "HISTORICAL_REGULAR_SEASON_INCOMPLETE")
    return lookup,sM/sN,{"prior_players":len(lookup),"prior_3pm":sM,
                        "prior_3pa":sN,"git_blob_sha1":sh,"source_commit":PRIOR_COMMIT}
def logit(p):return math.log(p/(1-p))
def logistic(t):return 1/(1+math.exp(-t))
def predict(v,priorleague,currentleague,tau):
    if v is None or v["a"]==0:return currentleague
    a=v["a"];p=(v["m"]+tau*priorleague)/(a+tau)
    return logistic(logit(p)+logit(currentleague)-logit(priorleague))

def run(root,prior_file,draws=3000):
    baseline,shots=full81(root,replicates=draws,include_shots=True)
    lookup,oldleague,priorinfo=loadprior(prior_file)
    newleague=baseline["official_3pm"]/baseline["official_3pa"]
    for r in shots:
        v=lookup.get(r["player"])
        r["prev"]=v
        r["prior75"]=predict(v,oldleague,newleague,TAU)
        r["prior25"]=predict(v,oldleague,newleague,25)
        r["prior150"]=predict(v,oldleague,newleague,150)
        r["prev_eligible"]=bool(v and v["a"]>=100)
        r["poor_shooter"]=bool(r["prev_eligible"] and v["raw"]<.32)
        r["elite_shooter"]=bool(r["prev_eligible"] and v["raw"]>=.38)
        r["middle_shooter"]=bool(r["prev_eligible"] and .32<=v["raw"]<.38)
    rowsby=collections.defaultdict(list)
    for r in shots:rowsby[r["def"]].append(r)
    rng=random.Random(SEED)
    out={}
    for team,rows in sorted(rowsby.items()):
        n=len(rows);m=sum(x["make"] for x in rows)
        expected=sum(x["prior75"] for x in rows)
        g=collections.defaultdict(list)
        for x in rows:g[x["game"]].append(x)
        gs=sorted(g)
        diff=[];mix=[]
        for _ in range(draws):
            sample=[x for gid in rng.choices(gs,k=len(gs)) for x in g[gid]]
            diff.append(sum(x["prior75"]-x["make"] for x in sample)/len(sample))
            mix.append(sum(x["prior75"]-newleague for x in sample)/len(sample))
        eligible=[x for x in rows if x["prev_eligible"]]
        unknown=[x for x in rows if not(x["prev"] and x["prev"]["a"]>0)]
        elite=[x for x in rows if x["elite_shooter"]]
        poor=[x for x in rows if x["poor_shooter"]]
        known=[x for x in rows if x["prev"] and x["prev"]["a"]>0]
        player_counts=collections.Counter(x["player"] for x in rows)
        detail=[]
        for pid,attempts in player_counts.most_common():
            past=lookup.get(pid)
            rws=[x for x in rows if x["player"]==pid]
            detail.append({"player_name":past["name"] if past else None,
                "player_id":pid,"opponent_3pa":attempts,
                "opponent_3pm":sum(x["make"] for x in rws),
                "previous_season_3pa":past["a"] if past else 0,
                "previous_season_3pct":pct(past["raw"]) if past and past["raw"] is not None else None,
                "season_prior_expected_pct":pct(statistics.mean(x["prior75"] for x in rws)),
                "prior_shooter_group":("ELITE_38" if rws[0]["elite_shooter"] else
                     "LOW_LT32" if rws[0]["poor_shooter"] else
                     "MIDDLE_32_38" if rws[0]["middle_shooter"] else "INSUFFICIENT_PREV_100")})
        detail.sort(key=lambda x:(-x["opponent_3pa"],x["player_id"]))
        allmatched=[x for x in rows if x["xfg"] is not None]
        elitematched=[x for x in elite if x["xfg"] is not None]
        out[team]={"games":baseline["all_teams"][team]["games"],
          "opponent_3pm":m,"opponent_3pa":n,"opponent_3pct":pct(m/n),
          "previous_season_shooter_history_matched_3pa":len(known),
          "previous_season_shooter_history_matched_pct":pct(len(known)/n),
          "previous_season_history_missing_3pa":len(unknown),
          "previous_100plus_3pa_share_pct":pct(len(eligible)/n),
          "historical_shooter_expected_3pct":pct(expected/n),
          "historical_shooter_selection_minus_current_81_league_pp":round(100*(expected/n-newleague),3),
          "historical_expected_minus_actual_pp":round(100*(expected/n-m/n),3),
          "hist_expected_minus_actual_game_bootstrap_CI95_pp":[pct(q(diff,.025)),pct(q(diff,.975))],
          "hist_shooter_selection_minus_current81_league_CI95_pp":[pct(q(mix,.025)),pct(q(mix,.975))],
          "historical_expected_tau25_pct":pct(statistics.mean(x["prior25"] for x in rows)),
          "historical_expected_tau150_pct":pct(statistics.mean(x["prior150"] for x in rows)),
          "previous_year_low_lt32_shooter_3pa":len(poor),
          "previous_year_low_lt32_shooter_share_all_pct":pct(len(poor)/n),
          "previous_year_elite_ge38_shooter_3pa":len(elite),
          "previous_year_elite_ge38_shooter_share_all_pct":pct(len(elite)/n),
          "elite_shooter_matched_xfg_count":len(elitematched),
          "elite_shooter_matched_xfg_expected_pct":pct(statistics.mean(x["xfg"] for x in elitematched)) if elitematched else None,
          "elite_shooter_matched_actual_pct":pct(statistics.mean(x["make"] for x in elitematched)) if elitematched else None,
          "elite_shooter_median_Blueprint_contestDistance_raw":q([x["contest"] for x in elitematched if type(x["contest"]) in (int,float)],.5),
          "unique_opponent_shooters":len(player_counts),
          "top_opponent_shooter_attempts":detail[:12]}
    return {"schema":"igp81.opponent3.historical-shooter-prior-v2",
        "qualification":"FIRST_STAGE_NO_TEAM_CAUSAL_DEFENSIVE_CLAIM",
        "original_FULL81_3pa":len(shots),"original_FULL81_3pm":sum(r["make"] for r in shots),
        "original_FULL81_games":81,"original_FULL81_teams":len(out),
        "full81_league_3pct":pct(newleague),"previous_year_league_3pct":pct(oldleague),
        "historical_prior_source":priorinfo,"estimator":"NBA player 2025-26 full season 3PM/3PA, beta shrink tau75 to 2025-26 league, logit shift to full81 league, missing fallback to full81 league",
        "coverage_and_limitations":["One prior season not full career; 100+ previous attempts used for tiers.",
           "Elite group 38%+, low group <32%; threshold sensitive, not causal suppression.",
           "Historical shooting includes shot environment and offensive role; not pure talent.",
           "Neither shooter prior nor published Blueprint xFG independently certifies defensive pressure.",
           "Shooter prior pre-2026-27 avoids target-game outcome contamination.",
           "Small six-game team sample, game-cluster bootstrap only, selective threshold and no multiple-testing correction.",
           "Sources original NBA official PBP plus external public NBA API historical mirror with blob lock."],
        "shortlist_under30":[{"team":t,**r} for t,r in out.items() if r["opponent_3pct"]<30],
        "teams":out}

def selftest():
    assert 0<predict({"a":200,"m":80},.36,.35,75)<1
    assert abs(predict(None,.36,.35,75)-.35)<1e-12
    assert pct(.288)==28.8
    print("IGP81_OPP3_HISTORICAL_PRIOR_SELFTEST_PASS")
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--prior")
    p.add_argument("--output")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:
        check(a.prior and a.output,"PRIOR_AND_OUTPUT_REQUIRED")
        f=Path(a.output);check(not f.exists(),"REFUSE_OVERWRITE_EXISTING_QA")
        d=run(Path(a.root),Path(a.prior))
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
        # Only aggregate quantities in public logs, no shooter/shot rows.
        eligible=[{k:v for k,v in r.items() if k not in ("top_opponent_shooter_attempts",)}
            for r in d["shortlist_under30"]]
        print("IGP81_HISTORICAL_SHOOTER_PRIOR_AGGREGATE",json.dumps({
           "official_3pa":d["original_FULL81_3pa"],
           "previous_year_source":d["historical_prior_source"],
           "previous_league_pct":d["previous_year_league_3pct"],
           "shortlist":eligible},sort_keys=True))
