import type { FeatureCollection } from 'geojson';
export const outageAreas=[
 {name:'Highlands · BLACKOUT',start:25,homes:240,ring:[[-118.571,34.075],[-118.556,34.075],[-118.553,34.058],[-118.565,34.055],[-118.576,34.063],[-118.571,34.075]]},
 {name:'Village · BLACKOUT',start:65,homes:380,ring:[[-118.54,34.055],[-118.518,34.055],[-118.513,34.043],[-118.535,34.04],[-118.54,34.055]]},
 {name:'Riviera · BLACKOUT',start:110,homes:170,ring:[[-118.511,34.063],[-118.495,34.062],[-118.49,34.052],[-118.507,34.047],[-118.511,34.063]]},
];
export function blackoutGeometry(elapsed:number):FeatureCollection{return {type:'FeatureCollection',features:outageAreas.filter(a=>elapsed>=a.start).map(a=>({type:'Feature',properties:{name:a.name},geometry:{type:'Polygon',coordinates:[a.ring]}}))}}

const poweredReserve={type:'Feature' as const,properties:{name:'Santa Monica · POWER ON · DEMO'},geometry:{type:'Polygon' as const,coordinates:[[[-118.497,34.034],[-118.466,34.034],[-118.46,34.014],[-118.482,34.01],[-118.497,34.034]]]}};
export function poweredGeometry(elapsed:number):FeatureCollection{const collection:FeatureCollection= {type:'FeatureCollection',features:outageAreas.filter(a=>elapsed<a.start).map(a=>({type:'Feature',properties:{name:a.name.replace('BLACKOUT','POWER ON · DEMO')},geometry:{type:'Polygon',coordinates:[a.ring]}}))};collection.features.push(poweredReserve);return collection}
