/** Official NBA every-season live SDK selection: no fixed dates or team/game allowlists. */
export const NBA_GAME_ID=/^00[1-5]\d{7}$/;
export const MAX_SIMULTANEOUS=16;
export function activeGames(schedule,now=Date.now()){
 if(!Number.isSafeInteger(now))throw Error('invalid_clock');
 const dates=schedule?.leagueSchedule?.gameDates;
 if(!Array.isArray(dates))throw Error('nba_schedule_schema_changed');
 const games=new Map();
 for(const day of dates)for(const g of day.games||[]){
  const id=String(g.gameId||'');
  if(!NBA_GAME_ID.test(id))continue;
  const start=Date.parse(g.gameDateTimeUTC||'');
  const status=Number(g.gameStatus);
  if(!Number.isSafeInteger(start)||![1,2,3].includes(status))continue;
  // Arm the existing licensed feed shortly BEFORE official tipoff, including
  // games whose published status has not advanced to in-progress.
  // Keep recently final games eligible; originals are never reconstructed.
  if(now<start-8*60000||now>start+6*3600000)continue;
  games.set(id,{id,tipoff:new Date(start).toISOString()});
 }
 const selected=[...games.values()].sort((a,b)=>a.tipoff.localeCompare(b.tipoff));
 if(selected.length>MAX_SIMULTANEOUS)throw Error('nba_concurrent_game_limit_exceeded');
 return selected;
}

/** Plan authorised browser-SDK seeks using source responses actually observed.
 * No signed-token construction, no coordinate modelling and no future slots.
 * Pre-final prioritises oldest original gaps. The immediate post-final phase
 * prioritises the last five minutes before returning to earlier source gaps.
 */
export function sourceBackfillCandidates({tipoff,now,observed,attempted,limit=36,final=false}){
 if(!Number.isSafeInteger(tipoff)||!Number.isSafeInteger(now)||
    !(observed instanceof Set)||!(attempted instanceof Set)||
    !Number.isInteger(limit)||limit<1||limit>72)throw Error('invalid_backfill_plan');
 const begin=Math.floor((tipoff-600000)/5000)*5000;
 const end=Math.floor((Math.min(now-15000,tipoff+5*3600000))/5000)*5000;
 if(end<=begin)return [];
 const missing=[];
 for(let ms=begin;ms<end;ms+=5000)
  if(!observed.has(ms)&&!attempted.has(ms))missing.push(ms);
 if(!final)return missing.slice(0,limit);
 const tail=missing.filter(ms=>ms>=end-5*60000).reverse();
 const earlier=missing.filter(ms=>ms<end-5*60000);
 return [...tail,...earlier].slice(0,limit);
}

/** The official game ID and gameStatus=3 are both mandatory.
 * A matching 'final' result is an observation at poll time, not an invented
 * exact last-play time; no source possession/clock assertion follows from it.
 */
export function officialFinalFromBoxscore(gameId,body){
 if(!NBA_GAME_ID.test(gameId))throw Error('invalid_nba_game_id');
 const g=body?.game;
 if(!g||String(g.gameId)!==gameId)return null;
 const status=Number(g.gameStatus);
 return status===3?true:status===1||status===2?false:null;
}


/** Continue the authentic already-open SDK session briefly after final;
 * stop on explicit app disable, sustained source silence, or a hard cap.
 * Preventing a late queue start is the point; no access-denial bypass.
 */

/** Official schedule is a fallback when box-score CDN status is unavailable.
 * Match the exact game identity, never infer final from elapsed wall time.
 */
export function officialFinalFromSchedule(gameId,doc){
 if(!NBA_GAME_ID.test(gameId))throw Error('invalid_nba_game_id');
 const days=doc?.leagueSchedule?.gameDates;
 if(!Array.isArray(days))return null;
 for(const day of days)for(const g of day.games||[]){
  if(String(g.gameId)!==gameId)continue;
  const status=Number(g.gameStatus);
  return status===3?true:status===1||status===2?false:null;
 }
 return null;
}

export function postfinalWindowDecision({finalSeenAt,now,disabledAt=null,lastSourceAt=null}){
 if(!Number.isSafeInteger(now)||!Number.isSafeInteger(finalSeenAt)||
    now<finalSeenAt)throw Error('invalid_postfinal_timing');
 if(disabledAt!==null)return 'STOP_SOURCE_DISABLED';
 if(now-finalSeenAt>=20*60000)return 'STOP_WINDOW_HARD_CAP';
 if(now-finalSeenAt>=3*60000&&
    (!Number.isSafeInteger(lastSourceAt)||now-lastSourceAt>=4*60000))
  return 'STOP_SOURCE_QUIET';
 return 'CONTINUE_AUTHENTIC_SOURCE';
}

export async function discover({request=fetch,now=Date.now()}={}){
 const res=await request('https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',{
  headers:{Accept:'application/json','User-Agent':'Mozilla/5.0','Referer':'https://www.nba.com/'},
  signal:AbortSignal.timeout(20000)
 });
 if(!res.ok)throw Error('official_nba_schedule_unavailable');
 return activeGames(await res.json(),now);
}

/** A fresh FINAL-triggered SDK attempt is deliberately separate from the
 * already-running live SDK stream. The Kings 0022600215 source experiment
 * recovered player+ball XYZ in a newly initialized postfinal session, then a
 * later session observed official SDK status 'disabled'. Poll the real NBA
 * final flag first; no estimated clock, unauthorized replay or forged URL.
 */
export function finalWatchPollMs(tipoff,now){
 if(!Number.isSafeInteger(tipoff)||!Number.isSafeInteger(now))
  throw Error('invalid_final_watch_clock');
 return now>=tipoff+100*60000?5000:20000;
}
export async function watchAndCaptureOnFinal({
 gameId,tipoff,request=fetch,now=()=>Date.now(),pause=ms=>new Promise(r=>setTimeout(r,ms)),
 launch=async()=>{throw Error('no_capture_launcher');}
}){
 if(!NBA_GAME_ID.test(gameId)||!Number.isSafeInteger(tipoff))
  throw Error('invalid_final_watch_identity');
 let polls=0,errors=0;
 // Every game discovered before tipoff gets its own CPU watcher. The overall
 // scheduled workflow retries interrupted watchers; this process never guesses
 // that a game has ended based only on elapsed wall-clock time.
 const deadline=tipoff+6*3600000;
 while(now()<=deadline){
  let state=null,origin=null;
  try{
   const r=await request('https://cdn.nba.com/static/json/liveData/boxscore/boxscore_'+gameId+'.json',{
    headers:{Accept:'application/json',Referer:'https://www.nba.com/'},
    signal:AbortSignal.timeout(10000)
   });
   if(r.ok){state=officialFinalFromBoxscore(gameId,await r.json());origin='boxscore';}
   else errors++;
  }catch{errors++;}
  // Consult schedule only if the exact game's official boxscore is missing.
  // A known boxscore status 1/2 cannot be overruled by a stale schedule.
  if(state===null&&polls%6===0){
   try{
    const r=await request('https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',{
     headers:{Accept:'application/json',Referer:'https://www.nba.com/'},
     signal:AbortSignal.timeout(15000)
    });
    if(r.ok){state=officialFinalFromSchedule(gameId,await r.json());origin='schedule';}
   }catch{errors++;}
  }
  polls++;
  if(state===true){
   console.log('IGP_EVERGREEN_FRESH_FINAL_CAPTURE_TRIGGER',JSON.stringify({
    game_id:gameId,final_observed_at_utc:new Date(now()).toISOString(),
    official_evidence:origin,polls,errors}));
   return await launch();
  }
  if(polls%30===0)console.log('IGP_EVERGREEN_FINAL_WATCH_ALIVE',
   JSON.stringify({game_id:gameId,polls,errors,official_status:state}));
  await pause(finalWatchPollMs(tipoff,now()));
 }
 console.error('IGP_EVERGREEN_FINAL_WATCH_EXPIRED',gameId,polls,errors);
 throw Error('official_final_not_observed_before_watch_deadline');
}
if(process.argv[1]?.endsWith('live_evergreen_discovery.mjs')){
 const fs=await import('node:fs');
 if(process.argv[2]==='--watch-final'){
  try{
   const gameId=process.env.GAMEPULSE_LIVE_ID;
   const tipoff=Date.parse(process.env.GAMEPULSE_LIVE_TIPOFF||'');
   const {spawn}=await import('node:child_process');
   const result=await watchAndCaptureOnFinal({
    gameId,tipoff,
    launch:()=>new Promise((resolve,reject)=>{
     const child=spawn(process.execPath,['live_realtime_all_games.mjs'],{
      cwd:import.meta.dirname,
      env:process.env,
      stdio:'inherit'
     });
     child.on('error',reject);
     child.on('close',(code,signal)=>{
      if(signal)reject(Error('sdk_collector_signalled_'+signal));
      else resolve(code??1);
     });
    })
   });
   if(result!==0)process.exitCode=result||4;
  }catch(e){
   console.error('IGP_EVERGREEN_FINAL_CAPTURE_FAILED',e?.message||'source_unavailable');
   process.exitCode=4;
  }
 }else{
  try{
   const games=await discover();
   if(!process.env.GITHUB_OUTPUT)throw Error('github_output_not_set');
   fs.appendFileSync(process.env.GITHUB_OUTPUT,'games='+JSON.stringify(games.length?games:[{id:'none',tipoff:'1970-01-01T00:00:00.000Z'}])+'\n');
   console.log('IGP_EVERGREEN_ACTIVE_GAMES',games.length,games.map(g=>g.id).join(','));
  }catch(e){console.error(e?.message||'evergreen_schedule_failed');process.exitCode=2;}
 }
}
