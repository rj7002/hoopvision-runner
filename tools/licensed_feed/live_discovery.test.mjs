import assert from 'node:assert/strict';import {test} from 'node:test';
import {activeGames} from './live_discovery.mjs';
const t=Date.parse('2026-10-24T00:00:00Z');
const doc={leagueSchedule:{gameDates:[{games:[
 {gameId:'0022600010',gameStatus:2,gameDateTimeUTC:new Date(t-40*60000).toISOString()},
 {gameId:'0022600011',gameStatus:2,gameDateTimeUTC:new Date(t-90*60000).toISOString()},
 {gameId:'0022600012',gameStatus:3,gameDateTimeUTC:new Date(t-190*60000).toISOString()},
 {gameId:'0022600013',gameStatus:1,gameDateTimeUTC:new Date(t+70*60000).toISOString()},
 {gameId:'0022600014',gameStatus:3,gameDateTimeUTC:new Date(t-11*3600000).toISOString()},
 {gameId:'0022500042',gameStatus:2,gameDateTimeUTC:new Date(t).toISOString()}
]}]}};
test('multi-game selection contains all concurrent live and recent finals without next game',()=>{
 const r=activeGames(doc,t);
 assert.deepEqual(new Set(r.map(x=>x.id)),new Set(['0022600010','0022600011','0022600012']));
});
test('never include a future game just because it is status 2',()=>{
 const d={leagueSchedule:{gameDates:[{games:[{gameId:'0022600015',gameStatus:2,gameDateTimeUTC:new Date(t+3600000).toISOString()}]}]}};
 assert.equal(activeGames(d,t).length,0);
});
test('changed upstream schedule fails closed',()=>{
 assert.throws(()=>activeGames({},t),/schema/);
});

test('preflight arms official scheduled games 30m before tipoff but not before that',()=>{
 const id='0022600199',start=t+30*60000;
 const d={leagueSchedule:{gameDates:[{games:[{gameId:id,gameStatus:1,
  gameDateTimeUTC:new Date(start).toISOString()}]}]}};
 assert.deepEqual(activeGames(d,t).map(g=>g.id),[id]);
 assert.equal(activeGames(d,t-1).length,0);
});

test('live-first scheduler does not recycle stale final programmes for hours',()=>{
 const oldFinal={leagueSchedule:{gameDates:[{games:[
  {gameId:'0022600208',gameStatus:3,gameDateTimeUTC:new Date(t-7*3600000).toISOString()},
  {gameId:'0022600209',gameStatus:3,gameDateTimeUTC:new Date(t-4*3600000).toISOString()},
  {gameId:'0022600210',gameStatus:2,gameDateTimeUTC:new Date(t-90*60000).toISOString()}
 ]}]}};
 assert.deepEqual(new Set(activeGames(oldFinal,t).map(g=>g.id)),
  new Set(['0022600209','0022600210']));
});
