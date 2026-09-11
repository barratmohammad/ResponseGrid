import type { Plugin } from 'vite';
export function providerPlugin(env:Record<string,string>):Plugin{
 const cache=new Map<string,{at:number;data:unknown}>();
 return {name:'responsegrid-local-providers',configureServer(server){server.middlewares.use('/ops-api',async(req,res)=>{
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  if(req.method!=='GET'){res.statusCode=405;res.end(JSON.stringify({error:'Read-only provider bridge'}));return}
  const key=req.url?.split('?')[0];
  if(key==='/connections'){res.end(JSON.stringify({twilio:env.TWILIO_ACCOUNT_SID&&env.TWILIO_AUTH_TOKEN?'Credentials present · not verified':'Credentials required',smsSender:!!env.TWILIO_MESSAGING_SERVICE_SID,dispatch:'Agency integration required',utility:'Utility integration required',satellite:'USGS archive imagery; live feed not connected'}));return}
  const url=key==='/weather'?'https://api.weather.gov/alerts/active?point=34.066,-118.537':key==='/closures'?'https://cwwp2.dot.ca.gov/data/d7/lcs/lcsStatusD07.json':null;
  if(!url){res.statusCode=404;res.end(JSON.stringify({error:'Unknown provider'}));return}
  const cached=cache.get(key!);if(cached&&Date.now()-cached.at<60000){res.end(JSON.stringify(cached.data));return}
  try{const upstream=await fetch(url,{headers:{'User-Agent':'ResponseGrid local incident demo','Accept':'application/json'},signal:AbortSignal.timeout(18000)});if(!upstream.ok)throw Error(`Provider HTTP ${upstream.status}`);const payload=await upstream.json();const fetchedAt=new Date().toISOString();let data;
   if(key==='/weather')data={fetchedAt,source:'National Weather Service',items:payload.features.map((f:any)=>({id:f.id,...f.properties}))};
   else data={fetchedAt,source:'Caltrans District 7 LCS',items:payload.data.map((r:any)=>r.lcs).filter((r:any)=>{const b=r.location.begin;return +b.beginLatitude>=34&&+b.beginLatitude<=34.14&&+b.beginLongitude>=-118.63&&+b.beginLongitude<=-118.43}).map((r:any)=>{const c=r.closure,t=c.closureTimestamp;const ended=c.code1098?.isCode1098==='true'||c.code1022?.isCode1022==='true';return {id:r.index,road:r.location.begin.beginRoute,location:r.location.begin.beginLocationName,direction:r.location.travelFlowDirection,type:c.typeOfClosure,work:c.typeOfWork,lanes:c.lanesClosed,status:ended?'Reported ended':c.code1097?.isCode1097==='true'?'Reported active':'Scheduled / not confirmed active',start:t.closureStartDate+' '+t.closureStartTime,end:t.closureEndDate+' '+t.closureEndTime,updated:r.recordTimestamp.recordDate+' '+r.recordTimestamp.recordTime,coordinates:[+r.location.begin.beginLongitude,+r.location.begin.beginLatitude]}}).sort((a:any,b:any)=>Number(b.status==='Reported active')-Number(a.status==='Reported active')||Number(a.status==='Reported ended')-Number(b.status==='Reported ended'))};
   cache.set(key!,{at:Date.now(),data});res.end(JSON.stringify(data));
  }catch(e){res.statusCode=502;res.end(JSON.stringify({error:e instanceof Error?e.message:'Provider unavailable',source:url}))}
 })}};
}
