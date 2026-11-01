#!/usr/bin/env python3
"""IGP81 exploratory opponent-3P decomposition. Private source input, aggregate-only output.

Original NBA PBP is canonical for 3PA/3PM. Blueprint xFG is a published, coarse
context model, not a calibrated causal defensive-effect or pure-luck oracle.
No private shot/player rows are emitted. No engine changes.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,random,statistics
from pathlib import Path

BASE=Path("gamepulse/fusion")
INDEX=BASE/"materialized/igp_2026_27_unified_season_v3/shot_biomechanics_all81_v1/index.json"
PBP=BASE/"official_pbp_timing/games"
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def check(v,msg):
    if not v: raise ValueError(msg)
def pct(x): return round(100*x,3)
def q(x,f):
    s=sorted(x)
    if not s:return None
    return round(s[min(len(s)-1,max(0,int((len(s)-1)*f)))],4)

def audit(root,replicates=3000):
    ix=json.loads((root/INDEX).read_text())
    check(ix.get("official_games")==81 and len(ix["games"])==81,"NOT_FULL81")
    shots=[]; allteams=set(); game_count=collections.Counter()
    mismatches=collections.Counter()
    for gid,meta in sorted(ix["games"].items()):
        fp=root/PBP/(gid+".json")
        check(sha(fp)==meta["official_PBP_SHA256"],"PBP_SHA:"+gid)
        d=json.loads(fp.read_bytes())
        check(d.get("game_id")==gid and d.get("official_final"),"PBP_ID_OR_FINAL:"+gid)
        home=d["official_final"]["home"]["team"];away=d["official_final"]["away"]["team"]
        check(home!=away,"MATCHUP_DUPLICATE")
        allteams|={home,away};game_count[home]+=1;game_count[away]+=1
        fga=[a for a in d["actions"] if a["action_type"] in ("2pt","3pt")]
        check(len(fga)==meta["official_FGA"],"FGA_NOT_RECONCILED:"+gid)
        bpfile=root/meta["blueprint_original_source_path"]
        check(sha(bpfile)==meta["blueprint_original_SHA256"],"BLUEPRINT_SHA:"+gid)
        bp=json.loads(bpfile.read_bytes())["shot_difficulty"]["shotDifficulty"]
        bm=collections.defaultdict(list)
        for item in bp:
            k=item.get("ngssEventId")
            if isinstance(k,int):bm[k].append(item)
        # Mirror the previously validated FULL81 official score reader:
        # order by period/descending clock and ONLY update the scoreboard on
        # scoring actions, never on rebounds/turnovers carrying stale displays.
        events=sorted(d["actions"],key=lambda a:(a["period"],-a["game_clock_ms_remaining"],
            a["order_number"],a["nba_action_number"]))
        prevH=0;prevA=0;seen=set()
        score_types={"2pt":2,"3pt":3,"freethrow":1}
        for a in events:
            key=(a["period"],a["nba_action_number"])
            check(key not in seen,"DUPLICATE_OFFICIAL_ACTION:"+gid)
            seen.add(key)
            h=a["score_home"];aw=a["score_away"]
            check(isinstance(h,int) and isinstance(aw,int),"PBP_SCORE_TYPE:"+gid)
            dh=da=0
            if a["action_type"] in score_types:
                dh=h-prevH;da=aw-prevA
                npts=score_types[a["action_type"]]
                check(0<=dh<=npts and 0<=da<=npts and not(dh and da),
                      "OFFICIAL_SCORING_DELTA_UNRESOLVED:"+gid+":"+str(a["nba_action_number"]))
                check(not (dh or da) or a["team"]==(home if dh else away),
                      "OFFICIAL_SCORE_TEAM_MISMATCH:"+gid)
                prevH=h;prevA=aw
            if a["action_type"]=="3pt":
                team=a["team"]
                check(team in (home,away),"SHOT_TEAM_INVALID:"+gid)
                delta=(dh if team==home else da)
                check(delta in (0,3),"THREE_SCORE_DELTA_CONFLICT:"+gid+":"+str(a["nba_action_number"])+":"+str(delta))
                hit=[v for v in bm[a["nba_action_number"]] if
                    v.get("shotType")=="3pt" and v.get("period")==a["period"]
                    and str((v.get("shooter") or {}).get("playerId"))==str(a["person_id"])]
                item=hit[0] if len(hit)==1 else None
                if len(hit)>1:mismatches["ambiguous_blueprint"]+=1
                if item is not None and bool(item.get("success")) != (delta==3):
                    mismatches["blueprint_outcome_disagreements"]+=1
                    item=None
                p=item.get("expFieldGoalPct") if item else None
                if type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1:p=None
                attrs=item.get("attributes",{}) if item else {}
                shots.append({"game":gid,"def":away if team==home else home,
                              "off":team,"player":a["person_id"],"make":int(delta==3),
                              "xfg":p,"contest":attrs.get("contestDistance"),
                              "dist":attrs.get("shotDistance")})
        check(prevH==d["official_final"]["home"]["score"] and
              prevA==d["official_final"]["away"]["score"],
              "FINAL_OFFICIAL_SCORE_NOT_RECONCILED:"+gid)
    check(len(shots)==6094,"OFFICIAL_3PA_NOT_6094")
    check(sum(game_count.values())==162,"81GAME_TEAM_COUNT_DRIFT")
    check(len(allteams)==30,"TEAM_COUNT_NOT_30")

    # Strictly out-of-game (not out-of-season) opponent ability baseline.
    # This is a weak short-season SHOOTER-MIX PROXY, not career shooter talent.
    group=collections.Counter();made=collections.Counter()
    gp=collections.Counter();gm=collections.Counter()
    for r in shots:
        group[r["player"]]+=1;made[r["player"]]+=r["make"]
        k=(r["player"],r["game"]);gp[k]+=1;gm[k]+=r["make"]
    league=sum(r["make"] for r in shots)/len(shots)
    for r in shots:
        k=(r["player"],r["game"])
        n=group[r["player"]]-gp[k];m=made[r["player"]]-gm[k]
        r["skill40"]=(m+40*league)/(n+40)
        r["skill100"]=(m+100*league)/(n+100)

    teams={}
    byteam=collections.defaultdict(list)
    for r in shots:byteam[r["def"]].append(r)
    rng=random.Random(81120261101)
    for team,rows in sorted(byteam.items()):
        n=len(rows);m=sum(r["make"] for r in rows)
        matched=[r for r in rows if r["xfg"] is not None]
        mcount=len(matched)
        x=sum(r["xfg"] for r in matched)
        a=sum(r["make"] for r in matched)
        # Compare identical matched shots, never full actual vs partial expected.
        delta=(x-a)/mcount if mcount else None
        games=collections.defaultdict(list)
        for r in matched:games[r["game"]].append(r)
        gkeys=sorted(games)
        sampled=[]
        if mcount and gkeys:
            for _ in range(replicates):
                draw=[r for g in rng.choices(gkeys,k=len(gkeys)) for r in games[g]]
                sampled.append(sum(r["xfg"]-r["make"] for r in draw)/len(draw))
        cd=[r["contest"] for r in matched if type(r["contest"]) in (int,float)]
        teams[team]={"games":game_count[team],"opp_3pa":n,"opp_3pm":m,
          "opp_3pct":pct(m/n),"under_30":m/n<.30,
          "xfg_matched_n":mcount,"xfg_coverage_pct":pct(mcount/n),
          "matched_actual_3pct":pct(a/mcount) if mcount else None,
          "matched_published_xfg_pct":pct(x/mcount) if mcount else None,
          "matched_xfg_minus_actual_pp":round(100*delta,3) if delta is not None else None,
          "matched_xfg_minus_actual_cluster_boot_ci95_pp":[pct(q(sampled,.025)),pct(q(sampled,.975))] if sampled else None,
          "all_3pa_leave_game_out_shooter_proxy_pct":pct(statistics.mean(r["skill40"] for r in rows)),
          "all_3pa_shooter_proxy_tau100_pct":pct(statistics.mean(r["skill100"] for r in rows)),
          "published_blueprint_contest_distance_median_raw":q(cd,.5),
          "contest_distance_n":len(cd)}
    check(sum(t["opp_3pa"] for t in teams.values())==6094,"TEAM_SHOTS_NOT_RECONCILED")
    shortlist=sorted(({"team":team,**t} for team,t in teams.items() if t["under_30"]),
                     key=lambda d:d["opp_3pct"])
    return {"schema":"igp81.opponent3.exploratory.source-verified.v1",
      "status":"RESEARCH_ONLY_NOT_CAUSAL_DEFENSIVE_IMPACT",
      "games":81,"official_3pa":len(shots),"official_3pm":sum(r["make"] for r in shots),
      "league_in_81_3pct":pct(league),"team_count":len(teams),
      "source_checks":dict(mismatches),
      "shortlist_under30":shortlist,"all_teams":teams,
      "limitations":["Blueprint xFG is coarsely rounded and may already include defender/shooter context",
       "xFG minus actual is model-conditioned residual, not proven luck",
       "shooter proxy uses only 81 cohort, not career or prior seasons",
       "published contestDistance raw units/meaning require provider and video validation",
       "some 3PA lack exact Blueprint joins; matched-subset inference is selection-sensitive",
       "not independently calibrated on held-out games","not a causal measure of team defense"]}

def selftest():
    assert pct(.298)==29.8
    assert q([3,1,2],.5)==2
    assert q([],.5) is None
    print("IGP81_OPP3_SOURCE_FREE_TESTS_PASS")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=".")
    p.add_argument("--out");p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:
        check(a.out,"OUTPUT_REQUIRED")
        dest=Path(a.out)
        check(not dest.exists(),"OUTPUT_EXISTS_NO_OVERWRITE")
        r=audit(Path(a.root))
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
        print("IGP81_OPP3_AGGREGATE_RESULT",json.dumps({k:v for k,v in r.items()
           if k!="all_teams"},sort_keys=True),flush=True)
