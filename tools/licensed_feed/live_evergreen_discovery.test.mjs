import assert from 'node:assert/strict';
import {test} from 'node:test';
import {NBA_GAME_ID,activeGames,MAX_SIMULTANEOUS} from './live_evergreen_discovery.mjs';
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
