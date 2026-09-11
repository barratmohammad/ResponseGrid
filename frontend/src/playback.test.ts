import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {vehiclePhase} from './playback';
test('Fire trucks continue on a return leg and dispatch again past three minutes',()=>{assert.equal(vehiclePhase(96,0,95,true).returning,true);assert.ok(vehiclePhase(181,0,95,true).fraction>0);assert.equal(vehiclePhase(191,0,95,true).returning,false);assert.ok(vehiclePhase(381,0,95,true).visible)});
test('Every engine route has a connected return trip',()=>{const routes=JSON.parse(readFileSync(new URL('../public/data/motion-routes.json',import.meta.url),'utf8'));for(const r of routes.filter((r:any)=>r.kind==='engine')){assert.deepEqual(r.returnCoordinates[0],r.coordinates.at(-1),r.id);assert.deepEqual(r.returnCoordinates.at(-1),r.coordinates[0],r.id)}});
