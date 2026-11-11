/**
 * Original NBA player/ball positions captured as the game unfolds.
 * Store ONLY SDK-observed authenticated slot responses in protected private Git and, if needed, private Release assets.
 * Live clock only; no replay-seek window recovery, credentials rewriting, or fabricated XYZ.
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

const ROOT=import.meta.dirname;
const GAME=process.env.GAMEPULSE_LIVE_ID;
const START=Date.parse(process.env.GAMEPULSE_LIVE_TIPOFF||'');
const REPO='timeedmonds-maker/104';
const TOKEN=process.env.GH_TOKEN;
const sleep=ms=>new Promise(done=>setTimeout(done,ms));
const CAPTURE_MS=Number(process.env.IGP_REALTIME_CAPTURE_MS||185000);
const PRETIPOFF_WAIT_MS=Number(process.env.IGP_REALTIME_PRETIPOFF_WAIT_MS||0);
const FLUSH_MS=Number(process.env.IGP_REALTIME_FLUSH_MS||40000);
const sha=b=>createHash('sha256').update(b).digest('hex');
const gitExec=promisify(execFile);
const PRIVATE_BRANCH='research/gamepulse-clock-boundary-integrity-20261025';
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
 if(process.env.GITHUB_REPOSITORY!=='timeedmonds-maker/hoopvision-runner'
  ||process.env.GITHUB_REF!=='refs/heads/main'
  ||!['schedule','workflow_dispatch','push'].includes(process.env.GITHUB_EVENT_NAME)
  ||!/^00[1-5]\d{7}$/.test(GAME||'')||!Number.isSafeInteger(START)
  ||!TOKEN||TOKEN.length<30)throw Error('unauthorized_live_collection');
 if(!Number.isSafeInteger(CAPTURE_MS)||CAPTURE_MS<30000||CAPTURE_MS>16000000
  ||!Number.isSafeInteger(PRETIPOFF_WAIT_MS)||PRETIPOFF_WAIT_MS<0||PRETIPOFF_WAIT_MS>14400000
  ||!Number.isSafeInteger(FLUSH_MS)||FLUSH_MS<20000||FLUSH_MS>180000)throw Error('invalid_live_duration');
 let now=Date.now();
 if(now<START-2*60000&&PRETIPOFF_WAIT_MS>0){
   if(START-2*60000-now>PRETIPOFF_WAIT_MS)throw Error('pregame_wait_exceeds_limit');
   console.log('IGP_LIVE_WAIT_FOR_TIPOFF',GAME,START);
   while(Date.now()<START-2*60000)await sleep(Math.min(30000,Math.max(1000,START-2*60000-Date.now())));
   now=Date.now();
 }
 if(now<START-2*60000||now>START+6*3600000){
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
 const seen=new Set(),pending=new Set(),buffer=new Map();
 const tag='gamepulse-live-sdk-'+GAME;
 let browser,saved=0,playerFrames=0,ballFrames=0;
 let storeQueue=Promise.resolve(),storageRetries=0,lastSdkResponse=Date.now(),lastLiveXYZ=0,seekErrors=0;
 // Source observation continues while private SHA uploads run in serialized background.
 function flush(){
  const entries=[...buffer.entries()].sort((a,b)=>a[1].from-b[1].from);
  if(!entries.length)return storeQueue;
  for(const [key] of entries)buffer.delete(key);
  const write=async()=>{
   const rows=entries.map(e=>e[1]),stats=countSource(rows);
  const zipped=gzipSync(Buffer.from(rows.map(r=>JSON.stringify(r)).join('\n')+'\n'));
  const digest=sha(zipped);
  const base='realtime-'+GAME+'-'+rows[0].from+'-'+digest.slice(0,16);
  const meta={schema:'igp.original-sdk-realtime-response.v1',game_id:GAME,
   original_source_grade:'SDK_OBSERVED_NOT_FULLGAME',
   source_observed_at_utc:new Date().toISOString(),...stats,
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
  page.on('response',response=>{
   try{
    const u=new URL(response.url());
    if(response.status()!==200||u.protocol!=='https:'
     ||u.hostname!=='nba-cdn.cloud.easelive.tv'
     ||!u.pathname.includes('/companion-'+GAME+'-positions/')
     ||!u.pathname.endsWith('/events/slot'))return;
    const from=Number(u.searchParams.get('from'));
    if(!Number.isSafeInteger(from)||from%5000!==0
     ||from<START-20*60000||from>START+6*3600000)return;
    lastSdkResponse=Date.now();
    const p=response.json().then(events=>{
     if(!Array.isArray(events))return;
     if(events.some(ev=>(ev?.metadata?.keyframes||[]).some(f=>{
      const keys=Object.keys(f?.positions||{});
      return keys.includes('ball')&&keys.some(k=>k!=='ball');
     })))lastLiveXYZ=Date.now();
     const body=JSON.stringify(events),key=from+':'+sha(body);
     if(seen.has(key))return;
     seen.add(key);buffer.set(key,{from,to:from+4999,events});
    }).catch(()=>{});
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
  // Prefer authenticated private Git commits: release REST API can be temporarily throttled.
  // Keep the browser alive and the uncommitted source buffer if private storage fails.
  let nextFlush=Date.now()+FLUSH_MS;
  const deadline=Date.now()+CAPTURE_MS;
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
   if(Date.now()>START+14*60000&&Date.now()-lastSdkResponse>120000)
    throw Error('sdk_source_watchdog_timeout');
  }
  await Promise.allSettled([...pending]);
  await flush();
  if(buffer.size)await flush();
  if(buffer.size)throw Error('private_source_unpersisted');
  console.log('IGP_REALTIME_SESSION_RESULT',JSON.stringify({game_id:GAME,
   archived_source_responses:saved,player_timestamps:playerFrames,
   ball_timestamps:ballFrames,verified_source:saved>0&&playerFrames>0&&ballFrames>0}));
 }finally{
  // Even after errors, preserve any authentic source responses already received.
  try{
   await Promise.allSettled([...pending]);
   await flush();
   if(buffer.size)await flush();
   if(buffer.size)throw Error('private_source_unpersisted');
  }catch(e){console.error('IGP_REALTIME_FINAL_CHECKPOINT_FAILED',e.message);process.exitCode=3;}
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
