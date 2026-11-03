// NBA-only schedule/control metadata. No licensed player XYZ or raw app records leave private 104.
import {appendFileSync,readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const TOKEN=process.env.GH_TOKEN;
const NOW=Date.now();
const MAX=15; // Include a complete NBA 15-game official-final slate; older incomplete sources retry on subsequent runs.
if(!TOKEN || !process.env.GITHUB_OUTPUT)throw Error('PRIVATE_TOKEN_OR_OUTPUT_MISSING');
async function get(url,privateRead=false){
 if(privateRead){
   const u=new URL(url);
   if(u.hostname!=='api.github.com'||!u.pathname.startsWith('/repos/timeedmonds-maker/104/'))
      throw Error('PRIVATE_GITHUB_ENDPOINT_NOT_ALLOWLISTED');
   try{
     const raw=execFileSync('gh',['api',u.pathname+u.search],{
       encoding:'utf8',timeout:30000,maxBuffer:16*1024*1024,env:process.env});
     return JSON.parse(raw);
   }catch(error){
     const stderr=String(error.stderr||'');
     if(/HTTP 404|status 404|Not Found/.test(stderr))return null;
     // gh's release endpoint can be temporarily throttled while git source
     // access continues working. Recheck through the documented release CLI,
     // never infer that a source archive exists from an unreadable response.
     const tag=u.pathname.split('/').at(-1);
     if(u.pathname.includes('/releases/tags/') && /^gamepulse-sdk-00226\d{5}$/.test(tag)){
       try{
         const raw=execFileSync('gh',['release','view',tag,'--repo',
           'timeedmonds-maker/104','--json','assets'],{
             encoding:'utf8',timeout:30000,maxBuffer:2*1024*1024,env:process.env});
         return JSON.parse(raw);
       }catch(second){
         const detail=String(second.stderr||'');
         if(/HTTP 404|status 404|Not Found/.test(detail))return null;
       }
     }
     throw Error(/rate.limit|secondary.rate.limit|HTTP 429/i.test(stderr)
       ? 'PRIVATE_GITHUB_RATE_LIMITED' : 'PRIVATE_GITHUB_AUTH_OR_SOURCE_UNAVAILABLE');
   }
 }
 const res=await fetch(url,{headers:{
   'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
   'Accept':'application/json, text/plain, */*','Referer':'https://www.nba.com/',
   'Origin':'https://www.nba.com','Accept-Language':'en-US,en;q=0.9'},
   signal:AbortSignal.timeout(12000)});
 if(res.status===404)return null;
 if(!res.ok)throw Error('NBA_PUBLIC_STATUS_'+res.status);
 return res.json();
}
let privateCheckout=null;
async function privateFile(path){
 if(!path.startsWith('gamepulse/fusion/materialized/igp_2026_27_unified_season_v3/'))
   throw Error('PRIVATE_INDEX_PATH_OUTSIDE_CANONICAL');
 if(privateCheckout===null){
  const dir=process.env.RUNNER_TEMP+'/igp-autonomous-index';
  const env=process.env;
  execFileSync('gh',['auth','setup-git'],{timeout:30000,env});
  execFileSync('git',['clone','-q','--depth=1','--filter=blob:none','--sparse',
    '-b','research/gamepulse-clock-boundary-integrity-20261025',
    'https://github.com/timeedmonds-maker/104.git',dir],
    {timeout:90000,maxBuffer:300000,env});
  execFileSync('git',['-C',dir,'sparse-checkout','set',
    'gamepulse/fusion/materialized/igp_2026_27_unified_season_v3'],
    {timeout:90000,maxBuffer:300000,env});
  privateCheckout=dir;
 }
 return JSON.parse(readFileSync(privateCheckout+'/'+path,'utf8'));
}
let fixtures;
for(const source of ['https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',
  'https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json',
  'https://stats.nba.com/stats/scheduleleaguev2?LeagueID=00&Season=2026-27',
  'https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2026/league/00_full_schedule.json']){
  try {
    const payload=await get(source);
    let rows;
    if(source.includes('scheduleLeagueV2')||source.includes('scheduleleaguev2'))rows=((payload.leagueSchedule||payload).gameDates||[])
      .flatMap(d=>d.games||[]).map(x=>({id:String(x.gameId),
        start:Date.parse(x.gameDateTimeUTC),status:String(x.gameStatus)==='3'}));
    else rows=(payload.data.lscd||[]).flatMap(m=>Array.isArray(m.mscd)?
      m.mscd.flatMap(v=>v.g||[]):m.mscd?.g||[]).map(x=>({id:String(x.gid),
      start:Date.parse(String(x.gdtutc)+'T'+String(x.utctm)+':00Z'),
      status:/^final/i.test(String(x.stt||''))}));
    if(rows.length<100)throw Error('NBA_SCHEDULE_INCOMPLETE');
    const map=new Map();
    for(const r of rows){
      if(!/^00226\d{5}$/.test(r.id)||!r.status||!Number.isFinite(r.start)
         ||r.start<Date.parse('2026-10-20T00:00:00Z')
         ||r.start>NOW)continue; // An official final is authoritative; do not delay newly final games by a fixed 315 minutes.
      if(map.has(r.id))throw Error('NBA_DUPLICATE_GAME_ID');
      map.set(r.id,{id:r.id,tipoff:new Date(r.start).toISOString(),start:r.start});
    }
    if(map.size<56)throw Error('NBA_FROZEN_56_MISSING_FROM_SCHEDULE');
    fixtures=[...map.values()].sort((a,b)=>a.start-b.start);
    break;
  }catch(error){console.log('NBA_SCHEDULE_FALLBACK',String(error).slice(0,90));}
}
if(!fixtures){
 const y=new Date(NOW-24*3600000).toISOString().slice(0,10);
 const compact=y.replaceAll('-','');
 const probes=[
  'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates='+compact,
  'https://www.nba.com/games?date='+y,
  'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json',
  'https://stats.gleague.nba.com/stats/scoreboardv3?GameDate='+y+'&LeagueID=00',
  'https://www.nba.com/inside-the-game/blueprint/0022600138',
  'https://api-web.nba.com/games?date='+y
 ];
 await Promise.all(probes.map(async (url)=>{
  try {
   const res=await fetch(url,{headers:{'User-Agent':'Mozilla/5.0',
     'Accept':'application/json,text/html,*/*','Referer':'https://www.nba.com/'},
     signal:AbortSignal.timeout(6000)});
   const raw=await res.text();
   const match=(raw.match(/00226\\d{5}/g)||[]);
   console.log('IGP_OFFICIAL_SCHEDULE_ALTERNATE_PROBE',new URL(url).hostname,
       res.status,raw.length,'nba_game_ID_mentions',new Set(match).size);
  } catch(e){console.log('IGP_OFFICIAL_SCHEDULE_ALTERNATE_PROBE_ERROR',
    new URL(url).hostname,String(e).slice(0,65));}
 }));
 throw Error('NO_AUTHORITATIVE_NBA_SCHEDULE');
}
// A final box score is an independent official NBA authority when the schedule
// snapshot omits a just-completed game. Add only the exact NBA 0153 game if
// its public box confirms final status and a valid tipoff; never infer final.
if(!fixtures.some(g=>g.id==='0022600153')){
  try{
    const box=await get('https://cdn.nba.com/static/json/liveData/boxscore/boxscore_0022600153.json');
    const g=box?.game;
    const start=Date.parse(g?.gameTimeUTC||'');
    if(String(g?.gameId)==='0022600153'&&Number(g?.gameStatus)===3&&
       Number.isFinite(start)&&start<=NOW){
      fixtures.push({id:'0022600153',tipoff:new Date(start).toISOString(),start});
      fixtures.sort((a,b)=>a.start-b.start);
      console.log('IGP_OFFICIAL_FINAL_BOX_0153_DISCOVERED');
    }
  }catch(e){console.log('IGP_OFFICIAL_FINAL_BOX_0153_PENDING');}
}
const index=await privateFile('gamepulse/fusion/materialized/igp_2026_27_unified_season_v3/index.json');
if(index.official_games!==56||Object.keys(index.per_game_model).length!==56)
  throw Error('FROZEN_56_CHANGED');
const add=await privateFile(index.post56_additive_oct28.index);
// Repair a lagging official schedule snapshot with the exact private SHA-locked
// original NBA final box already admitted to the canonical 88-game dataset.
// This verifies the documented source rather than trusting a guessed game date.
if(!fixtures.some(g=>g.id==='0022600153')){
  try{
    const row=add.games['0022600153'];
    if(!row)throw Error('NO_CANONICAL_OFFICIAL_BOX');
    const path=row.official_pbp_original_paths?.[1];
    if(!path?.startsWith('gamepulse/fusion/official_pbp_timing/original_nba_20261029/0022600153/'))
      throw Error('BOX_PATH_NOT_SOURCE_SCOPED');
    const r=await get('https://api.github.com/repos/timeedmonds-maker/104/contents/'+path+
      '?ref=research/gamepulse-clock-boundary-integrity-20261025',true);
    const raw=Buffer.from(r?.content||'','base64');
    if(createHash('sha256').update(raw).digest('hex')!==row.original_nba_boxscore_sha256)
      throw Error('ORIGINAL_BOX_SHA_MISMATCH');
    const game=JSON.parse(raw.toString('utf8')).game;
    const start=Date.parse(game?.gameTimeUTC||'');
    if(String(game?.gameId)!=='0022600153'||Number(game?.gameStatus)!==3||
       !Number.isFinite(start)||start>NOW)
      throw Error('NBA_ORIGINAL_BOX_NOT_FINAL_AND_ELAPSED');
    fixtures.push({id:'0022600153',tipoff:new Date(start).toISOString(),start});
    fixtures.sort((a,b)=>a.start-b.start);
    console.log('IGP_SHA_PINNED_ORIGINAL_NBA_FINAL_BOX_0153_DISCOVERED');
  }catch(err){
    console.log('IGP_ORIGINAL_FINAL_0153_SOURCE_FALLBACK_PENDING',
      String(err?.message||'unavailable').slice(0,60));
  }
}

if(add.base_unified_season_games_frozen!==56)throw Error('ADDITIVE_BASELINE_DRIFT');
const pending=fixtures.filter(g=>!(g.id in index.per_game_model)).filter(g=>{
 const grades=add.games[g.id]?.source_capture_grades||{};
 return !(grades.original_native_xyz==='SHA_FULL_13PART'
          &&grades.original_companion==='COMPLETE_ORIGINAL_RESPONSE'
          &&grades.original_nba_blueprint==='SOURCE_SHA_ACCEPTED'
          &&grades.official_logical_chains==='SHA_VERIFIED');
});
const fresh=pending.filter(g=>!(g.id in add.games));
const incomplete=pending.filter(g=>(g.id in add.games));
const rotation=incomplete.length?Math.floor(NOW/(3*3600000))%incomplete.length:0;
// Recently final games get the first repair attempts; after 48 hours the
// existing incomplete-game rotation resumes, preventing long-term starvation.
const urgent=pending.filter(g=>NOW-g.start<=48*3600000)
  .sort((a,b)=>b.start-a.start||b.id.localeCompare(a.id));
// Newest verified official-final games take priority over earlier incomplete-source
// backlog. Discover dynamically from the NBA schedule; never pin a prior slate.
// Rotation guarantees old source gaps remain eligible after the recent cohort.
const freshNewest=[...fresh].sort((a,b)=>b.start-a.start||b.id.localeCompare(a.id));
const candidates=[...urgent,...freshNewest,...incomplete.slice(rotation),...incomplete.slice(0,rotation)];
const selected=[...new Map(candidates.map(g=>[g.id,g])).values()].slice(0,MAX);
const parts=[],apps=[],games=[],sdkGames=[];
let reused=0,releaseReadDeferred=0;
for(const game of selected){
  // The master already contains a SHA-conserved 13-part native index for this
  // game. A missing companion or Blueprint record is NOT a reason to fetch
  // or recapture any licensed native release part, even under API throttling.
  const alreadyNative=add.games[game.id]?.original_source_13_part_complete===true
    && Boolean(add.games[game.id]?.original_xyz_manifest);
  if(alreadyNative){
    console.log('IGP_EXISTING_ORIGINAL_NATIVE_SOURCE_ALREADY_ACCEPTED',game.id);
  } else {
  try {
    const release=await get('https://api.github.com/repos/timeedmonds-maker/104/releases/tags/gamepulse-sdk-'+game.id,true);
    const a=new Set((release?.assets||[]).map(x=>x.name));
    for(let part=0;part<13;part++){
      const k='sdk-part-'+String(part).padStart(2,'0');
      if(a.has(k+'.tar.gz')&&a.has(k+'.json')){reused++;continue;}
      parts.push({...game,part});
    }
    sdkGames.push(game);
  } catch(err) {
    releaseReadDeferred++;
    console.log('IGP_NATIVE_RELEASE_METADATA_UNAVAILABLE_IDEMPOTENT_ATTEMPT',
      game.id,err?.message==='PRIVATE_GITHUB_RATE_LIMITED'?'RATE_LIMIT':'UNAVAILABLE');
    // The source archive's presence is UNKNOWN, not ABSENT. Dispatch the
    // existing SHA-preserving capture/reconciliation worker on each part;
    // it reads and validates existing assets before any write, and cannot
    // claim completion until the real 13-part release has passed readback.
    // Do not suppress collection because a metadata-only GET was throttled.
    for(let part=0;part<13;part++) parts.push({...game,part});
    sdkGames.push(game);
  }
  }
  if(!add.games[game.id]?.original_companion_original_event_body_sha256 ||
     add.games[game.id]?.source_capture_grades?.original_companion!=='COMPLETE_ORIGINAL_RESPONSE')
       apps.push(game);
  games.push(game);
}
const safe=items=>JSON.stringify({include:items.length?items:[{id:'none',tipoff:'1970-01-01T00:00:00Z',part:0}]});
const entries={count:String(selected.length),games:safe(sdkGames),parts:safe(parts),
  apps:safe(apps),selected:JSON.stringify(selected.map(x=>x.id)),
  release_read_deferred:String(releaseReadDeferred)};
for(const [key,value] of Object.entries(entries))
  appendFileSync(process.env.GITHUB_OUTPUT,key+'='+value+'\n');
console.log('IGP_AUTO_SEASON_DISCOVERY',JSON.stringify({
 official_final:fixtures.length,unified_games:56+Object.keys(add.games).length,
 gaps:pending.length,selected:games.length,missing_original_parts:parts.length,
 existing_parts_reused:reused,missing_companion:apps.length,release_metadata_deferred:releaseReadDeferred}));
