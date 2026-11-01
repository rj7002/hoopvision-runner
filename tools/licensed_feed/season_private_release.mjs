/** Private Release season lane. No credential reaches the browser or SDK import. */
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {copyFileSync,existsSync,mkdtempSync,readFileSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {planGame,parseSchedule,selectDue,summarize,diagnoseTrackingCoverage} from './season_core.mjs';

const REPO='timeedmonds-maker/104';
const PUBLIC='timeedmonds-maker/hoopvision-runner';
const PILOT=process.env.GAMEPULSE_FULLGAME_PILOT==='true';
const INDEX=PILOT?'gamepulse-sdk-public-pilot-index':'gamepulse-sdk-2026-27-index';
const TOKEN=process.env.GH_TOKEN;
const sha=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
const temp=()=>mkdtempSync(join(tmpdir(),'gp-season-'));
function gh(args){
 const p=spawnSync('gh',args,{encoding:'utf8',timeout:120000,maxBuffer:1024*1024,
  stdio:['ignore','pipe','pipe'],env:{...process.env,GH_TOKEN:TOKEN}});
 const err=p.stderr||'';
 // Never print GitHub stderr: it may contain a signed private asset URL.
 const category=/HTTP 429|rate limit/i.test(err)?'RATE_LIMIT':
  /HTTP 5\d\d|Bad Gateway|Service Unavailable/i.test(err)?'SERVER_ERROR':
  /HTTP 403|forbidden/i.test(err)?'FORBIDDEN':
  /HTTP 422|already_exists/i.test(err)?'CONFLICT':
  p.error?.code==='ETIMEDOUT'||p.signal==='SIGTERM'?'TIMEOUT':'OTHER';
 return {ok:p.status===0,out:p.stdout||'',category};
}
function call(args){
 const result=gh([...args,'--repo',REPO]);
 if(!result.ok)throw Error('private_github_operation_failed');
 return result.out;
}
function names(tag){
 const r=gh(['release','view',tag,'--repo',REPO,'--json','assets']);
 if(!r.ok){if(r.category==='RATE_LIMIT')throw Error('private_github_rate_limited');return null;}
 try{return new Set(JSON.parse(r.out).assets.map(x=>x.name));}
 catch{throw Error('private_asset_listing_invalid');}
}
function ensure(tag){
 if(names(tag)!==null)return;
 const result=gh(['release','create',tag,'--repo',REPO,'--target','main','--title',tag,
  '--notes','Private licensed SDK capture; no public observation assets','--latest=false']);
 if(!result.ok && names(tag)===null)throw Error('private_release_create_failed');
}
function download(tag,name,directory){
 const path=join(directory,name);
 for(let attempt=0;attempt<4;attempt++){
  const result=gh(['release','download',tag,'--pattern',name,'--dir',directory,'--repo',REPO]);
  if(result.ok&&existsSync(path))return path;
  if(attempt<3)spawnSync('sleep',['2'],{stdio:'ignore'});
 }
 throw Error('private_readback_missing');
}
function uploadOrExisting(tag,file,name){
 // A private GitHub release upload can fail transiently after the source
 // checkpoint has been captured. Keep the local archive and retry its exact
 // same asset without changing source bytes or overwriting an existing asset.
 for(let attempt=0;attempt<7;attempt++){
  const result=gh(['release','upload',tag,file,'--repo',REPO]);
  if(result.ok)return;
  if(result.category==='RATE_LIMIT')throw Error('private_github_rate_limited');
  if(names(tag)?.has(name))return;
  console.log('PRIVATE_UPLOAD_RETRY_REQUIRED',attempt+1,result.category);
  if(attempt<6)spawnSync('sleep',[String(Math.min(32,2**(attempt+1)))],{stdio:'ignore'});
 }
 throw Error('private_upload_failed');
}
function readIndex(){
 ensure(INDEX);
 const dir=temp();
 try{
  const assets=names(INDEX);
  if(!assets.has('index.json'))return {schema:'gamepulse-season-index.v1',games:{}};
  const obj=JSON.parse(readFileSync(download(INDEX,'index.json',dir),'utf8'));
  if(obj.schema!=='gamepulse-season-index.v1'||!obj.games||typeof obj.games!=='object')
   throw Error('private_index_invalid');
  return obj;
 }finally{rmSync(dir,{recursive:true,force:true});}
}
function writeIndex(index){
 const dir=temp();
 try{
  index.updated_at=new Date().toISOString();
  const p=join(dir,'index.json');writeFileSync(p,JSON.stringify(index)+'\n');
  call(['release','upload',INDEX,p,'--clobber']);
  const verify=temp();
  try{if(sha(download(INDEX,'index.json',verify))!==sha(p))throw Error('private_index_sha_mismatch');}
  finally{rmSync(verify,{recursive:true,force:true});}
 }finally{rmSync(dir,{recursive:true,force:true});}
}
function validatedPart(tag,job,dir){
 const base='sdk-part-'+String(job.part).padStart(2,'0');
 const archive=download(tag,base+'.tar.gz',dir),sidecar=download(tag,base+'.json',dir);
 const m=JSON.parse(readFileSync(sidecar,'utf8'));
 if(m.archive_sha256&&m.archive_sha256!==sha(archive))throw Error('private_archive_sha_mismatch');
 const unpack=temp();
 try{
  const tar=spawnSync('tar',['-xzf',archive,'-C',unpack,'manifest.json'],{stdio:'ignore',timeout:60000});
  if(tar.status!==0)throw Error('private_archive_invalid');
  const embedded=JSON.parse(readFileSync(join(unpack,'manifest.json'),'utf8'));
  for(const field of ['game_id','part','start_ms','successful_windows','frames_with_players',
   'frames_with_ball','empty_windows'])if(m[field]!==embedded[field])throw Error('private_manifest_mismatch');
  // Older private 104 checkpoint manifests did not include a part ordinal.
  // Bind it from the exact asset name and independently checked start/window.
  const normalized={...m,part:m.part??job.part};
  summarize([job],[normalized]);
  return normalized;
 }finally{rmSync(unpack,{recursive:true,force:true});}
}
function repairArchiveOnly(tag,job){
 const base='sdk-part-'+String(job.part).padStart(2,'0');
 const dir=temp(),unpack=temp();
 try{
  const archive=download(tag,base+'.tar.gz',dir);
  const tar=spawnSync('tar',['-xzf',archive,'-C',unpack,'manifest.json'],{stdio:'ignore',timeout:60000});
  if(tar.status!==0)throw Error('orphan_archive_invalid');
  const manifest=JSON.parse(readFileSync(join(unpack,'manifest.json'),'utf8'));
  summarize([job],[{...manifest,part:manifest.part??job.part}]);
  const sidecar=join(dir,base+'.json');
  writeFileSync(sidecar,JSON.stringify({...manifest,part:job.part,archive_sha256:sha(archive)})+'\n');
  uploadOrExisting(tag,sidecar,base+'.json');
  const check=temp();
  try{if(sha(download(tag,base+'.json',check))!==sha(sidecar))throw Error('orphan_repair_sha_mismatch');}
  finally{rmSync(check,{recursive:true,force:true});}
 }finally{rmSync(dir,{recursive:true,force:true});rmSync(unpack,{recursive:true,force:true});}
}
function repairOrphanManifest(tag,job){
 const base='sdk-part-'+String(job.part).padStart(2,'0');
 const sidecarName=base+'.json',archiveName=base+'.tar.gz';
 const releasePath='repos/'+REPO+'/releases/tags/'+tag;
 function listing(){
  const result=gh(['api',releasePath]);
  if(!result.ok)throw Error('orphan_release_inspection_failed');
  let payload;
  try{payload=JSON.parse(result.out);}catch{throw Error('orphan_asset_listing_invalid');}
  if(!Array.isArray(payload.assets))throw Error('orphan_asset_listing_invalid');
  return payload.assets;
 }
 let assets=listing();
 if(assets.some(x=>x.name===archiveName))return;
 const original=assets.find(x=>x.name===sidecarName);
 if(!original)return;
 const folder=temp(),check=temp();
 try{
  const source=download(tag,sidecarName,folder);
  const record=JSON.parse(readFileSync(source,'utf8'));
  if(record.game_id!==job.game_id||record.part!==job.part||
     record.start_ms!==job.start_ms||record.successful_windows!==job.count)
   throw Error('orphan_sidecar_identity_mismatch');
  const backupName=base+'-orphan-backup.json';
  const backup=join(folder,backupName);
  copyFileSync(source,backup);
  uploadOrExisting(tag,backup,backupName);
  if(sha(download(tag,backupName,check))!==sha(source))
   throw Error('orphan_backup_readback_mismatch');
  assets=listing();
  if(assets.some(x=>x.name===archiveName))return;
  const current=assets.find(x=>x.name===sidecarName);
  if(!current)return;
  if(current.id!==original.id||!Number.isSafeInteger(current.id))
   throw Error('orphan_sidecar_changed_during_repair');
  const deletion=gh(['api','--method','DELETE',
   'repos/'+REPO+'/releases/assets/'+current.id]);
  if(!deletion.ok&&names(tag)?.has(sidecarName))
   throw Error('orphan_sidecar_cleanup_denied');
  console.log('PRIVATE_ORPHAN_MANIFEST_BACKUP_VERIFIED');
 }finally{rmSync(folder,{recursive:true,force:true});rmSync(check,{recursive:true,force:true});}
}
async function capturePart(tag,job,capture){
 const dir=temp();
 try{
  // Transient source anchor/slot failures warrant a fresh SDK browser
  // session, not a fabricated successful window or a whole-game restart.
  for(let attempt=0;;attempt++){
   try{await capture(job,dir);break;}
   catch(e){
    const recoverable=['sdk_session_url_missing','uncovered_window','sdk_initialization_failed']
      .includes(e?.message);
    if(!recoverable||attempt>=2)throw e;
    // Another authorised worker may have saved the missing exact part.
    const base='sdk-part-'+String(job.part).padStart(2,'0');
    if(names(tag)?.has(base+'.tar.gz')&&names(tag)?.has(base+'.json')){
     const check=temp();
     try{return validatedPart(tag,job,check);}
     finally{rmSync(check,{recursive:true,force:true});}
    }
    console.log('PRIVATE_SDK_TRANSIENT_CHECKPOINT_RETRY',job.part,attempt+1);
    await new Promise(resolve=>setTimeout(resolve,1500*(attempt+1)));
   }
  }
  const source=JSON.parse(readFileSync(join(dir,'manifest.json'),'utf8'));
  summarize([job],[source]);
  const base='sdk-part-'+String(job.part).padStart(2,'0');
  const archive=join(dir,base+'.tar.gz'),sidecar=join(dir,base+'.json');
  copyFileSync(join(dir,'checkpoint.tar.gz'),archive);
  writeFileSync(sidecar,JSON.stringify({...source,archive_sha256:sha(archive)})+'\n');
  if(readFileSync(archive).length>32*1024*1024)throw Error('checkpoint_too_large');
  // Another public worker may reach the same part first. Reuse its archive
  // rather than overwrite it or bind a sidecar to a different local tarball.
  uploadOrExisting(tag,archive,base+'.tar.gz');
  if(!names(tag)?.has(base+'.json'))repairArchiveOnly(tag,job);
  const check=temp();
  try{return validatedPart(tag,job,check);}
  finally{rmSync(check,{recursive:true,force:true});}
 }finally{rmSync(dir,{recursive:true,force:true});}
}
async function archiveGame(game,index,capture,{skipSeasonIndex=false}={}){
 const plan=planGame(game),tag=(PILOT?'gamepulse-sdk-public-pilot-':'gamepulse-sdk-')+game.id;
 ensure(tag);
 const reports=[];
 const partLimit=Number(process.env.GAMEPULSE_PARTS_PER_RUN||13);
 if(!Number.isSafeInteger(partLimit)||partLimit<1||partLimit>13)throw Error('invalid_parts_limit');
 let newParts=0;
 for(const job of plan.parts){
  const base='sdk-part-'+String(job.part).padStart(2,'0');
  const existing=names(tag);
  const pair=[existing.has(base+'.tar.gz'),existing.has(base+'.json')];
  if(pair[0]&&!pair[1])repairArchiveOnly(tag,job);
  if(!pair[0]&&pair[1]){
   repairOrphanManifest(tag,job);
   const revised=names(tag);
   pair[0]=revised.has(base+'.tar.gz');
   pair[1]=revised.has(base+'.json');
  }
  const dir=temp();
  try{reports.push(pair[0]?validatedPart(tag,job,dir):await capturePart(tag,job,capture));}
  finally{rmSync(dir,{recursive:true,force:true});}
  // Release assets are the durable per-part state. Do not rewrite the shared
  // private season index for each of the 13 SHA readbacks.
  index.games[game.id]={status:'partial',last_checkpoint:job.part,last_attempt:new Date().toISOString()};
  if(!pair[0] && ++newParts>=partLimit && job.part<plan.parts.length-1){
   if(!skipSeasonIndex)writeIndex(index);
   console.log('PRIVATE_GAME_PARTIAL_SHA_READBACK');
   return;
  }
 }
 const sum=summarize(plan.parts,reports);
 if(sum.windows!==plan.windows||plan.windows!==3720||plan.parts.length!==13)
  throw Error('full_game_coverage_failed');
 const coverage=diagnoseTrackingCoverage(plan.parts,reports);
 const hasSufficientObservations=sum.players>100&&sum.ball>50;
 const done={schema:'gamepulse-fullgame-manifest.v1',game_id:game.id,
  tipoff_utc:new Date(game.start).toISOString(),planned_start_ms:plan.begin,
  planned_end_exclusive_ms:plan.end,expected_windows:plan.windows,
  successful_windows:sum.windows,parts:plan.parts.length,
  sum_frames_with_players:sum.players,sum_frames_with_ball:sum.ball,
  empty_windows:sum.empty,data_class:'observed; no missing coordinates imputed',
  tracking_coverage_qa:coverage,
  acceptance:!hasSufficientObservations?'complete_with_missingness_warning':
   coverage.suspicious_parts.length?'complete_with_tracking_gaps':'complete_with_QA',
  completed_at:new Date().toISOString()};
 const dir=temp();
 try{
  const marker=join(dir,'sdk-COMPLETE.json');writeFileSync(marker,JSON.stringify(done)+'\n');
  if(names(tag).has('sdk-COMPLETE.json')){
   const existing=temp();
   try{
    const old=download(tag,'sdk-COMPLETE.json',existing);
    if(JSON.parse(readFileSync(old,'utf8')).successful_windows!==plan.windows)
     throw Error('existing_complete_marker_conflict');
   }finally{rmSync(existing,{recursive:true,force:true});}
  }else call(['release','upload',tag,marker]);
  const readback=temp();
  try{
   const remote=download(tag,'sdk-COMPLETE.json',readback);
   if(!names(tag).has('sdk-COMPLETE.json')||JSON.parse(readFileSync(remote,'utf8')).successful_windows!==3720)
    throw Error('private_complete_readback_failed');
  }finally{rmSync(readback,{recursive:true,force:true});}
 }finally{rmSync(dir,{recursive:true,force:true});}
 index.games[game.id]={status:'complete',captured_at:done.completed_at,qa:done.acceptance,
  windows:sum.windows,frames_with_players:sum.players,frames_with_ball:sum.ball};
 if(!skipSeasonIndex)writeIndex(index);
 console.log('PRIVATE_GAME_COMPLETE_SHA_READBACK');
}
async function captureElapsedPriority(capture){
 if(process.env.GITHUB_EVENT_NAME!=='schedule')return;
 const id=process.env.GAMEPULSE_PRIORITY_ID;
 const start=Date.parse(process.env.GAMEPULSE_PRIORITY_TIPOFF||'');
 const now=Date.now();
 if(!Number.isSafeInteger(start)||now<start||now>=start+24*3600000)return;
 const jobs=planGame({id,start}).parts;
 const tag='gamepulse-sdk-'+id,existing=names(tag);
 if(!existing)return;
 let processed=0;
 for(const job of jobs){
  if(job.start_ms+job.count*5000+600000>now)break;
  const base='sdk-part-'+String(job.part).padStart(2,'0');
  if(existing.has(base+'.tar.gz')&&existing.has(base+'.json'))continue;
  if(existing.has(base+'.json')&&!existing.has(base+'.tar.gz'))throw Error('priority_orphan_sidecar');
  if(existing.has(base+'.tar.gz'))repairArchiveOnly(tag,job);
  else await capturePart(tag,job,capture);
  console.log('PRIVATE_PRIORITY_LIVE_PART_SHA_READBACK',job.part);
  if(++processed>=2)break;
 }
}
async function schedule(){
 const headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Referer':'https://www.nba.com/'};
 const sources=[['modern','https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json'],
  ['legacy','https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2026/league/00_full_schedule.json']];
 for(const [kind,url] of sources){
  try{
   const r=await fetch(url,{headers,signal:AbortSignal.timeout(20000)});
   if(!r.ok)continue;
   const games=parseSchedule(await r.json(),kind);
   if(games.length)return games;
  }catch{}
 }
 throw Error('schedule_sources_unavailable');
}

async function requireOfficialFinal(gameId){
 for(let attempt=0;attempt<3;attempt++){
  try{
   const response=await fetch('https://cdn.nba.com/static/json/liveData/boxscore/boxscore_'+gameId+'.json',{
    headers:{'Accept':'application/json','Referer':'https://www.nba.com/'},
    signal:AbortSignal.timeout(9000)});
   if(response.ok){
    const body=await response.json();
    const game=body?.game;
    if(String(game?.gameId)===gameId&&String(game?.gameStatus)==='3')return;
   }
  }catch{}
  try{if((await schedule()).some(g=>g.id===gameId))return;}catch{}
  if(attempt<2)await new Promise(done=>setTimeout(done,2000));
 }
 throw Error('official_final_not_verified');
}
function pilotGame(){
 const tags=JSON.parse(call(['release','list','--limit','100','--json','tagName']));
 const matches=tags.filter(x=>typeof x.tagName==='string'&&
  x.tagName.startsWith('gamepulse-sdk-github-acceptance-'));
 if(matches.length!==1)throw Error('private_pilot_assignment_ambiguous');
 const dir=temp();
 try{
  const manifest=JSON.parse(readFileSync(download(matches[0].tagName,'sdk-part-00.json',dir),'utf8'));
  const game={id:manifest.game_id,start:manifest.start_ms+600000};
  planGame(game);
  if(manifest.successful_windows!==300||manifest.frames_with_players<1)
   throw Error('private_pilot_assignment_invalid');
  return game;
 }finally{rmSync(dir,{recursive:true,force:true});}
}

export function assertContext(env){
 if(env.GITHUB_REPOSITORY!==PUBLIC||env.GITHUB_REF!=='refs/heads/main'||
    !['workflow_dispatch','push','schedule'].includes(env.GITHUB_EVENT_NAME)||
    (env.GITHUB_EVENT_NAME==='push'&&env.GAMEPULSE_FULLGAME_PILOT!=='true'&&env.GAMEPULSE_PRIORITY_FANOUT!=='true'&&env.GAMEPULSE_PRIORITY_FINALIZE!=='true'&&env.GAMEPULSE_PRODUCTION_ENABLED!=='true')||
    (env.GITHUB_EVENT_NAME==='schedule'&&
     (env.GAMEPULSE_PRODUCTION_ENABLED!=='true'||
      (env.GAMEPULSE_FULLGAME_PILOT==='true'&&env.GAMEPULSE_PILOT_FINALIZE!=='true')))||
    (env.GITHUB_EVENT_NAME==='workflow_dispatch'&&env.DRY_RUN!=='true'&&
     env.GAMEPULSE_PRODUCTION_ENABLED!=='true')||
    typeof env.GH_TOKEN!=='string'||
    env.GH_TOKEN.length<30)
  throw Error('unauthorized_private_collection');
}

/** One-time, original NBA SDK recapture of the known thin GSW-PHX midgame.
 * The original 13 release checkpoints MUST NOT be overwritten. This is an
 * independent second read with private-only SHA evidence and a bounded scope.
 */
async function probeGswPhoenixGap(capture){
 const gid='0022600111',original='gamepulse-sdk-'+gid;
 const recovered='gamepulse-sdk-recovery-'+gid+'-20261026';
 const game={id:gid,start:Date.parse('2026-10-25T02:00:00Z')};
 const plan=planGame(game);
 if(Date.now()>game.start+7*24*3600000)throw Error('source_recheck_window_expired');
 if(names(recovered)?.has('recheck-COMPLETE.json'))return;
 ensure(recovered);
 const reports=[];
 for(const part of [4,5,6]){
  const job=plan.parts[part],base='sdk-part-'+String(part).padStart(2,'0');
  const dir=temp(),oldDir=temp(),verify=temp();
  try{
   const old=JSON.parse(readFileSync(download(original,base+'.json',oldDir),'utf8'));
   if(old.game_id!==gid||old.part!==part||old.start_ms!==job.start_ms||
      old.successful_windows!==job.count)throw Error('old_recovery_source_identity_conflict');
   process.env.GAMEPULSE_FINAL_FASTLANE='true';
   let fresh=null,sourceState='NO_FRESH_SOURCE_AVAILABLE';
   try{
    await capture(job,dir);
    fresh=JSON.parse(readFileSync(join(dir,'manifest.json'),'utf8'));
    summarize([job],[fresh]);
    sourceState='SOURCE_READBACK_VALID';
   }catch(e){
    const safe=/^[a-z_]+$/.test(e?.message||'')?e.message:'source_read_unavailable';
    sourceState=safe;
   }finally{delete process.env.GAMEPULSE_FINAL_FASTLANE;}
   const better=!!fresh&&fresh.frames_with_players>old.frames_with_players;
   const qa={schema:'gamepulse.private-original-sdk-recovery.v1',
    game_id:gid,part,attempt_utc:new Date().toISOString(),
    source_status:sourceState,original_immutable:true,
    original:{frames_with_players:old.frames_with_players,
     frames_with_ball:old.frames_with_ball,empty_windows:old.empty_windows,
     archive_sha256:old.archive_sha256},
    retry:fresh?{frames_with_players:fresh.frames_with_players,
     frames_with_ball:fresh.frames_with_ball,empty_windows:fresh.empty_windows}:null,
    real_tracking_improvement:better,physical_possessions_certified:0};
   if(better){
    const archive=join(dir,'recovery-part-'+String(part).padStart(2,'0')+'.tar.gz');
    copyFileSync(join(dir,'checkpoint.tar.gz'),archive);
    uploadOrExisting(recovered,archive,'recovery-part-'+String(part).padStart(2,'0')+'.tar.gz');
    const saved=download(recovered,'recovery-part-'+String(part).padStart(2,'0')+'.tar.gz',verify);
    if(sha(saved)!==sha(archive))throw Error('private_recovery_sha_readback_failed');
    qa.retry.archive_sha256=sha(archive);
   }
   const name='recheck-part-'+String(part).padStart(2,'0')+'.json';
   const file=join(dir,name);writeFileSync(file,JSON.stringify(qa)+'\n');
   uploadOrExisting(recovered,file,name);
   const check=download(recovered,name,verify);
   if(sha(check)!==sha(file))throw Error('private_recheck_manifest_sha_disagrees');
   reports.push(qa);
   console.log('PRIVATE_NATIVE_GSW_PHOENIX_RECHECK',part,'recovered_more',better);
  }finally{
   rmSync(dir,{recursive:true,force:true});
   rmSync(oldDir,{recursive:true,force:true});
   rmSync(verify,{recursive:true,force:true});
  }
 }
 const finished=temp(),readback=temp();
 try{
  const marker=join(finished,'recheck-COMPLETE.json');
  writeFileSync(marker,JSON.stringify({schema:'gamepulse.private-source-recheck-complete.v1',
   game_id:gid,parts:reports.map(r=>r.part),
   improved_parts:reports.filter(r=>r.real_tracking_improvement).map(r=>r.part),
   source_limited_parts:reports.filter(r=>r.source_status!=='SOURCE_READBACK_VALID').map(r=>r.part),
   original_archive_unchanged:true,physical_possessions_certified:0})+'\n');
  uploadOrExisting(recovered,marker,'recheck-COMPLETE.json');
  if(sha(download(recovered,'recheck-COMPLETE.json',readback))!==sha(marker))
   throw Error('private_recheck_terminal_sha_disagrees');
  console.log('PRIVATE_NATIVE_GSW_PHOENIX_RECHECK_SHA_PASSED',
   reports.filter(r=>r.real_tracking_improvement).length,'improved_parts');
 }finally{
  rmSync(finished,{recursive:true,force:true});
  rmSync(readback,{recursive:true,force:true});
 }
}

/** The historical Oct 25 retry must never hijack a current-slate job. */
export function shouldProbeGswPhoenix(env){
 return env.GITHUB_EVENT_NAME==='push'&&
  env.GAMEPULSE_PRODUCTION_ENABLED==='true'&&
  env.GAMEPULSE_GSW_PHOENIX_RECHECK==='true'&&
  env.GAMEPULSE_PRIORITY_FANOUT!=='true'&&
  env.GAMEPULSE_PRIORITY_FINALIZE!=='true';
}

export async function run(){
 assertContext({...process.env,GH_TOKEN:TOKEN});
 delete process.env.GH_TOKEN;
 // All third-party imports occur only after GH_TOKEN leaves process.env.
 const {capture}=await import('./capture.mjs');
 // Two-day release-only fanout: one SHA-locked game per independent public CPU
 // worker; *never* rewrite the shared season index from concurrent jobs.
 // Shared index reconciliation is a separate serial step.
 if(process.env.GAMEPULSE_BATCH_CAPTURE_ENABLED==='true'){
  if(PILOT||!['push','schedule'].includes(process.env.GITHUB_EVENT_NAME))
   throw Error('batch_context_invalid');
  const gid=process.env.GAMEPULSE_BATCH_GAME_ID||'';
  if(!/^00226\d{5}$/.test(gid))throw Error('batch_game_id_invalid');
  // The independent Oct 25 source cohort 0022600112..0118 is already
  // production-accepted. The following exact nine NBA calendar Oct 26
  // fixtures use published tipoffs; do not depend on a single NBA CDN URL
  // that can fail with HTTP 403. Only archive after entire planned window.
  const knownStarts={
    '0022600119':'2026-10-26T23:00:00.000Z',
    '0022600120':'2026-10-26T23:00:00.000Z',
    '0022600121':'2026-10-26T23:30:00.000Z',
    '0022600122':'2026-10-26T23:30:00.000Z',
    '0022600123':'2026-10-27T00:00:00.000Z',
    '0022600124':'2026-10-27T00:00:00.000Z',
    '0022600125':'2026-10-27T00:30:00.000Z',
    '0022600126':'2026-10-27T01:00:00.000Z',
    '0022600127':'2026-10-27T02:00:00.000Z',
    '0022600130':'2026-10-28T00:00:00.000Z',
    '0022600131':'2026-10-28T03:00:00.000Z'
  };
  const tipoff=knownStarts[gid];
  if(!tipoff)throw Error('batch_game_not_in_verified_fixture_cohort');
  const game={id:gid,start:Date.parse(tipoff)};
  if(process.env.GAMEPULSE_BATCH_TIPOFF!==tipoff)
   throw Error('batch_tipoff_not_matched_to_bounded_fixture');
  if(Date.now()<game.start+315*60000){
   await requireOfficialFinal(gid);
   process.env.GAMEPULSE_FINAL_FASTLANE='true';
  }
  const live=names('gamepulse-live-sdk-'+gid);
  if(!live||![...live].some(n=>/^live-\d{13}\.tar\.gz$/.test(n)&&
      live.has(n.replace('.tar.gz','.json'))))
   throw Error('batch_live_source_provenance_unavailable');
  const local={schema:'gamepulse-season-index.v1',games:{}};
  await archiveGame(game,local,capture,{skipSeasonIndex:true});
  if(local.games[gid]?.status!=='complete')
   throw Error('batch_private_game_release_not_complete');
  console.log('PRIVATE_BATCH_GAME_SDK_RELEASE_SHA_ACCEPTED',
              gid,local.games[gid].qa,local.games[gid].windows);
  return;
 }
 // The Oct 25 GSW-PHX one-off source recheck is not a prerequisite for
 // current slate capture/finalization. Opt in explicitly, never from normal
 // push-triggered production jobs; preserve its original seven-day expiry.
 if(shouldProbeGswPhoenix(process.env))await probeGswPhoenixGap(capture);
 if(process.env.GAMEPULSE_PRIORITY_FANOUT==='true'){
  if(PILOT||!['push','schedule'].includes(process.env.GITHUB_EVENT_NAME))throw Error('priority_context_invalid');
  const game={id:process.env.GAMEPULSE_PRIORITY_ID,start:Date.parse(process.env.GAMEPULSE_PRIORITY_TIPOFF||'')};
  const plan=planGame(game),part=Number(process.env.GAMEPULSE_PRIORITY_PART);
  if(!Number.isSafeInteger(part)||part<0||part>12)throw Error('invalid_priority_part');
  const job=plan.parts[part];
  // Once the official NBA schedule marks the game final, every future time
  // window is postgame and can be queried immediately. Never infer empty slots:
  // capture() still requires an actual successful SDK response for every slot.
  if(process.env.GAMEPULSE_FINAL_FASTLANE==='true'){
   await requireOfficialFinal(game.id);
  }else{
   const remaining=job.start_ms+job.count*5000+10*60000-Date.now();
   if(remaining>40*60000)throw Error('priority_window_not_yet_observed');
   if(remaining>0)await new Promise(done=>setTimeout(done,remaining));
  }
  if(Date.now()>game.start+7*24*3600000)throw Error('priority_assignment_expired');
  const tag='gamepulse-sdk-'+game.id;
  ensure(tag);
  const existing=names(tag),base='sdk-part-'+String(part).padStart(2,'0');
  if(!existing)throw Error('private_release_missing');
  const archive=existing.has(base+'.tar.gz'),manifest=existing.has(base+'.json');
  if(manifest&&!archive)repairOrphanManifest(tag,job);
  const current=names(tag),hasArchive=current.has(base+'.tar.gz'),
   hasManifest=current.has(base+'.json');
  if(hasArchive&&!hasManifest)repairArchiveOnly(tag,job);
  if(hasArchive){
   const dir=temp();
   try{validatedPart(tag,job,dir);}finally{rmSync(dir,{recursive:true,force:true});}
  }else await capturePart(tag,job,capture);
  console.log('PRIVATE_PRIORITY_PART_SHA_READBACK_CERTIFIED');
  return;
 }
 if(process.env.GAMEPULSE_PRIORITY_FINALIZE==='true'){
  if(PILOT||!['push','schedule'].includes(process.env.GITHUB_EVENT_NAME))throw Error('priority_context_invalid');
  const game={id:process.env.GAMEPULSE_PRIORITY_ID,
   start:Date.parse(process.env.GAMEPULSE_PRIORITY_TIPOFF||'')};
  planGame(game);
  if(process.env.GAMEPULSE_FINAL_FASTLANE==='true'){
   await requireOfficialFinal(game.id);
  }else if(Date.now()<game.start+315*60000)throw Error('priority_fullgame_not_ready');
  if(Date.now()>game.start+7*24*3600000)throw Error('priority_assignment_expired');
  // Targeted source recovery is self-contained; do not gate real original SDK
  // preservation on the separately shared season-index release/API quota.
  // The canonical source catalog is rebuilt independently from game releases.
  const index={schema:'gamepulse-season-index.v1',games:{}};
  await archiveGame(game,index,capture,{skipSeasonIndex:true});
  if(index.games[game.id]?.status!=='complete')throw Error('priority_fullgame_incomplete');
  console.log('PRIVATE_PRIORITY_FULLGAME_CERTIFIED');
  return;
 }
 await captureElapsedPriority(capture);
 const priorityStart=Date.parse(process.env.GAMEPULSE_PRIORITY_TIPOFF||'');
 if(process.env.GITHUB_EVENT_NAME==='schedule'&&Number.isFinite(priorityStart)
    &&Date.now()>=priorityStart&&Date.now()<priorityStart+315*60000)return;
 const index=readIndex(),games=PILOT?[pilotGame()]:await schedule();
 if(PILOT&&index.games[games[0].id]?.status==='retry')
  index.games[games[0].id].retry_after=0;
 const due=selectDue(games,index,Date.now(),1,process.env.GAMEPULSE_PRIORITY_ID||null);
 console.log('PRIVATE_SEASON_DUE_COUNT',due.length);
 if(process.env.DRY_RUN==='true')return;
 for(const game of due){
  try{await archiveGame(game,index,capture);}
  catch(e){
   const reason=/^[a-z_]+$/.test(e?.message||'')?e.message:'capture_or_archive_failed';
   index.games[game.id]={status:'retry',retry_after:Date.now()+6*3600000,
    last_attempt:new Date().toISOString()};
   writeIndex(index);
   console.error('PRIVATE_SEASON_RETRY_REQUIRED',reason);
   process.exitCode=2;
  }
 }
}
if(process.argv[1]?.endsWith('season_private_release.mjs'))
 run().catch(e=>{
  const reason=/^[a-z_]+$/.test(e?.message||'')?e.message:'collector_failed';
  console.error('PRIVATE_SEASON_STOPPED',reason);process.exitCode=2;
 });
