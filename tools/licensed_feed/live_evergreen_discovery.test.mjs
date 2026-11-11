import assert from 'node:assert/strict';
import {test} from 'node:test';
import {NBA_GAME_ID,activeGames,MAX_SIMULTANEOUS,sourceBackfillCandidates,officialFinalFromBoxscore} from './live_evergreen_discovery.mjs';
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
