"""Convert an Overpass out-center-geom response into the UI inventory.
Usage: python3 scripts/build-infrastructure.py /path/to/overpass.json
Scope: 34.00,-118.63,34.14,-118.43. Snapshot only; no operational status.
"""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
raw=json.loads(Path(sys.argv[1]).read_text());features=[];assets=[]
for e in raw['elements']:
 t=e.get('tags',{});kind=t.get('amenity') if t.get('amenity') in ['hospital','fire_station'] else 'power' if 'power' in t else 'road'
 ident=f"{e['type']}/{e['id']}";name=t.get('name') or t.get('ref') or {'power':'Mapped power line','road':'Unnamed road','hospital':'Hospital','fire_station':'Fire station'}[kind]
 b=e.get('bounds');c=e.get('center') or ({'lat':(b['minlat']+b['maxlat'])/2,'lon':(b['minlon']+b['maxlon'])/2} if b else e);coords=[c.get('lon'),c.get('lat')]
 if kind in ['hospital','fire_station']:
  if None in coords:continue
  geometry={'type':'Point','coordinates':coords}
 else:
  pts=[[p['lon'],p['lat']] for p in e.get('geometry',[]) if p]
  if len(pts)<2:continue
  geometry={'type':'LineString','coordinates':pts};coords=pts[len(pts)//2]
 props={'id':ident,'kind':kind,'name':name,'status':'unknown','source':'OpenStreetMap','voltage':t.get('voltage','unknown')}
 features.append({'type':'Feature','properties':props,'geometry':geometry})
 if kind!='road':assets.append({'id':ident,'kind':kind,'name':name,'coordinates':coords})
root=Path(__file__).resolve().parents[1]/'public/data'
(root/'infrastructure.json').write_text(json.dumps({'fetchedAt':datetime.now(timezone.utc).isoformat(),'sourceTimestamp':raw['osm3s']['timestamp_osm_base'],'bbox':[34.00,-118.63,34.14,-118.43],'assets':assets,'geojson':{'type':'FeatureCollection','features':features}},separators=(',',':')))
print({k:sum(1 for f in features if f['properties']['kind']==k) for k in ['hospital','fire_station','power','road']})
