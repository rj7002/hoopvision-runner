import EaseLive from '@ease-live/ease-live-bridge-web';
let client;
let lifecycle={event_counts:{},error_type_counts:{warning:0,fatal:0,unknown:0},
 app_status_counts:{enabled:0,hidden:0,disabled:0},latest_app_status:null};
window.ephemeralFeed = {
  initialize: ({accountId,programId,timeoutMs=16000}) => new Promise(resolve => {
    let settled = false;
    lifecycle={event_counts:{},error_type_counts:{warning:0,fatal:0,unknown:0},
      app_status_counts:{enabled:0,hidden:0,disabled:0},latest_app_status:null};
    const done = value => {if (!settled) {settled = true; resolve(value);}};
    try {
      client = new EaseLive({
        accountId, programId, env:'prod', viewContainer:'#overlay',
        playerPlugin: bridge => {bridge.emit('player.ready', {}); return {};}
      });
      // Only sanitized lifecycle counts are made available to the collector.
      // Do not persist URL, event payload, SDK tokens, app data or error text.
      for (const name of ['easelive.ready','view.ready','bridge.ready',
        'app.ready','app.status','view.error','app.error',
        'bridge.error','easelive.error']) {
        client.on(name, payload => {
          lifecycle.event_counts[name]=(lifecycle.event_counts[name]||0)+1;
          if (name==='app.status' &&
              ['enabled','hidden','disabled'].includes(payload?.status))
            {lifecycle.latest_app_status=payload.status;
             lifecycle.app_status_counts[payload.status]++;}
          if (name.endsWith('.error')) {
            const type=['fatal','warning'].includes(payload?.type)?
              payload.type:'unknown';
            lifecycle.error_type_counts[type]++;
            // Ease Live explicitly distinguishes recoverable warnings from
            // fatal errors. Unclassified errors fail closed.
            if(type!=='warning')done('error');
          }
          if(name==='app.ready')done('ready');
        });
      }
      client.init();
      setTimeout(() => done('timeout'), Math.min(45000, Math.max(5000, timeoutMs)));
    } catch (_) {
      lifecycle.error_type_counts.unknown++;
      done('error');
    }
  }),
  diagnostics: () => ({
    event_counts:{...lifecycle.event_counts},
    error_type_counts:{...lifecycle.error_type_counts},
    app_status_counts:{...lifecycle.app_status_counts},
    latest_app_status:lifecycle.latest_app_status
  }),
  seek: ms => {
    if (!client || !Number.isSafeInteger(ms)) return false;
    client.emit('player.state', {state:'playing'});
    client.emit('player.time', {timecode:ms});
    return true;
  },
  shutdown: () => {try {client?.destroy();} catch (_) {}}
};
