import type { FeatureCollection } from 'geojson';
export type ZoneId = 'A' | 'B' | 'C';
export const zones = [
 {id:'A' as ZoneId,name:'Palisades Highlands',homes:420,center:[-118.565,34.078],direction:'South toward the coastal corridor',corridor:'Palisades Drive → Sunset Boulevard',route:[[-118.565,34.078],[-118.56,34.062],[-118.553,34.045],[-118.558,34.039]]},
 {id:'B' as ZoneId,name:'Village / Alphabet Streets',homes:680,center:[-118.521,34.053],direction:'Southeast toward Santa Monica',corridor:'Sunset Boulevard → Chautauqua Boulevard',route:[[-118.521,34.053],[-118.515,34.046],[-118.511,34.035],[-118.499,34.027]]},
 {id:'C' as ZoneId,name:'Brentwood / eastern edge',homes:310,center:[-118.491,34.065],direction:'South toward the staging area',corridor:'San Vicente Boulevard corridor',route:[[-118.491,34.065],[-118.488,34.05],[-118.477,34.041],[-118.466,34.035]]},
];
export function routeDecision(zone:ZoneId,condition?:string){
 if(condition==='road_blocked' && zone!=='C')return {available:false,status:'Route held',detail:'Coastal corridor blocked in this exercise. No replacement route is verified. Await traffic reassessment.'};
 if((condition==='wind_shift'||condition==='new_hazard_zone')&&zone==='B')return {available:false,status:'Reassessment required',detail:'Hazard boundary changed in this exercise. Previous routing is withdrawn.'};
 return {available:true,status:'Candidate · demo only',detail:zones.find(z=>z.id===zone)!.direction};
}
export function operationsGeometry(zone:ZoneId,condition?:string):FeatureCollection{
 const selected=zones.find(z=>z.id===zone)!;const decision=routeDecision(zone,condition);
 return {type:'FeatureCollection',features:[
 ...zones.map(z=>({type:'Feature' as const,properties:{kind:'zone',name:`ZONE ${z.id}`,selected:z.id===zone},geometry:{type:'Point' as const,coordinates:z.center}})),
 {type:'Feature',properties:{kind:'egress',name:decision.available?'DEMO EGRESS →':'ROUTE HELD ×',status:decision.available?'candidate':'held'},geometry:{type:'LineString',coordinates:selected.route}},
 {type:'Feature',properties:{kind:'responder',name:'DEMO ENGINE 23 → NORTH'},geometry:{type:'LineString',coordinates:[[-118.548,34.04],[-118.548,34.047],[-118.543,34.054],[-118.543,34.062]]}},
 {type:'Feature',properties:{kind:'responder',name:'DEMO ENGINE 69 → WEST'},geometry:{type:'LineString',coordinates:[[-118.487,34.052],[-118.499,34.053],[-118.509,34.055],[-118.518,34.06]]}},
 ]};
}
export function alertDraft(zone:ZoneId,condition?:string){const z=zones.find(z=>z.id===zone)!;const d=routeDecision(zone,condition);return `EXERCISE ONLY — NOT A PUBLIC ALERT\nZone ${zone}: ${z.name}. ${d.available?`Planning direction: ${z.direction.toLowerCase()}. Candidate corridor: ${z.corridor}. Route remains unverified.`:d.detail}\nFollow local authorities for actual evacuation instructions. No real recipients or live road verification are connected.`;}
