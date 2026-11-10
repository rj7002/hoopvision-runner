import {test} from 'node:test';
import assert from 'node:assert/strict';
import {checkJob,stats,sdkInitCanSeek} from './capture.mjs';
const j={game_id:'0022699999',account_id:'nba',program_id:'companion-0022699999-positions',start_ms:1792522800000,count:2,part:0};
test('exact window and program scoping',()=>{
 assert.equal(checkJob(j).count,2);
 assert.throws(()=>checkJob({...j,count:301}));
 assert.throws(()=>checkJob({...j,start_ms:j.start_ms+1}));
 assert.throws(()=>checkJob({...j,program_id:'other'}));
});
test('missingness remains observed',()=>{
 const rows=[{events:[{metadata:{keyframes:[{timestamp:1,positions:{a:[0],ball:[1]}},{timestamp:2,positions:{}}]}}]},{events:[]}];
 const result=stats(j,rows);
 assert.equal(result.manifest.unique_keyframes,2);
 assert.equal(result.manifest.empty_windows,1);
 assert.equal(result.manifest.frames_with_players,1);
 assert.equal(result.manifest.frames_with_ball,1);
});

test('post-final SDK late-ready handling remains strictly source gated',()=>{
 assert.equal(sdkInitCanSeek('ready'),true);
 assert.equal(sdkInitCanSeek('timeout'),true);
 assert.equal(sdkInitCanSeek('error'),false);
 assert.equal(sdkInitCanSeek(''),false);
 assert.equal(sdkInitCanSeek(undefined),false);
});

test('partial source metadata records exactly observed source slots and cannot certify completion',()=>{
 const observed=[{from:j.start_ms,events:[{metadata:{keyframes:[
  {timestamp:j.start_ms+1000,positions:{a:[1,2,3],ball:[4,5,6]}}]}}]}];
 const m=stats(j,observed).manifest;
 assert.equal(m.expected_windows,2);
 assert.equal(m.successful_windows,1);
 assert.equal(m.capture_complete,false);
 assert.deepEqual(m.source_window_starts_ms,[j.start_ms]);
 assert.equal(m.observed,true);
 assert.equal(m.imputed,false);
});
