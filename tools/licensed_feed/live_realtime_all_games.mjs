/**
 * Original NBA player/ball positions captured as the game unfolds.
 * Store ONLY SDK-observed authenticated slot responses in protected private Git and, if needed, private Release assets.
 * Live-first original collection plus bounded SDK-native historical seeks while the\n * authorised in-game session is active; no token replay, disabled-app bypass,\n * extrapolation, or fabricated XYZ. Sources and audit receipts remain private.
 */
import puppeteer from 'puppeteer-core';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdtempSync,rmSync,mkdirSync,chmodSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync,execFile,spawnSync} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {sourceBackfillCandidates,officialFinalFromBoxscore,officialFinalFromSchedule,postfinalWindowDecision} from './live_evergreen_discovery.mjs';
import {slotRequestUrl} from './sdk_slot.mjs';
import {planGame} from './season_core.mjs';

const ROOT=import.meta.dirname;
const GAME=process.env.GAMEPULSE_LIVE_ID;
const START=Date.parse(process.env.GAMEPULSE_LIVE_TIPOFF||'');
const PUBLIC_REPO='rj7002/hoopvision-runner';
const REPO=process.env.GAMEPULSE_PRIVATE_DATA_REPO;
const TOKEN=process.env.GH_TOKEN;
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
const CAPTURE_MS=Number(process.env.IGP_REALTIME_CAPTURE_MS||185000);
const LIVE_STOP_MS=Number(process.env.IGP_REALTIME_LIVE_STOP_MS||300*60000);
const PRETIPOFF_WAIT_MS=Number(process.env.IGP_REALTIME_PRETIPOFF_WAIT_MS||0);
const FLUSH_MS=Number(process.env.IGP_REALTIME_FLUSH_MS||40000);
const sha=b=>createHash('sha256').update(b).digest('hex');
const gitExec=promisify(execFile);
const PRIVATE_BRANCH=process.env.GAMEPULSE_PRIVATE_DATA_BRANCH||'main';
const PRIVATE_BASE='gamepulse/fusion/live_original_'+new Date(START).toISOString().slice(0,10).replaceAll('-','')+'/'+GAME;
let privateGit=null;
async function git(args,{cwd,timeout=90000}={}){
 const env={...process.env,GH_TOKEN:TOKEN,GIT_TERMINAL_PROMPT:'0',GIT_ASKPASS:privateGit?.askpass};
 return gitExec('git',args,{cwd,env,timeout,maxBuffer:1024*1024});
}
async function initPrivateGit(){
 if(privateGit)return privateGit;
 const dir=mkdtempSync(join(tmpdir(),'igp-private-git-'));
 const askpass=join(dir,'askpass.sh');
 writeFileSync(askpass,'#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token\\n";; *Password*) printf "%s\\n" "$GH_TOKEN";; *) exit 1;; esac\n');
 chmodSync(askpass,0o700);
 privateGit={dir,askpass,root:join(dir,'private')};
 try{
  await git(['clone','-q','--filter=blob:none','--depth=1','--sparse','-b',PRIVATE_BRANCH,
   'https://github.com/'+REPO+'.git',privateGit.root],{timeout:110000});
  await git(['sparse-checkout','set',PRIVATE_BASE],{cwd:privateGit.root});
  await git(['config','user.name','github-actions[bot]'],{cwd:privateGit.root});
  await git(['config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],{cwd:privateGit.root});
  console.log('IGP_PRIVATE_GIT_SOURCE_STORAGE_READY',GAME);
  return privateGit;
 }catch(e){rmSync(dir,{recursive:true,force:true});privateGit=null;throw e;}
}
async function savePrivateGit(base,zipped,meta){
 const state=await initPrivateGit();
 const target=join(state.root,PRIVATE_BASE);
 mkdirSync(target,{recursive:true});
 const one=PRIVATE_BASE+'/'+base+'.jsonl.gz',two=PRIVATE_BASE+'/'+base+'.json';
 writeFileSync(join(state.root,one),zipped);
 writeFileSync(join(state.root,two),Buffer.from(JSON.stringify(meta)+'\n'));
 await git(['add','-f','--',one,two],{cwd:state.root});
 const staged=await git(['diff','--cached','--name-only'],{cwd:state.root});
 if(staged.stdout.trim())await git(['commit','-q','-m','data(igp): immutable realtime SDK XYZ '+GAME+' '+base],{cwd:state.root});
 for(let attempt=0;attempt<8;attempt++){
  try{
   await git(['fetch','-q','origin',PRIVATE_BRANCH],{cwd:state.root});
   // A second live CPU observer may have already uploaded the identical
   // original gzip. Accept only a byte-identical, SHA-verified private copy;
   // a different metadata observation time is not a source conflict.
   let priorBlob=null,priorMeta=null;
   try{
    priorBlob=execFileSync('git',['show','FETCH_HEAD:'+one],{cwd:state.root,maxBuffer:16*1024*1024,timeout:20000});
    priorMeta=JSON.parse(execFileSync('git',['show','FETCH_HEAD:'+two],{cwd:state.root,maxBuffer:1024*1024,timeout:20000}).toString('utf8'));
   }catch{}
   if(priorBlob){
    if(sha(priorBlob)!==sha(zipped)||priorMeta?.original_blob_sha256!==sha(zipped)
      ||priorMeta?.game_id!==GAME)throw Error('private_source_same_key_sha_conflict');
    await git(['reset','--hard','FETCH_HEAD'],{cwd:state.root});
    console.log('IGP_PRIVATE_GIT_EXISTING_REMOTE_SHA_READBACK',GAME,base,sha(zipped));
    return;
   }
   await git(['rebase','-q','FETCH_HEAD'],{cwd:state.root});
   await git(['push','-q','origin','HEAD:refs/heads/'+PRIVATE_BRANCH],{cwd:state.root});
   await git(['fetch','-q','origin',PRIVATE_BRANCH],{cwd:state.root});
   const verifyBlob=execFileSync('git',['show','FETCH_HEAD:'+one],{cwd:state.root,maxBuffer:16*1024*1024,timeout:90000});
   const verifyMeta=execFileSync('git',['show','FETCH_HEAD:'+two],{cwd:state.root,maxBuffer:1024*1024,timeout:90000});
   if(sha(verifyBlob)!==sha(zipped)||sha(verifyMeta)!==sha(Buffer.from(JSON.stringify(meta)+'\n')))
    throw Error('private_source_sha_readback_failed');
   console.log('IGP_PRIVATE_GIT_REMOTE_SHA_READBACK',GAME,base,sha(zipped));
   return;
  }catch(e){
   // Independent per-game files are safe to rebase after competing writers.
   try{await git(['rebase','--abort'],{cwd:state.root});}catch{}
   await sleep(1000*(attempt+1));
  }
 }
 throw Error('private_git_push_exhausted');
}

/** Persist access-window evidence privately for repeated cross-game tests.
 * Contains UTC metadata and counts ONLY; no SDK URLs, tokens or native XYZ.
 * Independent immutable SHA filename prevents concurrent source overwrite.
 */
async function savePrivateFinalWindowReceipt(report){
 const state=await initPrivateGit();
 const body=Buffer.from(JSON.stringify(report,null,2)+'\n');
 const digest=sha(body);
 const rel=PRIVATE_BASE+'/access-window-'+digest.slice(0,24)+'.json';
 mkdirSync(join(state.root,PRIVATE_BASE),{recursive:true});
 writeFileSync(join(state.root,rel),body);
 await git(['add','-f','--',rel],{cwd:state.root});
 const staged=await git(['diff','--cached','--name-only'],{cwd:state.root});
 if(staged.stdout.trim())await git(['commit','-q','-m','data(igp): immutable NBA postfinal source-access evidence '+GAME],{cwd:state.root});
 for(let attempt=0;attempt<8;attempt++){
  try{
   await git(['fetch','-q','origin',PRIVATE_BRANCH],{cwd:state.root});
   let prior=null;
   try{prior=execFileSync('git',['show','FETCH_HEAD:'+rel],
    {cwd:state.root,maxBuffer:1024*1024,timeout:20000});}catch{}
   if(prior){
    if(sha(prior)!==digest)throw Error('private_final_window_evidence_conflict');
    console.log('IGP_FINAL_WINDOW_PRIVATE_EVIDENCE_SHA_VERIFIED',GAME,digest);
    return;
   }
   await git(['rebase','-q','FETCH_HEAD'],{cwd:state.root});
   await git(['push','-q','origin','HEAD:refs/heads/'+PRIVATE_BRANCH],{cwd:state.root});
   await git(['fetch','-q','origin',PRIVATE_BRANCH],{cwd:state.root});
   const readback=execFileSync('git',['show','FETCH_HEAD:'+rel],
    {cwd:state.root,maxBuffer:1024*1024,timeout:30000});
   if(sha(readback)!==digest)throw Error('private_final_window_evidence_sha_failed');
   console.log('IGP_FINAL_WINDOW_PRIVATE_EVIDENCE_SHA_VERIFIED',GAME,digest);
   return;
  }catch{
   try{await git(['rebase','--abort'],{cwd:state.root});}catch{}
   await sleep(750*(attempt+1));
  }
 }
 throw Error('private_final_window_evidence_commit_unavailable');
}

async function gh(args){
 // Never block SDK response handlers when GitHub private storage is throttled.
 const {stdout}=await gitExec('gh',args,{encoding:'utf8',timeout:60000,maxBuffer:4*1024*1024,
  env:{...process.env,GH_TOKEN:TOKEN}});
 return stdout;
}
async function ensureRelease(tag){
 try{await gh(['release','view',tag,'--repo',REPO,'--json','tagName']);return;}
 catch{}
 try{await gh(['release','create',tag,'--repo',REPO,'--target','main','--title',tag,
  '--notes','Private authorised live NBA original player-ball source','--latest=false']);}
 catch{await gh(['release','view',tag,'--repo',REPO,'--json','tagName']);}
}
function chrome(){
 for(const name of ['google-chrome','google-chrome-stable','chromium']){
  try{return execFileSync('which',[name],{encoding:'utf8'}).trim();}catch{}
 }
 throw Error('chromium_unavailable');
}
function countSource(rows){
 const ts=new Map(),windows=new Set();
 for(const row of rows){
  windows.add(row.from);
  for(const ev of row.events){
   for(const f of ev?.metadata?.keyframes||[]){
    if(!Number.isSafeInteger(f?.timestamp))continue;
    const p=Object.keys(f?.positions||{}),old=ts.get(f.timestamp)||{player:false,ball:false};
    ts.set(f.timestamp,{player:old.player||p.some(k=>k!=='ball'),ball:old.ball||p.includes('ball')});
   }
  }
 }
 const frames=[...ts.values()];
 return {source_windows:windows.size,source_responses:rows.length,
  native_timestamps:frames.length,player_timestamps:frames.filter(f=>f.player).length,
  ball_timestamps:frames.filter(f=>f.ball).length,
  player_and_ball_timestamps:frames.filter(f=>f.player&&f.ball).length};
}
async function uploadedAndReadback(tag,name,data,dir){
 const path=join(dir,name),verify=join(dir,'readback');
 writeFileSync(path,data);
 try{await gh(['release','upload',tag,path,'--repo',REPO]);}
 catch{console.log('IGP_SOURCE_ARCHIVE_ALREADY_PRESENT_RECHECK',name.slice(0,30));}
 await gh(['release','download',tag,'--repo',REPO,'--pattern',name,'--dir',verify]);
 if(sha(readFileSync(join(verify,name)))!==sha(data))throw Error('private_source_sha_readback_failed');
}
async function main(){
if(process.env.GITHUB_REPOSITORY!==PUBLIC_REPO
  ||process.env.GITHUB_REF!=='refs/heads/main'
  ||!['schedule','workflow_dispatch','push'].includes(process.env.GITHUB_EVENT_NAME)
  ||!/^\w[\w.-]*\/[\w.-]+$/.test(REPO||'')
  ||!/^00[1-5]\d{7}$/.test(GAME||'')||!Number.isSafeInteger(START)
  ||!TOKEN||TOKEN.length<30)throw Error('unauthorized_live_collection');
 if(!Number.isSafeInteger(CAPTURE_MS)||CAPTURE_MS<30000||CAPTURE_MS>19200000
   ||!Number.isSafeInteger(LIVE_STOP_MS)||LIVE_STOP_MS<600000||LIVE_STOP_MS>21000000
  ||!Number.isSafeInteger(PRETIPOFF_WAIT_MS)||PRETIPOFF_WAIT_MS<0||PRETIPOFF_WAIT_MS>14400000
  ||!Number.isSafeInteger(FLUSH_MS)||FLUSH_MS<20000||FLUSH_MS>180000)throw Error('invalid_live_duration');
 let now=Date.now();
 if(now<START-2*60000&&PRETIPOFF_WAIT_MS>0){
   if(START-2*60000-now>PRETIPOFF_WAIT_MS)throw Error('pregame_wait_exceeds_limit');
   console.log('IGP_LIVE_WAIT_FOR_TIPOFF',GAME,START);
   while(Date.now()<START-2*60000)await sleep(Math.min(30000,Math.max(1000,START-2*60000-Date.now())));
   now=Date.now();
 }
 if(now<START-2*60000||now>START+LIVE_STOP_MS){
  console.log('REALTIME_OUTSIDE_SOURCE_WINDOW',GAME);return;
 }
 // Keep GitHub storage secrets away from the browser and SDK bundle.
 delete process.env.GH_TOKEN;
 await build({entryPoints:[join(ROOT,'browser.js')],bundle:true,platform:'browser',
  format:'iife',outfile:join(ROOT,'bundle.js'),logLevel:'silent'});
 const server=createServer((req,res)=>{
  const file=req.url==='/'?'index.html':req.url==='/bundle.js'?'bundle.js':null;
  if(!file){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':'text/html');
  res.end(readFileSync(join(ROOT,file)));
 });
 await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 const seen=new Set(),pending=new Set(),buffer=new Map(),sourceResponseMetadata=new Map();
 const observedSlots=new Set(),observedPlayerBallSlots=new Set(),attemptedBackfill=new Set();
 const tag='gamepulse-live-sdk-'+GAME;
 let browser,saved=0,playerFrames=0,ballFrames=0;
 let storeQueue=Promise.resolve(),storageRetries=0,lastSdkResponse=Date.now(),lastLiveXYZ=0,seekErrors=0,acceptResponses=true;
 let postFinalOriginalResponses=0,postFinalPlayerBallResponses=0, firstOriginalAt=null,lastOriginalAt=null,disabledAt=null;
 let finalObservedAt=null,observedSdkIssuedSlotUrl=null;
 let signedDrainPromise=null,signedDrainActive=false,signedDrainStop=false,sourceDeniedAt=null;
 let signedOriginalSuccessful=0,signedOriginalPlayerBall=0,signedOriginalAttempts=0;
 let sourceBackfillAttempts=0,postFinalBackfillAttempts=0,sourceBackfillObserved=0;
 let finalAttemptedReset=false;
 const FIRST_RECOVERY_MINUTE=45, BACKFILL_LIMIT=36;
 const FINAL_POLL_MS=10000, BACKFILL_INTERVAL_MS=24000;
 // Source observation continues while private SHA uploads run in serialized background.
 function flush(){
  const entries=[...buffer.entries()].sort((a,b)=>a[1].from-b[1].from);
  if(!entries.length)return storeQueue;
  for(const [key] of entries)buffer.delete(key);
  const write=async()=>{
   const rows=entries.map(e=>e[1]),stats=countSource(rows);
   const receivedTimes=entries.map(e=>sourceResponseMetadata.get(e[0])?.received_at_ms)
     .filter(Number.isSafeInteger);
   const postFinalResponses=entries.filter(e=>
     sourceResponseMetadata.get(e[0])?.official_final_verified_before_receipt===true).length;
   if(receivedTimes.length!==entries.length)throw Error('sdk_source_observation_time_missing');
  const zipped=gzipSync(Buffer.from(rows.map(r=>JSON.stringify(r)).join('\n')+'\n'));
  const digest=sha(zipped);
  const base='realtime-'+GAME+'-'+rows[0].from+'-'+digest.slice(0,16);
  const meta={schema:'igp.original-sdk-realtime-response.v1',game_id:GAME,
   original_source_grade:'SDK_OBSERVED_NOT_FULLGAME',
   source_observed_at_utc:new Date().toISOString(),
   first_actual_sdk_http_response_at_utc:new Date(Math.min(...receivedTimes)).toISOString(),
   last_actual_sdk_http_response_at_utc:new Date(Math.max(...receivedTimes)).toISOString(),
   sdk_http_responses_after_verified_official_final:postFinalResponses,
   sdk_source_methods:Object.fromEntries([...new Set(entries.map(e=>
    sourceResponseMetadata.get(e[0])?.original_sdk_method||'UNKNOWN'))].map(method=>[
    method,entries.filter(e=>sourceResponseMetadata.get(e[0])?.original_sdk_method===method).length])),...stats,
   original_blob_sha256:digest,imputed:false,physical_possessions_certified:0};
  const dir=mkdtempSync(join(tmpdir(),'igp-live-original-'));
  try{
   let persisted=false;
   try{await savePrivateGit(base,zipped,meta);persisted=true;}
   catch(e){console.log('IGP_PRIVATE_GIT_SOURCE_RETRY_REQUIRED',GAME,e?.code||'TRANSIENT');}
   if(!persisted){
    try{
     await ensureRelease(tag);
     await uploadedAndReadback(tag,base+'.jsonl.gz',zipped,dir);
     await uploadedAndReadback(tag,base+'.json',Buffer.from(JSON.stringify(meta)+'\n'),dir);
     persisted=true;
    }catch(e){console.log('IGP_PRIVATE_RELEASE_SOURCE_RETRY_REQUIRED',GAME);}
   }
   if(!persisted){
    for(const [key,value] of entries)if(!buffer.has(key))buffer.set(key,value);
    throw Error('private_source_unpersisted');
   }
   for(const [key] of entries)sourceResponseMetadata.delete(key);
   saved+=stats.source_responses;playerFrames+=stats.player_timestamps;ballFrames+=stats.ball_timestamps;
   console.log('IGP_REALTIME_ORIGINAL_SOURCE_SHA_READBACK',JSON.stringify({
    game_id:GAME,...stats,archive_sha256:digest}));
  }finally{rmSync(dir,{recursive:true,force:true});}
  };
  // Single writer per game; rebase conflicts cannot pause the live SDK seeker.
  storeQueue=storeQueue.then(write).catch(e=>{
   storageRetries++;
   console.error('IGP_LIVE_PRIVATE_STORAGE_RETRY_REQUIRED',GAME,e?.message||'private_storage_error');
  });
  return storeQueue;
 }
 try{
  browser=await puppeteer.launch({headless:true,executablePath:chrome(),
   args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage();
  // Both the browser and bounded signed-session backfill use this one source
  // preservation path. Only original SDK event arrays can enter private Git.
  function observeOriginalSlot(from,events,method='SDK_BROWSER_SOURCE'){
    if(!acceptResponses||!Array.isArray(events)||!Number.isSafeInteger(from)
      ||from%5000!==0||from<START-20*60000||from>START+LIVE_STOP_MS)return false;
    const observedNow=Date.now();
    lastSdkResponse=observedNow;
    firstOriginalAt??=observedNow;
    lastOriginalAt=observedNow;
    observedSlots.add(from);
    if(finalObservedAt!==null&&observedNow>=finalObservedAt)postFinalOriginalResponses++;
    const hasPlayerBall=events.some(ev=>(ev?.metadata?.keyframes||[]).some(frame=>{
      const keys=Object.keys(frame?.positions||{});
      return keys.includes('ball')&&keys.some(k=>k!=='ball');
    }));
    if(hasPlayerBall){
      lastLiveXYZ=observedNow;
      observedPlayerBallSlots.add(from);
      if(finalObservedAt!==null&&observedNow>=finalObservedAt)postFinalPlayerBallResponses++;
    }
    const body=JSON.stringify(events),key=from+':'+sha(body);
    if(seen.has(key))return false;
    seen.add(key);
    sourceResponseMetadata.set(key,{
      received_at_ms:observedNow,
      official_final_verified_before_receipt:finalObservedAt!==null&&observedNow>=finalObservedAt,
      original_sdk_method:method
    });
    buffer.set(key,{from,to:from+4999,events});
    return hasPlayerBall;
  }
  page.on('response',response=>{
   try{
    if(!acceptResponses)return;
    const u=new URL(response.url());
    if(response.status()!==200||u.protocol!=='https:'||
       u.hostname!=='nba-cdn.cloud.easelive.tv'||
       !u.pathname.includes('/companion-'+GAME+'-positions/')||
       !u.pathname.endsWith('/events/slot'))return;
    const from=Number(u.searchParams.get('from'));
    if(!Number.isSafeInteger(from)||from%5000!==0||
       from<START-20*60000||from>START+LIVE_STOP_MS)return;
    // Token-bearing URL remains in this running process ONLY, never logged,
    // committed, exported, or reconstructed from external credentials.
    if(u.searchParams.has('token'))observedSdkIssuedSlotUrl=response.url();
    const p=response.json().then(events=>
      observeOriginalSlot(from,events,'SDK_BROWSER_SOURCE')).catch(()=>{});
    pending.add(p);p.finally(()=>pending.delete(p));
   }catch{}
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/',
   {waitUntil:'domcontentloaded',timeout:12000});
  await page.waitForFunction(()=>typeof window.ephemeralFeed?.initialize==='function',
   {timeout:10000});
  const init=await page.evaluate(gameId=>window.ephemeralFeed.initialize({
   accountId:'nba',programId:'companion-'+gameId+'-positions',timeoutMs:20000}),GAME);
  console.log('IGP_REALTIME_SDK_INIT',GAME,init);
  if(init==='error')throw Error('sdk_initialization_failed');

  // FINAL-WHISTLE WINDOW: the official final signal is checked in the ALREADY
  // OPEN authentic SDK browser, not in queued, freshly initialized runners.
  // No authentication bypass and no signed URL replay. Only SDK player.time
  // seeks; the response handler above admits genuine HTTP-200 SDK slot arrays.
  let nextBackfill=Date.now()+BACKFILL_INTERVAL_MS;
  async function backfillObservedSource(isFinal){
    // A postfinal test may have no initial live response, but may still have
    // an authorised SDK session capable of seeking saved historical slots.
    // Attempt source reads only if this SDK has not explicitly disabled access.
    if(!lastOriginalAt&&!isFinal)return;
    if(isFinal&&signedDrainActive)return;
    const state=await page.evaluate(()=>window.ephemeralFeed.diagnostics());
    if(state?.latest_app_status==='disabled'){
      if(disabledAt===null){
        disabledAt=Date.now();
        console.log('IGP_FINAL_WINDOW_APP_DISABLED',GAME,new Date(disabledAt).toISOString());
      }
      return;
    }
    const firstFinal=isFinal&&!finalAttemptedReset;
    if(firstFinal){
      for(const ms of attemptedBackfill)if(!observedPlayerBallSlots.has(ms))attemptedBackfill.delete(ms);
      finalAttemptedReset=true;
    }
    const limit=isFinal?BACKFILL_LIMIT*2:BACKFILL_LIMIT;
    const effectiveNow=isFinal?Math.min(Date.now(),finalObservedAt+15000):Date.now();
    const selected=sourceBackfillCandidates({
      tipoff:START,now:effectiveNow,observed:observedPlayerBallSlots,
      attempted:attemptedBackfill,limit,final:isFinal
    });
    // A small stratified first-final test probes actual earlier gameplay,
    // avoiding the fallacy that empty post-buzzer slots imply historical XYZ
    // is no longer accessible. Only the genuine SDK can return observations.
    const fullGameProbes=firstFinal?
      [10,25,40,55,70,85,100,115,130,145,160,175,190,205,220,235,250]
      .map(min=>Math.floor((START+min*60000)/5000)*5000)
      .filter(ms=>ms<effectiveNow-15000&&
        !observedPlayerBallSlots.has(ms)&&!attemptedBackfill.has(ms)):[];
    const targets=[...new Set([...fullGameProbes,...selected])].slice(0,limit);
    let sent=0;
    const before=observedSlots.size;
    const richBefore=observedPlayerBallSlots.size;
    for(const ms of targets){
      if(disabledAt)break;
      attemptedBackfill.add(ms);
      const accepted=await page.evaluate(t=>window.ephemeralFeed.seek(t),ms);
      if(!accepted)break;
      sent++;
      await sleep(145);
      if(sent%12===0){
        const check=await page.evaluate(()=>window.ephemeralFeed.diagnostics());
        if(check?.latest_app_status==='disabled'){
          disabledAt??=Date.now();
          break;
        }
      }
    }
    sourceBackfillAttempts+=sent;
    if(isFinal)postFinalBackfillAttempts+=sent;
    sourceBackfillObserved+=Math.max(0,observedPlayerBallSlots.size-richBefore);
    if(sent)console.log('IGP_FINAL_WINDOW_AUTHENTIC_SEEK_QA',JSON.stringify({
      game_id:GAME,mode:isFinal?'OFFICIAL_FINAL':'LATE_LIVE',
      attempted_source_slots:sent,new_original_slot_responses:Math.max(0,observedSlots.size-before),
      new_source_player_ball_windows:Math.max(0,observedPlayerBallSlots.size-richBefore),
      previously_observed_unique_slots:before,final_observed_at_utc:
       finalObservedAt?new Date(finalObservedAt).toISOString():null,
      source_session_disabled:!!disabledAt
    }));
  }

  /** Immediate authorised post-final bulk read from an SDK-ISSUED signed slot.
   * The original SDK produces the URL; we only vary its exact 5-second times
   * through the same validated code already used by season_private_release.
   * Four simultaneous requests maximum per game. Access denial stops work.
   * No token replay after SDK disable, no guessed coordinates, no public XYZ.
   */
  async function drainSignedOriginalAtFinal(){
    if(!finalObservedAt||!observedSdkIssuedSlotUrl||disabledAt||sourceDeniedAt)return;
    signedDrainActive=true;
    const plan=planGame({id:GAME,start:START});
    if(plan.windows!==3720||plan.parts.length!==13)
      throw Error('postfinal_original_sdk_plan_invalid');
    const order=[6,5,4,3,2,1,7,0,8,9,10,11,12];
    const statuses={},deadline=finalObservedAt+16*60000;
    let denied=false,requested=0,accepted=0,rich=0,invalid=0;
    try{
      for(const part of order){
        if(signedDrainStop||denied||disabledAt||Date.now()>=deadline)break;
        const job=plan.parts[part];
        if(!job||job.count<=0)throw Error('postfinal_part_outside_sdk_plan');
        const from=job.start_ms,count=job.count;
        const todo=Array.from({length:count},(_,i)=>from+i*5000)
          .filter(t=>!observedPlayerBallSlots.has(t));
        let cursor=0;
        async function worker(){
          while(!signedDrainStop&&!denied&&!disabledAt&&Date.now()<deadline){
            const index=cursor++;
            if(index>=todo.length)return;
            const timestamp=todo[index];
            const url=slotRequestUrl(observedSdkIssuedSlotUrl,job,timestamp);
            for(let attempt=0;attempt<2;attempt++){
              if(signedDrainStop||denied||disabledAt)return;
              requested++;signedOriginalAttempts++;
              try{
                const response=await fetch(url,{signal:AbortSignal.timeout(12000),
                  headers:{Accept:'application/json',Referer:'https://www.nba.com/',
                    'User-Agent':'Mozilla/5.0 (compatible; licensed NBA source collector)'}});
                const code=response.status;
                statuses[code]=(statuses[code]||0)+1;
                if(code===401||code===403){
                  denied=true;sourceDeniedAt??=Date.now();
                  console.log('IGP_POSTFINAL_SIGNED_SDK_SOURCE_ACCESS_DENIED',GAME,code);
                  return;
                }
                if(response.ok){
                  const events=await response.json();
                  if(Array.isArray(events)){
                    const hasBall=observeOriginalSlot(timestamp,events,'SDK_ISSUED_SIGNED_ORIGINAL');
                    accepted++;signedOriginalSuccessful++;
                    if(hasBall){rich++;signedOriginalPlayerBall++;}
                    break;
                  }
                  invalid++;
                }
              }catch{statuses.network=(statuses.network||0)+1;}
              if(attempt===0)await sleep(400);
            }
          }
        }
        await Promise.all(Array.from({length:4},()=>worker()));
        void flush();
        const state=await page.evaluate(()=>window.ephemeralFeed.diagnostics());
        if(state?.latest_app_status==='disabled'){
          disabledAt??=Date.now();break;
        }
        console.log('IGP_POSTFINAL_SIGNED_SDK_PART_QA',JSON.stringify({
          game_id:GAME,part,attempts:requested,accepted_source_responses:accepted,
          rich_original_player_ball_source_windows:rich,
          observed_slot_windows:observedSlots.size,denied,invalid_bodies:invalid,
          sdk_status_denied:false
        }));
      }
    }finally{
      signedDrainActive=false;
      // Strictly aggregate/grade-only: no SDK URLs, coordinates, source rows.
      console.log('IGP_POSTFINAL_SIGNED_SDK_FINAL_QA',JSON.stringify({
        game_id:GAME,official_final_at_utc:new Date(finalObservedAt).toISOString(),
        requested,accepted,player_ball_source_windows:rich,
        unique_original_windows:observedSlots.size,
        auth_denied:denied,source_http_status_counts:statuses
      }));
    }
  }
  function startSignedDrainIfReady(){
    if(!signedDrainPromise&&finalObservedAt!==null&&
       observedSdkIssuedSlotUrl&&!disabledAt&&!sourceDeniedAt){
      signedDrainPromise=drainSignedOriginalAtFinal().catch(()=>{
        console.log('IGP_POSTFINAL_SIGNED_SDK_SOURCE_RETRY_REQUIRED',GAME);
      });
    }
  }

  let nextFinalScheduleFallback=Date.now()+30000;
  async function pollOfficialFinal(){
    if(finalObservedAt!==null)return;
    let officialState=null,source='boxscore';
    try{
      const response=await fetch('https://cdn.nba.com/static/json/liveData/boxscore/boxscore_'+GAME+'.json',{
        headers:{Accept:'application/json',Referer:'https://www.nba.com/'},
        signal:AbortSignal.timeout(7000)
      });
      if(response.ok)officialState=officialFinalFromBoxscore(GAME,await response.json());
    }catch{}
    if(officialState===null&&Date.now()>=nextFinalScheduleFallback){
      nextFinalScheduleFallback=Date.now()+30000;
      try{
        const fallback=await fetch('https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',{
          headers:{Accept:'application/json',Referer:'https://www.nba.com/'},
          signal:AbortSignal.timeout(7000)
        });
        if(fallback.ok){
          officialState=officialFinalFromSchedule(GAME,await fallback.json());
          source='schedule';
        }
      }catch{}
    }
    if(officialState!==true)return;
    finalObservedAt=Date.now();
    console.log('IGP_OFFICIAL_FINAL_FIRST_OBSERVED',JSON.stringify({
      game_id:GAME,authoritative_status_source:source,
      observed_at_utc:new Date(finalObservedAt).toISOString(),
      last_authenticated_slot_utc:lastOriginalAt?new Date(lastOriginalAt).toISOString():null,
      source_armed_before_final:lastOriginalAt!==null
    }));
    // Trigger from this already-open SDK session before an external runner
    // could queue. The bounded signed-source drain is preferred over serial seeks.
    startSignedDrainIfReady();
    if(!signedDrainActive){
      try{await backfillObservedSource(true);}
      catch{console.log('IGP_FIRST_FINAL_SEEK_TRANSIENT',GAME);}
    }
  }

  // Prefer authenticated private Git commits: release REST API can be temporarily throttled.
  // Keep the browser alive and the uncommitted source buffer if private storage fails.
  let nextFlush=Date.now()+FLUSH_MS, nextStatusCheck=Date.now()+FINAL_POLL_MS;
  // A delayed runner cannot silently extend a nominally live capture into postgame.
  const deadline=Math.min(Date.now()+CAPTURE_MS,START+LIVE_STOP_MS);
  while(Date.now()<deadline){
   // Emit actual advancing live player time, not arbitrary post-final seeks.
   const liveMs=Date.now()-1500;
   try{
    await page.evaluate(t=>window.ephemeralFeed.seek(t),liveMs);
    seekErrors=0;
   }catch(e){
    seekErrors++;
    console.log('IGP_LIVE_SEEK_TRANSIENT',GAME,seekErrors);
    if(seekErrors>=15)throw Error('sdk_seek_continuous_failures');
   }
   await sleep(1000);
   if(Date.now()>=nextFlush){
    void flush();nextFlush=Date.now()+FLUSH_MS;
    console.log('IGP_LIVE_SDK_HEARTBEAT',JSON.stringify({
     game_id:GAME,seconds_since_source:Math.round((Date.now()-lastSdkResponse)/1000),
     seconds_since_xyz:lastLiveXYZ?Math.round((Date.now()-lastLiveXYZ)/1000):null,
     buffered_source_responses:buffer.size,storage_retries:storageRetries}));
   }
   if(Date.now()>=nextStatusCheck && Date.now()>START+80*60000){
    nextStatusCheck=Date.now()+FINAL_POLL_MS;
    await pollOfficialFinal();
   }
   if(finalObservedAt)startSignedDrainIfReady();
   if(Date.now()>=nextBackfill && Date.now()>START+FIRST_RECOVERY_MINUTE*60000 &&
      lastOriginalAt!==null && !disabledAt && !sourceDeniedAt && !signedDrainActive){
    nextBackfill=Date.now()+(finalObservedAt?9000:BACKFILL_INTERVAL_MS);
    try{await backfillObservedSource(finalObservedAt!==null);}
    catch(e){console.log('IGP_SOURCE_BACKFILL_TRANSIENT',GAME,
      /^[a-z_]+$/.test(e?.message||'')?e.message:'sdk_source_unavailable');}
   }
   const finalDecision=sourceDeniedAt?'STOP_SIGNED_ORIGINAL_SOURCE_ACCESS_DENIED':
     finalObservedAt?postfinalWindowDecision({
       finalSeenAt:finalObservedAt,now:Date.now(),disabledAt,lastSourceAt:lastOriginalAt
     }):'CONTINUE_AUTHENTIC_SOURCE';
   if(finalObservedAt&&finalDecision!=='CONTINUE_AUTHENTIC_SOURCE'){
    console.log('IGP_FINAL_WINDOW_TIMING_RECEIPT',JSON.stringify({
      stopping_reason:finalDecision,
      game_id:GAME,official_final_first_seen_utc:new Date(finalObservedAt).toISOString(),
      first_authenticated_slot_seen_utc:firstOriginalAt?new Date(firstOriginalAt).toISOString():null,
      last_authenticated_slot_seen_utc:lastOriginalAt?new Date(lastOriginalAt).toISOString():null,
      sdk_disabled_first_seen_utc:disabledAt?new Date(disabledAt).toISOString():null,
      signed_source_denied_first_seen_utc:sourceDeniedAt?new Date(sourceDeniedAt).toISOString():null,
      postfinal_original_slot_responses:postFinalOriginalResponses,
      postfinal_original_player_ball_responses:postFinalPlayerBallResponses,
      pre_and_postfinal_seek_attempts:sourceBackfillAttempts,
      postfinal_seek_attempts:postFinalBackfillAttempts,
      postfinal_sdk_signed_source_attempts:signedOriginalAttempts,
      postfinal_sdk_signed_source_responses:signedOriginalSuccessful,
      postfinal_sdk_signed_player_ball_windows:signedOriginalPlayerBall,
      unique_original_slots_session:observedSlots.size,
      original_player_ball_windows_session:observedPlayerBallSlots.size,
      hypothesis_status:postFinalPlayerBallResponses&&disabledAt?
        'POSTFINAL_PLAYER_BALL_OBSERVED_THEN_DISABLED':
        postFinalPlayerBallResponses?'POSTFINAL_PLAYER_BALL_SOURCE_OBSERVED':
        postFinalOriginalResponses?'POSTFINAL_RESPONSE_ONLY_NO_PLAYER_BALL_PROOF':
        disabledAt?'POSTFINAL_DISABLED_NO_SOURCE':'UNCERTAIN_NO_POSTFINAL_SOURCE'
    }));
    console.log('IGP_LIVE_OFFICIAL_FINAL_GRACE_COMPLETE',GAME);
    break;
   }
   if(!finalObservedAt&&Date.now()>START+14*60000&&Date.now()-lastSdkResponse>120000)
    throw Error('sdk_source_watchdog_timeout');
  }
  // Freeze input BEFORE the private SHA queue drains. Otherwise live browser
  // responses can keep refilling the buffer and falsely fail final readback.
  acceptResponses=false;
  await Promise.allSettled([...pending]);
  for(let retry=0;retry<5;retry++){
   await flush();
   if(!buffer.size)break;
   await sleep(400*(retry+1));
  }
  if(buffer.size)throw Error('private_source_unpersisted');
  console.log('IGP_FINAL_WINDOW_SOURCE_SUMMARY',JSON.stringify({
    game_id:GAME,unique_original_slot_windows:observedSlots.size,
    original_player_ball_windows:observedPlayerBallSlots.size,
    source_backfill_attempts:sourceBackfillAttempts,
    successful_source_backfill_slot_delta:sourceBackfillObserved,
    first_final_status_observed:finalObservedAt?new Date(finalObservedAt).toISOString():null,
    last_authentic_source_response:lastOriginalAt?new Date(lastOriginalAt).toISOString():null,
    sdk_app_disabled_observed:disabledAt?new Date(disabledAt).toISOString():null,
    postfinal_original_player_ball_responses:postFinalPlayerBallResponses,
    signed_sdk_source_attempts:signedOriginalAttempts,
    signed_sdk_source_responses:signedOriginalSuccessful,
    signed_sdk_source_player_ball_windows:signedOriginalPlayerBall
  }));
  console.log('IGP_REALTIME_SESSION_RESULT',JSON.stringify({game_id:GAME,
   archived_source_responses:saved,player_timestamps:playerFrames,
   ball_timestamps:ballFrames,verified_source:saved>0&&playerFrames>0&&ballFrames>0}));
 }finally{
  // Stop bounded direct retrieval before closing SDK and make sure its genuine
  // event-array results enter the private SHA pipeline exactly once.
  signedDrainStop=true;
  if(signedDrainPromise)try{await signedDrainPromise;}catch{}
  // Even after errors, preserve any authentic source responses already received.
  try{
   acceptResponses=false;
   await Promise.allSettled([...pending]);
   for(let retry=0;retry<5;retry++){
    await flush();
    if(!buffer.size)break;
    await sleep(400*(retry+1));
   }
   if(buffer.size)throw Error('private_source_unpersisted');
  }catch(e){console.error('IGP_REALTIME_FINAL_CHECKPOINT_FAILED',e.message);process.exitCode=3;}
  try{
    await savePrivateFinalWindowReceipt({
      schema:'igp.original-sdk.postfinal-access-window-evidence.v1',
      game_id:GAME,
      tipoff_utc:new Date(START).toISOString(),
      source_first_seen_utc:firstOriginalAt?new Date(firstOriginalAt).toISOString():null,
      source_last_seen_utc:lastOriginalAt?new Date(lastOriginalAt).toISOString():null,
      official_final_first_seen_utc:finalObservedAt?new Date(finalObservedAt).toISOString():null,
      sdk_app_disabled_first_seen_utc:disabledAt?new Date(disabledAt).toISOString():null,
      signed_source_denied_first_seen_utc:sourceDeniedAt?new Date(sourceDeniedAt).toISOString():null,
      original_slot_responses_saved:saved,
      original_player_xyz_timestamp_rows_saved:playerFrames,
      original_ball_xyz_timestamp_rows_saved:ballFrames,
      unique_sdk_original_slot_windows_observed:observedSlots.size,
      original_player_ball_source_windows_observed:observedPlayerBallSlots.size,
      pre_and_postfinal_backfill_attempts:sourceBackfillAttempts,
      postfinal_backfill_attempts:postFinalBackfillAttempts,
      postfinal_original_responses:postFinalOriginalResponses,
      postfinal_original_player_ball_responses:postFinalPlayerBallResponses,
      postfinal_sdk_signed_source_attempts:signedOriginalAttempts,
      postfinal_sdk_signed_successful_source_responses:signedOriginalSuccessful,
      postfinal_sdk_signed_player_ball_source_responses:signedOriginalPlayerBall,
      source_storage_retries:storageRetries,
      native_xyz_imputed:false,
      signed_sdk_url_or_token_persisted:false,
      postfinal_source_access_proven:postFinalPlayerBallResponses>0,
      observed_at_utc:new Date().toISOString()
    });
  }catch{console.error('IGP_FINAL_WINDOW_PRIVATE_EVIDENCE_RETRY_REQUIRED',GAME);}
  if(browser)await browser.close();
  await new Promise(ok=>server.close(ok));
  if(privateGit){rmSync(privateGit.dir,{recursive:true,force:true});privateGit=null;}
 }
 if(playerFrames===0||ballFrames===0){
  console.log('IGP_REALTIME_ZERO_XYZ_RETRY_REQUIRED',GAME,saved,playerFrames,ballFrames);
  process.exitCode=4;
 }
}
main().catch(e=>{const message=/^[a-z_]+$/.test(e?.message||'')?e.message:'source_unavailable';
 console.error('IGP_REALTIME_CAPTURE_FAILED',GAME,message);process.exitCode=2;});
