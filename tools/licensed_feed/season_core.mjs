export const CHUNK_WINDOWS=300;
const FIVE_SECONDS=5000;
const START=Date.parse('2026-10-20T00:00:00Z');
const idOK=id=>/^(002|003|004|005|006)\d{7}$/.test(id);

export function planGame(game){
 if(!idOK(game?.id)||!Number.isSafeInteger(game.start))throw Error('invalid_game');
 const begin=Math.floor((game.start-600000)/FIVE_SECONDS)*FIVE_SECONDS;
 const end=Math.floor((game.start+300*60000)/FIVE_SECONDS)*FIVE_SECONDS;
 const windows=(end-begin)/FIVE_SECONDS;
 const parts=[];
 for(let i=0;i<windows;i+=CHUNK_WINDOWS){
  const part=parts.length;
  const job={game_id:game.id,account_id:'nba',program_id:`companion-${game.id}-positions`,
   part,start_ms:begin+i*FIVE_SECONDS,count:Math.min(CHUNK_WINDOWS,windows-i)};
  parts.push(job);
 }
 return {begin,end,windows,parts};
}

export function parseSchedule(doc,kind){
 const games=new Map();
 if(kind==='modern'){
  if(!Array.isArray(doc?.leagueSchedule?.gameDates))throw Error('schedule_schema_changed');
  for(const day of doc.leagueSchedule.gameDates)for(const game of day.games||[]){
   const id=String(game.gameId||''),start=Date.parse(game.gameDateTimeUTC||'');
   if(idOK(id)&&String(game.gameStatus)==='3'&&Number.isFinite(start)&&start>=START)
    games.set(id,{id,start});
  }
 }else if(kind==='legacy'){
  if(!Array.isArray(doc?.data?.lscd))throw Error('schedule_schema_changed');
  for(const month of doc.data.lscd){
   const groups=month?.mscd;
   const rows=Array.isArray(groups)?groups.flatMap(g=>g.g||[]):groups?.g||[];
   for(const game of rows){
    const id=String(game.gid||'');
    const start=Date.parse(String(game.gdtutc||'')+'T'+String(game.utctm||'')+':00Z');
    if(idOK(id)&&/^final/i.test(String(game.stt||''))&&Number.isFinite(start)&&start>=START)
     games.set(id,{id,start});
   }
  }
 }else throw Error('unknown_schedule_source');
 return [...games.values()];
}

export function priorityId(config,now=Date.now()){
 if(config?.schema!=='gamepulse-priority.v1'||!idOK(config.game_id)||
   !Number.isSafeInteger(now))return null;
 const tipoff=Date.parse(config.tipoff_utc||'');
 const expires=Date.parse(config.expires_at_utc||'');
 if(!Number.isFinite(tipoff)||!Number.isFinite(expires)||
   expires<=tipoff||now<tipoff||now>=expires)return null;
 return config.game_id;
}

export function selectDue(games,index,now,max=1,preferred=null){
 if(!Number.isSafeInteger(max)||max<1||max>3)throw Error('invalid_game_limit');
 return games.filter(g=>idOK(g.id)&&Number.isSafeInteger(g.start)
  &&g.start+315*60000<now&&index.games?.[g.id]?.status!=='complete'
  &&(index.games?.[g.id]?.retry_after||0)<=now)
  .sort((a,b)=>(a.id===preferred?-1:0)-(b.id===preferred?-1:0)||a.start-b.start).slice(0,max);
}

export function summarize(parts,manifests){
 if(parts.length!==manifests.length)throw Error('checkpoint_count_mismatch');
 const sum={windows:0,players:0,ball:0,empty:0};
 for(let i=0;i<parts.length;i++){
  const j=parts[i],m=manifests[i];
  if(m.game_id!==j.game_id||m.part!==j.part||m.start_ms!==j.start_ms||
    m.successful_windows!==j.count||m.observed!==true||m.imputed!==false||
    !Number.isSafeInteger(m.frames_with_players)||m.frames_with_players<0||
    !Number.isSafeInteger(m.frames_with_ball)||m.frames_with_ball<0||
    !Number.isSafeInteger(m.empty_windows)||m.empty_windows<0)throw Error('checkpoint_qa_failed');
  sum.windows+=m.successful_windows;
  sum.players+=m.frames_with_players;sum.ball+=m.frames_with_ball;sum.empty+=m.empty_windows;
 }
 return sum;
}

/**
 * Archive completeness (all requested 5s HTTP slots returned) is not the same as
 * tracking completeness (usable NBA player positions within game minutes).
 * Restrict this source-coverage warning to the five middle 25-minute parts:
 * late postgame empty SDK responses must never be called missing gameplay.
 * Fail closed on sparse gameplay rather than inventing coordinates.
 */
export function diagnoseTrackingCoverage(parts,manifests){
 if(parts.length!==manifests.length||parts.length===0)
  throw Error('coverage_manifest_count_mismatch');
 const middle=parts.map((job,i)=>({part:job.part,
  frames:manifests[i]?.frames_with_players,
  ball:manifests[i]?.frames_with_ball,
  empty:manifests[i]?.empty_windows,
  windows:job.count}))
  .filter(x=>x.part>=1&&x.part<=5);
 if(!middle.length)return {state:'INSUFFICIENT_MIDDLE_GAME_EVIDENCE',
   suspicious_parts:[],middle_part_frame_baseline:null};
 if(middle.some(x=>!Number.isSafeInteger(x.frames)||x.frames<0||
   !Number.isSafeInteger(x.ball)||x.ball<0||
   !Number.isSafeInteger(x.empty)||x.empty<0))
   throw Error('invalid_tracking_coverage_counts');
 const frames=middle.map(x=>x.frames).sort((a,b)=>a-b);
 const baseline=frames[Math.floor(frames.length/2)];
 const suspicious_parts=middle.filter(x=>
   x.frames<Math.max(100,Math.floor(baseline*0.2))&&x.empty>=Math.floor(x.windows*0.5))
   .map(x=>x.part);
 return {state:suspicious_parts.length?'SUSPECTED_SOURCE_TRACKING_GAPS':
  'NO_SEVERE_MIDDLE_PART_GAPS_DETECTED',
  middle_part_frame_baseline:baseline,suspicious_parts,
  review_scope:'NATIVE_SOURCE_OBSERVATION_ONLY_NOT_PHYSICAL_POSSESSION_CERTIFICATION'};
}
