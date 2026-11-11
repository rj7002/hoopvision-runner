import assert from 'node:assert/strict';
import {test} from 'node:test';
import {eligibleSlot,eligibleOldestSlot,validateLiveManifest,restoreOriginalSourceSidecar} from './live_capture_cycle.mjs';
const tipoff=Date.parse('2026-10-23T01:30:00Z');
test('live-first selects latest elapsed slot, not oldest backlog',()=>{
 assert.equal(eligibleSlot(tipoff,tipoff+41*60000+31000),50);
});
test('live-first resumes next newest missing slot',()=>{
 const s=new Set([tipoff+40*60000]);
 assert.equal(eligibleSlot(tipoff,tipoff+41*60000+31000,s),49);
});
test('does not request an incomplete current minute',()=>{
 assert.equal(eligibleSlot(tipoff,tipoff+31000),null);
});
test('ends once all due slots are already archived',()=>{
 const s=new Set(Array.from({length:41},(_,i)=>tipoff+i*60000));
 assert.equal(eligibleSlot(tipoff,tipoff+41*60000+31000,s),null);
});

test('live-only backlog rescue finds earliest missing source minutes before end of game',()=>{
 const at=tipoff+41*60000+31000+180000;
 const set=new Set([tipoff,tipoff+2*60000]);
 assert.equal(eligibleOldestSlot(tipoff,at,set),11);
 assert.equal(eligibleSlot(tipoff,at,set)>11,true);
 assert.equal(eligibleOldestSlot(tipoff,tipoff+60000+30000+179999),null);
 assert.equal(eligibleOldestSlot(tipoff,tipoff+60000+30000+180000),10);
});
test('live-first accepts exact original full and partial five-second receipts, never confuses coverage',()=>{
 const j={game_id:'0022600208',part:1,start_ms:1794272400000,count:12};
 const m={schema:'nba-gamepulse-sdk-chunk.v1',game_id:j.game_id,part:1,
  start_ms:j.start_ms,expected_windows:12,successful_windows:8,capture_complete:false,
  source_window_starts_ms:[0,1,2,3,4,5,8,9].map(i=>j.start_ms+i*5000),
  observed:true,imputed:false,frames_with_players:7,frames_with_ball:6,empty_windows:1};
 assert.equal(validateLiveManifest(j,m),'PARTIAL_5S_SOURCE_COVERAGE');
 const full={...m,successful_windows:12,capture_complete:true,source_window_starts_ms:
  Array.from({length:12},(_,i)=>j.start_ms+i*5000)};
 assert.equal(validateLiveManifest(j,full),'FULL_5S_SOURCE_COVERAGE');
 for(const bad of [{...m,successful_windows:12},{...m,imputed:true},
  {...m,source_window_starts_ms:[...m.source_window_starts_ms.slice(0,7),m.source_window_starts_ms[0]]},
  {...m,source_window_starts_ms:[...m.source_window_starts_ms.slice(0,7),j.start_ms+60000]},
  {...m,source_window_starts_ms:m.source_window_starts_ms.slice(1)}])
  assert.throws(()=>validateLiveManifest(j,bad));
});

test('an interrupted private archive upload is repaired from exact original 5s rows only',()=>{
 const from=1794272400000,job={game_id:'0022600208',part:1,start_ms:from,count:12};
 const rows=Array.from({length:12},(_,i)=>({from:from+i*5000,to:from+i*5000+4999,events:[]}));
 const base={schema:'nba-gamepulse-sdk-chunk.v1',game_id:job.game_id,
  part:job.part,start_ms:from,successful_windows:12,
  frames_with_players:0,frames_with_ball:0,empty_windows:12,
  observed:true,imputed:false};
 const digest='a'.repeat(64);
 const ready=restoreOriginalSourceSidecar(job,base,rows,digest,'FULL_5S_SOURCE_COVERAGE');
 assert.equal(ready.capture_complete,true);
 assert.equal(ready.archive_sha256,digest);
 assert.deepEqual(ready.source_window_starts_ms,rows.map(x=>x.from));
 const partial=restoreOriginalSourceSidecar(job,{...base,successful_windows:8,empty_windows:8},
  rows.slice(0,8),digest,'PARTIAL_5S_SOURCE_COVERAGE');
 assert.equal(partial.successful_windows,8);
 assert.equal(partial.capture_complete,false);
 assert.throws(()=>restoreOriginalSourceSidecar(job,base,rows.slice(1),digest,'FULL_5S_SOURCE_COVERAGE'));
 assert.throws(()=>restoreOriginalSourceSidecar(job,base,rows,digest,'PARTIAL_5S_SOURCE_COVERAGE'));
 assert.throws(()=>restoreOriginalSourceSidecar(job,base,[...rows.slice(0,11),
  {...rows[11],to:rows[11].to-1}],digest,'FULL_5S_SOURCE_COVERAGE'));
 assert.throws(()=>restoreOriginalSourceSidecar(job,base,rows,'bad','FULL_5S_SOURCE_COVERAGE'));
});
