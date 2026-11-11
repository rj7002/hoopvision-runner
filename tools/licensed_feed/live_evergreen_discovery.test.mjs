import assert from 'node:assert/strict';
import {test} from 'node:test';
import {NBA_GAME_ID,activeGames,MAX_SIMULTANEOUS,sourceBackfillCandidates,officialFinalFromBoxscore,officialFinalFromSchedule,postfinalWindowDecision,finalWatchPollMs,watchAndCaptureOnFinal} from './live_evergreen_discovery.mjs';
const now=Date.parse('2026-11-11T02:00:00.000Z');
const row=(id,min,status=2)=>({gameId:id,gameDateTimeUTC:new Date(now+min*60000).toISOString(),gameStatus:status});
const wrap=(games)=>({leagueSchedule:{gameDates:[{games}]}});
test('discovers concurrent NBA games from current official schedule without hardcoded game IDs',()=>{
 const a=activeGames(wrap([row('0022600211',-90),row('0022600212',-60),row('0022600213',0),row('0022600214',0),row('0022600215',60,1)]),now);
 assert.deepEqual(a.map(x=>x.id),['0022600211','0022600212','0022600213','0022600214']);
});
test('arms future games eight minutes before tipoff',()=>{
 assert.deepEqual(activeGames(wrap([row('0022700001',8,1)]),now).map(x=>x.id),['0022700001']);
 assert.deepEqual(activeGames(wrap([row('0022700001',9,1)]),now),[]);
});
test('supports a new season and NBA playoff game identifiers',()=>{
 const ids=['0022700001','0042700012','0012700002','0052700003','0032700004'];
 for(const id of ids)assert.equal(NBA_GAME_ID.test(id),true);
 assert.equal(activeGames(wrap(ids.map(x=>row(x,0))),now).length,5);
});
test('does not recycle games after end of official live observation window',()=>{
 assert.deepEqual(activeGames(wrap([row('0022600211',-361,3),row('0022600212',-300,3)]),now).map(x=>x.id),['0022600212']);
});
test('fails closed on corrupted schedule, invalid clock or exceeding NBA slate limit',()=>{
 assert.throws(()=>activeGames({},now),/schema_changed/);
 assert.throws(()=>activeGames(wrap([]),Infinity),/invalid_clock/);
 const tooMany=Array.from({length:MAX_SIMULTANEOUS+1},(_,i)=>row('002270'+String(i).padStart(4,'0'),0));
 assert.throws(()=>activeGames(wrap(tooMany),now),/concurrent_game_limit/);
});

test('official final signal is exact-game, genuine status 3, and fail-closed',()=>{
 assert.equal(officialFinalFromBoxscore('0022600212',{game:{gameId:'0022600212',gameStatus:3}}),true);
 assert.equal(officialFinalFromBoxscore('0022600212',{game:{gameId:'0022600212',gameStatus:'2'}}),false);
 assert.equal(officialFinalFromBoxscore('0022600212',{game:{gameId:'0022600211',gameStatus:3}}),null);
 assert.equal(officialFinalFromBoxscore('0022600212',{}),null);
 assert.throws(()=>officialFinalFromBoxscore('BAD',{game:{gameId:'BAD',gameStatus:3}}),/invalid_nba_game_id/);
});
test('pre-final recovery uses only past original SDK slots and skips observed or attempted windows',()=>{
 const start=Date.parse('2026-11-11T01:00:00Z'), observed=new Set([start-600000,start-595000]);
 const attempted=new Set([start-590000]);
 const selected=sourceBackfillCandidates({tipoff:start,now:start+60000,observed,attempted,limit:5});
 assert.deepEqual(selected,[start-585000,start-580000,start-575000,start-570000,start-565000]);
 assert(selected.every(x=>x%5000===0&&x+5000<=start+60000-10000));
});
test('prioritises source-backed final-whistle tail then older gaps; no fabricated positions',()=>{
 const start=Date.parse('2026-11-11T01:00:00Z');
 const seen=new Set(),attempted=new Set();
 const now=start+150*60000;
 const result=sourceBackfillCandidates({tipoff:start,now,observed:seen,attempted,limit:6,final:true});
 assert.equal(result.length,6);
 assert.deepEqual(result,[now-20000,now-25000,now-30000,now-35000,now-40000,now-45000]);
 for(const ms of result)attempted.add(ms);
 const next=sourceBackfillCandidates({tipoff:start,now,observed:seen,attempted,limit:2,final:true});
 assert.deepEqual(next,[now-50000,now-55000]);
});
test('invalid source-window selection fails closed',()=>{
 const start=Date.parse('2026-11-11T01:00:00Z');
 assert.throws(()=>sourceBackfillCandidates({tipoff:start,now:Infinity,observed:new Set(),attempted:new Set()}),/invalid_backfill_plan/);
 assert.throws(()=>sourceBackfillCandidates({tipoff:start,now:start,observed:[],attempted:new Set()}),/invalid_backfill_plan/);
 assert.throws(()=>sourceBackfillCandidates({tipoff:start,now:start,observed:new Set(),attempted:new Set(),limit:1000}),/invalid_backfill_plan/);
});

test('bounded postfinal observation remains inside the same authorised SDK session',()=>{
 const final=Date.parse('2026-11-11T03:45:00Z');
 const grade=(ms,last=null,disabled=null)=>postfinalWindowDecision({
  finalSeenAt:final,now:final+ms,disabledAt:disabled,lastSourceAt:last
 });
 assert.equal(grade(0,final),'CONTINUE_AUTHENTIC_SOURCE');
 assert.equal(grade(180000,final+150000),'CONTINUE_AUTHENTIC_SOURCE');
 assert.equal(grade(14*60000,final+13*60000),'CONTINUE_AUTHENTIC_SOURCE');
 assert.equal(grade(14*60000,final+9*60000),'STOP_SOURCE_QUIET');
 assert.equal(grade(2*60000,final+2*60000,final+119000),'STOP_SOURCE_DISABLED');
 assert.equal(grade(20*60000,final+19*60000),'STOP_WINDOW_HARD_CAP');
 assert.throws(()=>grade(-1,final),/invalid_postfinal_timing/);
});

test('official schedule fallback only accepts exact game and final status',()=>{
 const date=Date.parse('2026-11-11T04:00:00Z');
 const schedule=wrap([row('0022600212',0,3),row('0022600211',0,2)]);
 assert.equal(officialFinalFromSchedule('0022600212',schedule),true);
 assert.equal(officialFinalFromSchedule('0022600211',schedule),false);
 assert.equal(officialFinalFromSchedule('0022600213',schedule),null);
 assert.equal(officialFinalFromSchedule('0022600212',{}),null);
 assert.throws(()=>officialFinalFromSchedule('wrong',schedule),/invalid_nba_game_id/);
});


test('fresh FINAL watcher triggers collector immediately on exact official final',async()=>{
 const id='0022700010';
 let clock=Date.parse('2027-01-10T02:20:00Z'),calls=0,launches=0;
 const start=clock-120*60000;
 const seen=[];
 const request=async url=>{
  seen.push(url);
  calls++;
  return {ok:true,json:async()=>({game:{
   gameId:id,gameStatus:calls>=3?3:2
  }})};
 };
 const code=await watchAndCaptureOnFinal({
  gameId:id,tipoff:start,request,now:()=>clock,
  pause:async ms=>{clock+=ms;},
  launch:async()=>{launches++;return 0;}
 });
 assert.equal(code,0);
 assert.equal(launches,1);
 assert.equal(calls,3);
 assert.equal(clock,Date.parse('2027-01-10T02:20:10Z'));
 assert(seen.every(x=>x.includes('boxscore_'+id)));
});

test('exact game ID is mandatory for FINAL; mismatched status cannot trigger a capture',async()=>{
 const id='0022700011';
 const tipoff=Date.parse('2027-01-10T01:00:00Z');
 let clock=tipoff+6*3600000,launches=0;
 const request=async url=>({ok:url.includes('boxscore_'),
  json:async()=>({game:{gameId:'0022700012',gameStatus:3}})});
 await assert.rejects(
  watchAndCaptureOnFinal({gameId:id,tipoff,request,now:()=>clock,
   pause:async ms=>{clock+=ms;},
   launch:async()=>{launches++;return 0;}
  }),/official_final_not_observed/);
 assert.equal(launches,0);
});

test('official schedule is an acceptable exact-game FINAL fallback when boxscore is unavailable',async()=>{
 const id='0042700010',tipoff=Date.parse('2027-05-20T01:00:00Z');
 let clock=tipoff+150*60000,launches=0;
 const request=async url=>url.includes('boxscore_')?
  {ok:false}:{ok:true,json:async()=>({leagueSchedule:{gameDates:[{games:[{
   gameId:id,gameStatus:3
  }]}]}})};
 const code=await watchAndCaptureOnFinal({
  gameId:id,tipoff,request,now:()=>clock,pause:async()=>{},
  launch:async()=>{launches++;return 0;}
 });
 assert.equal(code,0);
 assert.equal(launches,1);
});

test('completion monitor polls rapidly around game end without an inferred FINAL',()=>{
 const start=Date.parse('2027-01-10T01:00:00Z');
 assert.equal(finalWatchPollMs(start,start+99*60000),20000);
 assert.equal(finalWatchPollMs(start,start+100*60000),5000);
 assert.throws(()=>finalWatchPollMs(NaN,Date.now()),/invalid_final_watch_clock/);
});
