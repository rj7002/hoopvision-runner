/** Protected SDK-only Positions#show readback. Never log raw XYZ or signed URLs.
 * Captures ONLY browser-observed, authorised 200-response SDK slots for a
 * bounded ten-second comparison. No token replay, no alternative endpoints.
 */
import puppeteer from 'puppeteer-core';
import {build} from 'esbuild';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {mkdtempSync,readFileSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const gid='0022600153',start=1793498095000,stop=start+10000;
const program='companion-'+gid+'-positions';
const dest=process.env.IGP_60HZ_PRIVATE_TEMP_CAPTURE;
if(!dest||!dest.startsWith(process.env.RUNNER_TEMP||'/tmp/'))throw Error('PRIVATE_DEST_REQUIRED');
const root=fileURLToPath(new URL('.',import.meta.url));
const scratch=mkdtempSync(join(tmpdir(),'igp60-sdk-'));
let browser,server;
const recorded=new Map(),rawBodies=[],networkGroups=new Map();
const wait=ms=>new Promise(ok=>setTimeout(ok,ms));
function browserBinary(){
  for(const n of ['google-chrome','google-chrome-stable','chromium']){
    try{return execFileSync('which',[n],{encoding:'utf8'}).trim();}catch{}
  }throw Error('CHROME_UNAVAILABLE');
}
try {
  const bundle=join(scratch,'bundle.js');
  await build({entryPoints:[join(root,'browser.js')],bundle:true,platform:'browser',
       format:'iife',outfile:bundle,logLevel:'silent'});
  server=createServer((req,res)=>{
    if(req.url==='/'){res.writeHead(200,{'Content-Type':'text/html'}).end(
      '<!doctype html><div id="overlay"></div><script src="/bundle.js"></script>');return;}
    if(req.url==='/bundle.js'){res.writeHead(200,{'Content-Type':'application/javascript'}).end(readFileSync(bundle));return;}
    res.writeHead(404).end();
  });
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  browser=await puppeteer.launch({headless:true,executablePath:browserBinary(),
      args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage(),pending=new Set();
  page.on('response',r=>{
    let u;try{u=new URL(r.url());}catch{return;}
    if(u.hostname!=='nba-cdn.cloud.easelive.tv'||!u.pathname.includes('/'+program+'/'))return;
    const fam=u.pathname.endsWith('/events/slot')?'positions_slot':
           u.pathname.endsWith('/events')?'program_events':'other_program';
    const key=fam+'_'+r.status();networkGroups.set(key,(networkGroups.get(key)||0)+1);
    if(fam!=='positions_slot'||r.status()!==200)return;
    const job=(async()=>{
      try{
        const bytes=await r.buffer();if(bytes.length>10000000)return;
        const obj=JSON.parse(bytes.toString());
        if(!Array.isArray(obj))return;
        const from=Number(u.searchParams.get('from'));
        if(!Number.isSafeInteger(from)||from<start||from>=stop)return;
        const positions=obj.filter(e=>e?.event==='Positions#show'&&
                                 e?.programId===program);
        if(!positions.length)return;
        const old=recorded.get(from);
        if(old&&JSON.stringify(old)!==JSON.stringify(positions))
          throw Error('CONFLICTING_AUTHORISED_SDK_SOURCE');
        recorded.set(from,positions);
      }catch{}
    })();
    pending.add(job);job.finally(()=>pending.delete(job));
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/',{waitUntil:'domcontentloaded',timeout:15000});
  await page.waitForFunction(()=>typeof window.ephemeralFeed?.initialize==='function',{timeout:12000});
  const ready=await page.evaluate(p=>window.ephemeralFeed.initialize({accountId:'nba',programId:p,timeoutMs:25000}),program);
  if(ready==='ready'||ready==='timeout'){
    for(const ms of [start,start+5000,start+1000,start+6000,start,start+5000]){
      await page.evaluate(ms=>window.ephemeralFeed.seek(ms),ms);
      await wait(1200);
    }
    await wait(3500);await Promise.allSettled([...pending]);
  }
  const events=[...recorded.entries()].sort((a,b)=>a[0]-b[0]).flatMap(([,ev])=>ev);
  // This raw object is written to the protected runner temp directory ONLY.
  if(events.length)writeFileSync(dest,JSON.stringify(events)+'\n',{mode:0o600});
  const slots=events.length;
  const frames=events.flatMap(e=>e.metadata?.keyframes||[]);
  const observed=new Set(frames.map(x=>x.timestamp));
  console.log('IGP_60HZ_AUTHORISED_SDK_METADATA',JSON.stringify({
    sdk_initialize_result:ready,actual_received_slot_events:slots,
    distinct_original_xyz_keyframes:observed.size,
    frame_count_60hz_proven:false,network_response_families:Object.fromEntries(networkGroups),
    private_capture_available:events.length>0}));
  await page.close();
} finally {
  if(browser)await browser.close();
  if(server)await new Promise(ok=>server.close(ok));
  rmSync(scratch,{recursive:true,force:true});
}
