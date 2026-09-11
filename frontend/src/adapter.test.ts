import test from 'node:test';
import assert from 'node:assert/strict';
import {adapter} from './adapter';

test('run HTTP payload matches the actual FastAPI RunRequest',async()=>{
 const prior=globalThis.fetch;const calls:{url:string;body:any}[]=[];
 globalThis.fetch=async(url,init)=>{calls.push({url:String(url),body:JSON.parse(String(init?.body))});return new Response(JSON.stringify({run_id:'real-id'}),{status:200})};
 try{assert.equal((await adapter.start('sequential','palisades_wildfire')).run_id,'real-id');assert.deepEqual(calls,[{url:'/api/runs',body:{execution_mode:'sequential',scenario:'palisades_wildfire'}}])}finally{globalThis.fetch=prior}
});
test('injection follows the child run when API returns only its parent',async()=>{
 const prior=globalThis.fetch;const bodies:any[]=[];
 globalThis.fetch=async(url,init)=>{if(init?.method==='POST'){bodies.push(JSON.parse(String(init.body)));return new Response(JSON.stringify({ok:true,parent_run_id:'parent'}))}return new Response(JSON.stringify({runs:[{run_id:'child',parent_run_id:'parent',injected_event:'road_blocked'}]}))};
 try{assert.equal((await adapter.inject('parent',{event_type:'road_blocked',target:'Pacific Coast Highway'})).run_id,'child');assert.deepEqual(bodies,[{type:'road_blocked',payload:{target:'Pacific Coast Highway'}}])}finally{globalThis.fetch=prior}
});
test('named SSE errors stay distinct from connection errors and stream cleans up',()=>{
 const prior=globalThis.EventSource;let current:any;
 class FakeSource {onopen:any;onmessage:any;onerror:any;closed=false;listeners:Record<string,any>={};constructor(){current=this}addEventListener(type:string,fn:any){this.listeners[type]=fn}close(){this.closed=true}}
 globalThis.EventSource=FakeSource as any;const events:any[]=[];const links:string[]=[];
 try{const stop=adapter.subscribe('run',e=>events.push(e),s=>links.push(s));current.onopen();current.onerror({});current.listeners.error({});assert.equal(links.at(-1),'reconnecting');const raw={data:JSON.stringify({ts:1789140000,run_id:'run',seq:1,event_type:'error',message:'Specialist failed',payload:{}})};current.onerror(raw);current.listeners.error(raw);assert.equal(events[0].message,'Specialist failed');assert.equal(links.at(-1),'reconnecting');stop();assert.equal(current.closed,true)}finally{globalThis.EventSource=prior}
});
