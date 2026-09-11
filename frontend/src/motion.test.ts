import test from 'node:test';
import assert from 'node:assert/strict';
import {positionAlong,type MotionRoute} from './MapSimulation';
const route:MotionRoute={id:'test',label:'test',kind:'civilian',coordinates:[[0,0],[0,1],[1,1]],streets:[],length:1};
test('Vehicle interpolation follows corners instead of cutting across blocks',()=>{const p=positionAlong(route,.25);assert.equal(p.point[0],0);assert.ok(p.point[1]>0&&p.point[1]<1);const q=positionAlong(route,.8);assert.equal(q.point[1],1);assert.ok(q.point[0]>0&&q.point[0]<1)});
test('Vehicle endpoints are clamped to the street path',()=>{assert.deepEqual(positionAlong(route,-1).point,[0,0]);assert.deepEqual(positionAlong(route,2).point,[1,1])});
