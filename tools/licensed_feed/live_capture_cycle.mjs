/** Live-first NBA SDK source collection. CPU only; original assets PRIVATE in 104.
 * Source-verified 5s responses are never discarded because a different slot failed.
 * A partial minute is a separate, immutable, SHA-checked asset; never a full minute.
 */
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {appendFileSync,copyFileSync,mkdtempSync,rmSync,readFileSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {planGame} from './season_core.mjs';

const PRIV='timeedmonds-maker/104',PUB='timeedmonds-maker/hoopvision-runner';
const TOKEN=process.env.GH_TOKEN;
const sha=b=>createHash('sha256').update(b).digest('hex');
const pause=ms=>new Promise(ok=>setTimeout(ok,ms));

function gh(args) {
 const r=spawnSync('gh',args,{encoding:'utf8',timeout:110000,maxBuffer:2*1024*1024,
  stdio:['ignore','pipe','pipe'],env:{...process.env,GH_TOKEN:TOKEN}});
 if(r.status!==0){
  // Never print stderr or signed private release URLs.
  if(/HTTP 404|404 Not Found/i.test(r.stderr||''))throw Error('private_resource_missing');
  if(/HTTP 429|rate limit/i.test(r.stderr||''))throw Error('private_rate_limited');
  throw Error('private_operation_failed');
 }
 return r.stdout;
}
function getAssets(tag) {
 try{
  const obj=JSON.parse(gh(['api','repos/'+PRIV+'/releases/tags/'+tag]));
  if(!Array.isArray(obj.assets))throw Error('private_release_invalid');
  return new Map(obj.assets.map(a=>[a.name,a]));
 }catch(e){
  if(e?.message==='private_resource_missing')return null;
  throw e;
 }
}
function ensure(tag) {
 if(getAssets(tag)!==null)return;
 try{
  gh(['release','create',tag,'--repo',PRIV,'--title',tag,
   '--notes','Original observed live Game Pulse checkpoints, private only','--latest=false']);
 }catch(e){
  if(getAssets(tag)===null)throw e;
 }
 if(getAssets(tag)===null)throw Error('private_release_creation_unverified');
}
export function eligibleSlot(start,now,slotsAlready=new Set()) {
 const full=planGame({id:'0022600001',start});
 // Prioritize latest *elapsed* source minute, then move backward through gaps.
 let latest=null;
 for(let i=10;i<310;i++){
  const from=full.begin+i*60000;
  if(from>=full.end)break;
  if(now<from+Math.min(60000,full.end-from)+30000)break;
  if(!slotsAlready.has(from))latest=i;
 }
 return latest;
}
export function validateLiveManifest(job,m) {
 if(!m||m.schema!=='nba-gamepulse-sdk-chunk.v1'
  ||m.game_id!==job.game_id||m.start_ms!==job.start_ms||m.part!==job.part
  ||m.observed!==true||m.imputed!==false
  ||m.expected_windows!==job.count
  ||!Number.isSafeInteger(m.successful_windows)
  ||m.successful_windows<1||m.successful_windows>job.count
  ||m.capture_complete!==(m.successful_windows===job.count)
  ||!Number.isSafeInteger(m.empty_windows)||m.empty_windows<0||m.empty_windows>m.successful_windows
  ||!Number.isSafeInteger(m.frames_with_players)||m.frames_with_players<0
  ||!Number.isSafeInteger(m.frames_with_ball)||m.frames_with_ball<0
  ||!Array.isArray(m.source_window_starts_ms)
  ||m.source_window_starts_ms.length!==m.successful_windows)
  throw Error('live_source_manifest_invalid');
 const unique=new Set(m.source_window_starts_ms);
 if(unique.size!==m.successful_windows
  ||m.source_window_starts_ms.some((t,i)=>!Number.isSafeInteger(t)
      ||t<job.start_ms||t>=job.start_ms+job.count*5000
      ||t%5000!==0||(i>0&&t<=m.source_window_starts_ms[i-1])))
   throw Error('live_source_window_identity_invalid');
 return m.capture_complete?'FULL_5S_SOURCE_COVERAGE':'PARTIAL_5S_SOURCE_COVERAGE';
}
function acceptedCompleteMinutes(assets){
 const result=new Set();
 for(const name of assets.keys()){
  const match=/^live-(\d{13})\.tar\.gz$/.exec(name);
  if(match&&assets.has(name.replace('.tar.gz','.json')))result.add(Number(match[1]));
 }
 return result;
}
function uploadImmutable(tag,file,name,digest){
 const existing=getAssets(tag);
 if(existing===null)throw Error('private_release_missing');
 const asset=existing.get(name);
 if(asset){
  if(asset.digest!=='sha256:'+digest)throw Error('private_existing_source_sha_conflict');
  return false;
 }
 gh(['release','upload',tag,file,'--repo',PRIV]);
 const check=getAssets(tag)?.get(name);
 if(!check||check.digest!=='sha256:'+digest)
  throw Error('private_live_source_sha_readback_failed');
 return true;
}
async function main() {
 const id=process.env.GAMEPULSE_LIVE_ID;
 const start=Date.parse(process.env.GAMEPULSE_LIVE_TIPOFF||'');
 if(process.env.GITHUB_REPOSITORY!==PUB||
    process.env.GITHUB_REF!=='refs/heads/main'||
    !['schedule','push','workflow_dispatch'].includes(process.env.GITHUB_EVENT_NAME)||
    !/^00226\d{5}$/.test(id||'')||!Number.isSafeInteger(start)||
    !TOKEN||TOKEN.length<30)throw Error('unauthorized_live_collection');
 delete process.env.GH_TOKEN;
 const {capture}=await import('./capture.mjs');
 const tag='gamepulse-live-sdk-'+id;
 ensure(tag);
 const fullPlan=planGame({id,start});
 const deadline=Date.now()+215000;
 let fullSaved=0,partialSaved=0,failed=0;
 const attempted=new Set();
 const failures={};
 while(Date.now()<deadline-20000 && attempted.size<10){
  const assets=getAssets(tag);
  if(assets===null)throw Error('private_release_missing');
  const archived=acceptedCompleteMinutes(assets);
  const slot=eligibleSlot(start,Date.now(),new Set([...archived,...attempted]));
  if(slot===null){
   // Discovery arms the game before tipoff but avoids wasting 3+ min of CPU.
   if(Date.now()<start+90000){console.log('LIVE_PREGAME_DISCOVERED',id);break;}
   // All eligible completed minutes are already stored.
   console.log('LIVE_ALL_ELAPSED_COMPLETE_MINUTES_ARCHIVED',id,archived.size);
   break;
  }
  const from=fullPlan.begin+slot*60000;
  attempted.add(from);
  const job={game_id:id,account_id:'nba',program_id:'companion-'+id+'-positions',
   part:Math.floor((from-fullPlan.begin)/(300*5000)),start_ms:from,
   count:Math.min(12,(fullPlan.end-from)/5000)};
  const dir=mkdtempSync(join(tmpdir(),'gp-live-'));
  try{
   await capture(job,dir,{allowPartial:true});
   const m=JSON.parse(readFileSync(join(dir,'manifest.json'),'utf8'));
   const grade=validateLiveManifest(job,m);
   const archive=join(dir,'checkpoint.tar.gz'),digest=sha(readFileSync(archive));
   const base=grade==='FULL_5S_SOURCE_COVERAGE'?'live-'+from:
    'partial-observed-'+from+'-'+digest.slice(0,20);
   const archivePath=join(dir,base+'.tar.gz'),side=join(dir,base+'.json');
   copyFileSync(archive,archivePath);
   writeFileSync(side,JSON.stringify({...m,archive_sha256:digest,source_grade:grade})+'\n');
   // Never replace original files. Partial captures use distinct names outside the live-*.tar.gz complete-minute consumer glob.
   uploadImmutable(tag,archivePath,base+'.tar.gz',digest);
   uploadImmutable(tag,side,base+'.json',sha(readFileSync(side)));
   if(grade==='FULL_5S_SOURCE_COVERAGE')fullSaved++;
   else partialSaved++;
   failed=0;
   console.log('PRIVATE_LIVE_ORIGINAL_SHA_VERIFIED',JSON.stringify({
    game_id:id,minute_utc_ms:from,grade,expected_windows:job.count,
    authentic_windows:m.successful_windows,
    player_keyframes:m.frames_with_players,ball_keyframes:m.frames_with_ball}));
  }catch(e){
   failed++;
   const safe=/^[a-z_]+$/.test(e?.message||'')?e.message:'source_unavailable';
   failures[safe]=(failures[safe]||0)+1;
   console.log('PRIVATE_LIVE_SOURCE_RETRY_REQUIRED',JSON.stringify({
    game_id:id,minute_utc_ms:from,category:safe}));
   // Two independent empty minutes with no source response are sufficient
   // for this cycle. Retry on the next scheduled discovery, not ten times
   // against a programme that has not published authentic SDK slots.
   if(failed>=2&&fullSaved+partialSaved===0&&
      ['uncovered_window','sdk_session_url_missing','sdk_initialization_failed'].includes(safe)){
    console.log('LIVE_POSITIONS_FEED_UNAVAILABLE_BACKOFF',id,safe);
    break;
   }
   // Do not re-query a failed minute in this cycle. Other mature minutes
   // may still have original observations worth preserving right now.
  }finally{rmSync(dir,{recursive:true,force:true});}
 }
 const result={game_id:id,complete_minutes_saved:fullSaved,
  partial_minutes_saved:partialSaved,failed_minutes:failed,
  distinct_minutes_attempted:attempted.size,failures};
 console.log('LIVE_FIRST_INGESTION_CYCLE',JSON.stringify(result));
 if(process.env.GITHUB_STEP_SUMMARY)appendFileSync(process.env.GITHUB_STEP_SUMMARY,
  '### Live-first original SDK source health\\n\\n'+
  'Game '+id+'; complete source minutes '+fullSaved+'; authentic partial minutes '+
  partialSaved+'; failed minutes '+failed+'. Missing XYZ remains unobserved, never imputed.\\n');
 if(process.env.GITHUB_OUTPUT)
  appendFileSync(process.env.GITHUB_OUTPUT,'new_capture='+
   String(fullSaved+partialSaved>0)+'\n');
 if(failed>0&&fullSaved+partialSaved===0)process.exitCode=2;
}
if(process.argv[1]?.endsWith('live_capture_cycle.mjs')){
 main().catch(e=>{console.error(/^[a-z_]+$/.test(e?.message||'')?
  e.message:'live_worker_failed');process.exitCode=2;});
}
