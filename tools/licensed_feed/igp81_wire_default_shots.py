#!/usr/bin/env python3
"""Add exactly one backwards-compatible, 81-game detailed-shot query route."""
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument("--root",required=True)
root=Path(p.parse_args().root)
path=root/"gamepulse/fusion/igp81_default_engine_v1.py"
source=path.read_text()
anchor='def query(root=".", *, engine=DEFAULT_ENGINE, **filters):\n    if engine == DEFAULT_ENGINE:'
replacement="\n".join((
    'def query(root=".", *, engine=DEFAULT_ENGINE, **filters):',
    '    # Source-original 81game official FGA, Blueprint, biomechanics, xFG.',
    '    with_shots=filters.pop("include_shots",False)',
    '    action=filters.pop("shot_action_number",None)',
    '    offset=filters.pop("shot_offset",0)',
    '    limit=filters.pop("shot_limit",20)',
    '    if with_shots or action is not None:',
    '        if engine != DEFAULT_ENGINE:',
    '            raise ValueError("SHOT_DETAIL_REQUIRES_FULL81_DEFAULT_ENGINE")',
    '        gid=filters.pop("game_id",None)',
    '        if filters:raise ValueError("SHOT_DETAIL_CANNOT_MIX_OTHER_FILTERS")',
    '        from query_igp81_full_shot_detail_v1 import query as shot_query',
    '        return shot_query(root,gid,action,offset,limit)',
    '    if engine == DEFAULT_ENGINE:'))
if 'from query_igp81_full_shot_detail_v1 import query as shot_query' not in source:
    assert source.count(anchor)==1,"DEFAULT_ENGINE_QUERY_ANCHOR_MOVED"
    source=source.replace(anchor,replacement)
parser_anchor='    p.add_argument("--summary-only", action="store_true")'
if 'p.add_argument("--shots",' not in source:
    assert source.count(parser_anchor)==1
    source=source.replace(parser_anchor,parser_anchor+'\n'+"\n".join((
        '    p.add_argument("--shots", action="store_true")',
        '    p.add_argument("--shot-action-number", type=int)',
        '    p.add_argument("--shot-offset", type=int, default=0)',
        '    p.add_argument("--shot-limit", type=int, default=20)')))
anchor='    if args.start_utc_ms is not None:\n        if not args.game_id:'
if 'shot details and time-bounded native scenes are separate' not in source:
    assert source.count(anchor)==1
    source=source.replace(anchor,
         '    if args.start_utc_ms is not None:\n'
         '        if args.shots or args.shot_action_number is not None:\n'
         '            p.error("shot details and time-bounded native scenes are separate")\n'
         '        if not args.game_id:')
anchor="\n".join((
    '    else:',
    '        result = query(args.root, game_id=args.game_id, team=args.team,',
    '                       engine=args.engine,',
    '                       include_team_game_rows=not args.summary_only)',
    '    print(json.dumps(result, sort_keys=True))'))
replacement="\n".join((
    '    else:',
    '        if args.shots or args.shot_action_number is not None:',
    '            if not args.game_id or args.team is not None:',
    '                p.error("shot details need --game-id, not --team")',
    '            result=query(args.root,game_id=args.game_id,engine=args.engine,',
    '                         include_shots=True,shot_action_number=args.shot_action_number,',
    '                         shot_offset=args.shot_offset,shot_limit=args.shot_limit)',
    '        else:',
    '            result = query(args.root, game_id=args.game_id, team=args.team,',
    '                           engine=args.engine,',
    '                           include_team_game_rows=not args.summary_only)',
    '    print(json.dumps(result, sort_keys=True))'))
if 'shot details need --game-id, not --team' not in source:
    assert source.count(anchor)==1,"DEFAULT_ENGINE_CLI_ANCHOR_MOVED"
    source=source.replace(anchor,replacement)
path.write_text(source)
print("IGP81_DEFAULT_QUERY_SHOT_ROUTE_PATCHED_WITH_TRACKING_STATISTICS_UNCHANGED")
