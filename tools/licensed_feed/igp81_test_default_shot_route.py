#!/usr/bin/env python3
"""Release gate: all81 official FGA source/identity and canonical engine route."""
import json
import igp81_default_engine_v1 as engine
from query_igp81_full_shot_detail_v1 import query, audit
assert engine.DEFAULT_ENGINE=="IGP32_P2B_GUARDED_NBA81_FULL_SOURCE_QA_10HZ_20261101"
for gid in ("0022600009","0022600015","0022600142","0022600143"):
    rows=engine.query(".",game_id=gid,include_shots=True,shot_limit=1)
    assert rows["official_fga_game"]>0 and len(rows["rows"])==1
    action=rows["rows"][0]["nba_action_number"]
    single=engine.query(".",game_id=gid,shot_action_number=action,shot_limit=1)
    assert single["rows"][0]==rows["rows"][0] and single["selected"]==1
    assert single["tracking_engine_id"]==engine.DEFAULT_ENGINE
    print("IGP81_CANONICAL_DEFAULT_SHOT_QUERY_OK",gid,action,flush=True)
print("IGP81_DEFAULT_ENGINE_SHOT_QUERY_RELEASE_ACCEPTED")
