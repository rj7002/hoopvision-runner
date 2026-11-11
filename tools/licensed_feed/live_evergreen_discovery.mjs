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
export async function discover({request=fetch,now=Date.now()}={}){
 const res=await request('https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',{
  headers:{Accept:'application/json','User-Agent':'Mozilla/5.0','Referer':'https://www.nba.com/'},
  signal:AbortSignal.timeout(20000)
 });
 if(!res.ok)throw Error('official_nba_schedule_unavailable');
 return activeGames(await res.json(),now);
}
if(process.argv[1]?.endsWith('live_evergreen_discovery.mjs')){
 const fs=await import('node:fs');
 try{
  const games=await discover();
  if(!process.env.GITHUB_OUTPUT)throw Error('github_output_not_set');
  fs.appendFileSync(process.env.GITHUB_OUTPUT,'games='+JSON.stringify(games.length?games:[{id:'none',tipoff:'1970-01-01T00:00:00.000Z'}])+'\n');
  console.log('IGP_EVERGREEN_ACTIVE_GAMES',games.length,games.map(g=>g.id).join(','));
 }catch(e){console.error(e?.message||'evergreen_schedule_failed');process.exitCode=2;}
}
