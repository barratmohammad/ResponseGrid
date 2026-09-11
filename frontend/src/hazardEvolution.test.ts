import test from 'node:test';
import assert from 'node:assert/strict';
import {blackoutGeometry} from './hazardEvolution';
test('Blackout progression follows playback and resets with the timeline',()=>{assert.equal(blackoutGeometry(0).features.length,0);assert.equal(blackoutGeometry(25).features.length,1);assert.equal(blackoutGeometry(65).features.length,2);assert.equal(blackoutGeometry(110).features.length,3);assert.equal(blackoutGeometry(0).features.length,0)});
