/** All-game NBA regular-season live scheduler. Public safe: outputs game IDs/tipoff only to Actions matrix. */
export const GAME=/^00226\d{5}$/;
const LIMIT=16;
export function activeGames(schedule,now=Date.now()) {
 if(!Number.isSafeInteger(now))throw Error('invalid_clock');
 const days=schedule?.leagueSchedule?.gameDates;
 if(!Array.isArray(days))throw Error('nba_schedule_schema_changed');
 const found=new Map();
 for(const day of days)for(const row of day.games||[]){
  const id=String(row.gameId||''),start=Date.parse(row.gameDateTimeUTC||'');
  if(!GAME.test(id)||!Number.isFinite(start))continue;
  const status=Number(row.gameStatus);
  // Include recently completed games to resume missing live windows after final.
  // Start observing the official slate before tipoff. No source slot is
  // requested until its entire five-second interval and settle guard elapse.
  // Stop retrying long-finished games from the live pipeline. Full-game
  // recovery is separately gated by genuine SDK position-source readiness.
  const eligible=(status===2&&now>=start-15*60000&&now<=start+6*3600000)
    ||(status===3&&now>=start&&now<=start+5*3600000)
    ||(status===1&&now>=start-30*60000&&now<=start+5*3600000);
  if(eligible)found.set(id,{id,tipoff:new Date(start).toISOString()});
 }
 return [...found.values()].sort((a,b)=>a.tipoff.localeCompare(b.tipoff)).slice(0,LIMIT);
}
export async function discover({request=fetch,now=Date.now()}={}) {
 const url='https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json';
 const res=await request(url,{headers:{'Accept':'application/json','User-Agent':'Mozilla/5.0','Referer':'https://www.nba.com/'},signal:AbortSignal.timeout(20000)});
 if(!res.ok)throw Error('nba_live_schedule_unavailable');
 return activeGames(await res.json(),now);
}
if(process.argv[1]?.endsWith('live_discovery.mjs')){
 const fs=await import('node:fs');
 try{
  const games=await discover();
  const matrix=games.length?games:[{id:'none',tipoff:'1970-01-01T00:00:00.000Z'}];
  const out=process.env.GITHUB_OUTPUT;
  if(!out)throw Error('github_output_not_set');
  fs.appendFileSync(out,'games='+JSON.stringify(matrix)+'\n');
  console.log('LIVE_ACTIVE_GAME_COUNT',games.length);
 }catch(e){console.error(e?.message||'live_discovery_failed');process.exitCode=2;}
}
