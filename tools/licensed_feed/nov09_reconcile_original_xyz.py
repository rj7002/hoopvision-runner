#!/usr/bin/env python3
"""Reconcile existing original NBA SDK/live slots using SHA-verified private assets only."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,tarfile
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def rank(r):
    p=r["positions_native_units"]
    return (sum(k!="ball" for k in p),int("ball" in p),int(r.get("source_upstream_interpolated") is False))
def reconcile(gid,live,sdk,out):
    if len(gid)!=10 or not gid.startswith("00226") or not gid.isdigit(): raise ValueError("invalid_game_id")
    livebest={}; chosen={}; digests={}; variants=0; conflicts=0
    def ingest(path,kind,store):
        nonlocal variants,conflicts
        raw=path.read_bytes();h=sha(raw)
        sc=json.loads(path.with_suffix("").with_suffix(".json").read_bytes())
        if sc.get("archive_sha256")!=h: raise ValueError("original_source_sha_mismatch")
        digests[kind+"/"+path.name]=h
        with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tf:
            if not {"manifest.json","raw-slots.jsonl.gz"}.issubset(tf.getnames()):
                raise ValueError("source_members_missing")
            m=json.load(tf.extractfile("manifest.json"))
            if m.get("game_id")!=gid or m.get("observed") is not True or m.get("imputed") is not False:
                raise ValueError("nonoriginal_source")
            for k in ("start_ms","successful_windows","frames_with_players","frames_with_ball"):
                if m[k]!=sc[k]:raise ValueError("source_manifest_mismatch")
            rows=gzip.decompress(tf.extractfile("raw-slots.jsonl.gz").read()).splitlines()
            if len(rows)!=m["successful_windows"]:raise ValueError("source_window_count_mismatch")
            for line in rows:
                row=json.loads(line)
                if row["to"]!=row["from"]+4999:raise ValueError("noncanonical_slot")
                for event in row.get("events",[]):
                    for frame in (event.get("metadata") or {}).get("keyframes",[]):
                        t=frame.get("timestamp");p=frame.get("positions")
                        if not isinstance(t,int) or not isinstance(p,dict):continue
                        variants+=1
                        if not p:continue
                        rec={"source_frame_utc_ms":t,"positions_native_units":p,
                             "source_upstream_interpolated":frame.get("interpolated"),
                             "source_original_archive":kind+"/"+path.name,
                             "source_original_archive_sha256":h,
                             "source_grade":"ORIGINAL_SDK_NOT_OFFICIAL_TEN_CERTIFIED"}
                        prev=store.get(t)
                        if prev is None or rank(rec)>rank(prev):store[t]=rec
                        elif rank(rec)==rank(prev) and rec["positions_native_units"]!=prev["positions_native_units"]:
                            conflicts+=1
    lives=sorted(live.glob("live-*.tar.gz"))
    sdks=sorted(sdk.glob("sdk-part-*.tar.gz"))
    if len(lives)!=8 or len(sdks)>13:raise ValueError("source_part_count_invalid")
    for p in lives:ingest(p,"live",livebest)
    chosen.update(livebest)
    for p in sdks:ingest(p,"sdk",chosen)
    def counts(x):
        return {
          "native_utc_with_any_xyz":len(x),
          "native_utc_with_player_xyz":sum(any(k!="ball" for k in z["positions_native_units"]) for z in x.values()),
          "native_utc_with_ball_xyz":sum("ball" in z["positions_native_units"] for z in x.values()),
          "native_utc_with_player_ball_xyz":sum("ball" in z["positions_native_units"] and any(k!="ball" for k in z["positions_native_units"]) for z in x.values()),
        }
    before=counts(livebest);after=counts(chosen)
    if any(after[k]<before[k] for k in before):raise ValueError("source_union_regression")
    out.mkdir(parents=True,exist_ok=True)
    dst=out/"source_original_native.jsonl.gz"
    with dst.open("wb") as f:
        with gzip.GzipFile(fileobj=f,filename="",mode="wb",mtime=0,compresslevel=6) as g:
            for t,rec in sorted(chosen.items()):
                g.write((json.dumps(rec,sort_keys=True,separators=(",",":"))+"\n").encode())
    result={
      "schema":"igp.nov09-original-source-progressive-merge.v1",
      "game_id":gid,"original_live_archives":len(lives),"original_sdk_archives":len(sdks),
      "original_source_sha256":dict(sorted(digests.items())),
      "live_only":before,"sdk_plus_live":after,
      "net_new_player_utc":after["native_utc_with_player_xyz"]-before["native_utc_with_player_xyz"],
      "net_new_ball_utc":after["native_utc_with_ball_xyz"]-before["native_utc_with_ball_xyz"],
      "source_sha256":sha(dst.read_bytes()),"source_filename":dst.name,
      "source_equal_richness_conflicts":conflicts,"source_keyframe_variants":variants,
      "all_13_sdk_parts_present":len(sdks)==13,
      "full_game_active_play_certified":False,"official_ten_lineup_certified":False,
      "raw_source_unchanged":True,"modeled_coordinates_added":0
    }
    (out/"index.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    return result
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--game-id",required=True)
    ap.add_argument("--live",type=Path,required=True)
    ap.add_argument("--sdk",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    x=ap.parse_args()
    v=reconcile(x.game_id,x.live,x.sdk,x.out)
    print("IGP_SHA_ORIGINAL_BACKFILL_MERGED",json.dumps({
      "game_id":x.game_id,"sdk_parts":v["original_sdk_archives"],
      "player_xyz":v["sdk_plus_live"]["native_utc_with_player_xyz"],
      "ball_xyz":v["sdk_plus_live"]["native_utc_with_ball_xyz"],
      "new_player_xyz":v["net_new_player_utc"],"new_ball_xyz":v["net_new_ball_utc"]},sort_keys=True))
