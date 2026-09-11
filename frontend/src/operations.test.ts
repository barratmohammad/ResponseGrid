import test from 'node:test';
import assert from 'node:assert/strict';
import {routeDecision,alertDraft,operationsGeometry} from './operations';
test('Coastal closure withdraws affected route without inventing another',()=>{for(const z of ['A','B'] as const){assert.equal(routeDecision(z,'road_blocked').available,false);assert.match(alertDraft(z,'road_blocked'),/No replacement route is verified/)}assert.equal(routeDecision('C','road_blocked').available,true)});
test('Hazard change withdraws previous Zone B direction',()=>{assert.equal(routeDecision('B','wind_shift').available,false);assert.equal(routeDecision('B','new_hazard_zone').available,false)});
test('Withheld route is marked held on map and every alert is exercise-only',()=>{const route=operationsGeometry('A','road_blocked').features.find(f=>f.properties?.kind==='egress');assert.equal(route?.properties?.status,'held');assert.match(alertDraft('A'),/EXERCISE ONLY/);assert.match(alertDraft('A'),/unverified/)});
