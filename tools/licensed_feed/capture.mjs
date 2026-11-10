import puppeteer from 'puppeteer-core';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {spawnSync,execFileSync} from 'node:child_process';
import {gzipSync} from 'node:zlib';
import {recoverMissingWindows,recoveryAnchor} from './sdk_slot.mjs';

const ROOT=import.meta.dirname;
const WINDOW=5000;
const sleep=ms=>new Promise(ok=>setTimeout(ok,ms));
export function checkJob(job) {
 if (!job||!/^(002|003|004|005|006)26\d{5}$/.test(job.game_id)
  ||job.account_id!=='nba'||job.program_id!=='companion-'+job.game_id+'-positions'
  ||!Number.isSafeInteger(job.start_ms)||job.start_ms%WINDOW!==0
  ||!Number.isSafeInteger(job.count)||job.count<1||job.count>300
  ||!Number.isSafeInteger(job.part)||job.part<0||job.part>50) throw Error('invalid_job');
 return job;
}
export function stats(job,rows){
 const frames=new Map();
 let empty=0;
 for(const row of rows){
  if(!Array.isArray(row.events))throw Error('invalid_event_rows');
  if(row.events.length===0)empty++;
  for(const event of row.events){
   for(const f of event?.metadata?.keyframes||[]){
    if(Number.isSafeInteger(f?.timestamp)&&!frames.has(f.timestamp))frames.set(f.timestamp,f);
   }
  }
 }
 const observed=[...frames.values()].sort((a,b)=>a.timestamp-b.timestamp);
 const hasPlayers=f=>Object.keys(f.positions||{}).some(k=>k!=='ball');
 const hasBall=f=>Object.hasOwn(f.positions||{},'ball');
 return {
  manifest:{schema:'nba-gamepulse-sdk-chunk.v1',game_id:job.game_id,
   part:job.part,start_ms:job.start_ms,successful_windows:rows.length,
   expected_windows:job.count,capture_complete:rows.length===job.count,
   source_window_starts_ms:rows.map(x=>x.from),
   empty_windows:empty,unique_keyframes:observed.length,
   frames_with_players:observed.filter(hasPlayers).length,
   frames_with_ball:observed.filter(hasBall).length,
   observed:true,imputed:false},
  frames:observed
 };
}
function browserBinary(){
 for(const name of ['google-chrome','google-chrome-stable','chromium']){
  try{return execFileSync('which',[name],{encoding:'utf8'}).trim();}catch(_){}
 }
 throw Error('chromium_unavailable');
}
async function launchClient(job,received,pending){
 await build({entryPoints:[join(ROOT,'browser.js')],bundle:true,platform:'browser',
  format:'iife',outfile:join(ROOT,'bundle.js'),logLevel:'silent'});
 const server=createServer((req,res)=>{
  const file=req.url==='/'?'index.html':req.url==='/bundle.js'?'bundle.js':null;
  if(!file){res.writeHead(404).end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':'text/html');
  res.end(readFileSync(join(ROOT,file)));
 });
 await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 let browser,observedSlotUrl=null;
 try{
  browser=await puppeteer.launch({headless:true,executablePath:browserBinary(),
   args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage();
  page.on('response',response=>{
   try{
    const url=new URL(response.url());
    if(response.status()!==200||url.hostname!=='nba-cdn.cloud.easelive.tv'
     ||!url.pathname.includes('/'+job.program_id+'/')
     ||!url.pathname.endsWith('/events/slot'))return;
    const ms=Number(url.searchParams.get('from'));
    if(!Number.isSafeInteger(ms))return;
    // Keep SDK-issued session credentials in memory even when the browser
    // probes an observed anchor slot outside the assigned capture chunk.
    if(url.searchParams.has('token'))observedSlotUrl=response.url();
    if(ms<job.start_ms||ms>=job.start_ms+job.count*WINDOW)return;
    const p=response.json().then(events=>{
      if(Array.isArray(events))received.set(ms,{from:ms,to:ms+4999,events});
    }).catch(()=>{});
    pending.add(p);p.finally(()=>pending.delete(p));
   }catch(_){}
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/',{waitUntil:'domcontentloaded',timeout:12000});
  await page.waitForFunction(()=>typeof window.ephemeralFeed?.initialize==='function',{timeout:10000});
  const result=await page.evaluate(j=>window.ephemeralFeed.initialize({
    accountId:j.account_id,programId:j.program_id
  }),job);
  // The SDK may emit genuine source responses even if app.ready arrives late.
  // A timeout is seek-eligible, never proof of ingestion: downstream requires
  // an observed SDK-issued slot URL and every exact original 5s response.
  // Explicit SDK error states remain a hard failure.
  const lifecycle=await page.evaluate(()=>window.ephemeralFeed.diagnostics());
  console.log('SDK_INITIALIZATION_GRADE',result==='ready'?'READY':result==='timeout'?'TIMEOUT_SOURCE_REQUIRED':'ERROR');
  console.log('SDK_SOURCE_LIFECYCLE',JSON.stringify({game_id:job.game_id,
   stage_counts:lifecycle.event_counts,app_status:lifecycle.latest_app_status,
   app_status_counts:lifecycle.app_status_counts,
   warning_count:lifecycle.error_type_counts?.warning||0}));
  const gate=sdkInitSourceGate(result,lifecycle,!!observedSlotUrl,received.size);
  if(gate!=='SEEK_SOURCE_REQUIRED')throw Error(gate);
  return {page,observedUrl:()=>observedSlotUrl,
   close:async()=>{await browser.close();await new Promise(ok=>server.close(ok));}};
 }catch(e){
  if(browser)await browser.close();
  await new Promise(ok=>server.close(ok));
  throw e;
 }
}
export function sdkInitCanSeek(state){return state==='ready'||state==='timeout';}
export function sdkInitSourceGate(state,lifecycle,hasSourceSlotUrl=false,observedWindows=0){
 if(!sdkInitCanSeek(state))return 'sdk_initialization_failed';
 if(state==='timeout'&&lifecycle?.latest_app_status==='disabled'&&
   !hasSourceSlotUrl&&observedWindows===0)return 'sdk_app_disabled';
 return 'SEEK_SOURCE_REQUIRED';
}

export async function initializeWithRetry(factory,wait=sleep){
 for(let attempt=0;attempt<3;attempt++){
  try{return await factory();}
  catch(e){
   if(e?.message!=='sdk_initialization_failed'||attempt===2)throw e;
   await wait(1500*(attempt+1));
  }
 }
}
export async function capture(job,dir,{allowPartial=false}={}){
 checkJob(job);
 // Live acceleration is limited to matured, fully elapsed five-second source windows.
 // The licensed SDK must authenticate and every slot response must be observed.
 if(process.env.GAMEPULSE_LIVE_ELAPSED_FASTLANE==='true' &&
    Date.now()<job.start_ms+job.count*WINDOW+10*60000)
   throw Error('live_window_not_mature');
 const received=new Map(),pending=new Set();
 const session=await initializeWithRetry(()=>launchClient(job,received,pending));
 try{
  const windows=Array.from({length:job.count},(_,i)=>job.start_ms+i*WINDOW);
  const seek=ms=>session.page.evaluate(t=>window.ephemeralFeed.seek(t),ms);
  if(process.env.GAMEPULSE_FINAL_FASTLANE==='true'||
     process.env.GAMEPULSE_LIVE_ELAPSED_FASTLANE==='true'){
   // Any post-final checkpoint can be collected by authentic exact SDK slots.
   // Use an earlier, actually observed SDK slot to obtain an in-memory signed
   // session URL, then require successful exact responses for EVERY target slot.
   const anchor=recoveryAnchor(job);
   // SDK feeds sometimes do not publish the first sampled anchor. Probe
   // independent in-game points to recover an actual signed 200-response URL.
   const anchorOffsets=[0,5*WINDOW,-15*60000,15*60000,30*60000,45*60000];
   for(const offset of anchorOffsets){
    if(session.observedUrl())break;
    await seek(anchor+offset);
    await sleep(1200);
   }
   if(!session.observedUrl())throw Error('sdk_session_url_missing');
   await recoverMissingWindows(job,received,session.observedUrl());
  }else{
   for(const ms of windows){await seek(ms);await sleep(450);}
   await sleep(1700);await Promise.allSettled([...pending]);
   for(let retry=0;retry<3;retry++){
    const missing=windows.filter(ms=>!received.has(ms));
    if(!missing.length)break;
    for(const ms of missing){await seek(ms);await sleep(750);}
    await sleep(1600);await Promise.allSettled([...pending]);
   }
   if(process.env.GAMEPULSE_DIAGNOSTIC_ONLY==='true')
    console.log('SDK_NATIVE_SEEK_WINDOW_COVERAGE',JSON.stringify({
     game_id:job.game_id,start_ms:job.start_ms,
     native_windows_received:windows.filter(ms=>received.has(ms)).length,
     expected_windows:windows.length
    }));
   if(windows.some(ms=>!received.has(ms))){
    try{await recoverMissingWindows(job,received,session.observedUrl());}
    catch(e){
     // A live source-read failure must not discard other genuinely observed
     // five-second SDK responses. Full thirteen-part archives remain strict.
     if(!allowPartial||!['uncovered_window','sdk_session_url_missing'].includes(e?.message))throw e;
    }
   }
  }
  const rows=windows.map(ms=>received.get(ms)).filter(Boolean);
  if(rows.length===0||(!allowPartial&&rows.length!==windows.length))throw Error('uncovered_window');
  if(allowPartial&&rows.length<windows.length)
   console.log('SDK_LIVE_OBSERVED_PARTIAL_WINDOWS',JSON.stringify({
    game_id:job.game_id,part:job.part,expected:windows.length,observed:rows.length}));
  const {manifest,frames}=stats(job,rows);
  mkdirSync(dir,{recursive:true});
  writeFileSync(join(dir,'manifest.json'),JSON.stringify(manifest)+'\n');
  writeFileSync(join(dir,'raw-slots.jsonl.gz'),gzipSync(Buffer.from(rows.map(x=>JSON.stringify(x)).join('\n')+'\n')));
  writeFileSync(join(dir,'frames.jsonl.gz'),gzipSync(Buffer.from(frames.map(x=>JSON.stringify(x)).join('\n')+'\n')));
  const tar=spawnSync('tar',['-czf',join(dir,'checkpoint.tar.gz'),'-C',dir,
    'manifest.json','raw-slots.jsonl.gz','frames.jsonl.gz'],{stdio:'ignore',timeout:60000});
  if(tar.status!==0)throw Error('archive_pack_failed');
 }finally{await session.close();}
}
if(process.argv[1]?.endsWith('capture.mjs')){
 const job=JSON.parse(readFileSync(process.argv[2],'utf8'));
 capture(job,process.argv[3]).then(()=>console.log('CAPTURE_READY')).catch(e=>{
  const safe=/^[a-z_]+$/.test(e?.message||'')?e.message:'capture_failed';
  console.error(safe);process.exitCode=2;
 });
}
