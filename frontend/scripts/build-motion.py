"""Build exercise routes along connected OSM road nodes; obey mapped one-way tags."""
import json,math,heapq,sys
from pathlib import Path
raw=json.load(open(sys.argv[1]));nodes={};graph={}
def dist(a,b):return math.hypot((a[0]-b[0])*math.cos(math.radians(34)),a[1]-b[1])*111320
for w in raw['elements']:
 t=w.get('tags',{})
 if w['type']!='way' or 'highway' not in t:continue
 ids=w.get('nodes',[]);geo=w.get('geometry',[])
 for n,p in zip(ids,geo):
  if p:nodes[n]=[p['lon'],p['lat']]
 for u,v in zip(ids,ids[1:]):
  if u not in nodes or v not in nodes:continue
  cost=dist(nodes[u],nodes[v]);name=t.get('name','Connecting road');one=t.get('oneway','yes' if t.get('junction')=='roundabout' else 'no')
  if one!='-1':graph.setdefault(u,[]).append((v,cost,name))
  if one not in ['yes','1','true']:graph.setdefault(v,[]).append((u,cost,name))
# Restrict to the central road network that supports connected outbound and return trips.
reverse={}
for u,edges in graph.items():
 for v,_,_ in edges:reverse.setdefault(v,[]).append((u,0,''))
def reachable(seed,adj):
 seen={seed};stack=[seed]
 while stack:
  for v,_,_ in adj.get(stack.pop(),[]):
   if v not in seen:seen.add(v);stack.append(v)
 return seen
seed=min(graph,key=lambda n:dist(nodes[n],[-118.522,34.045]))
connected=reachable(seed,graph)&reachable(seed,reverse)
graph={u:[e for e in edges if e[0] in connected] for u,edges in graph.items() if u in connected}
print('Round-trip road nodes:',len(graph))
def path(start,end):
 a=min(graph,key=lambda n:dist(start,nodes[n]));b=min(graph,key=lambda n:dist(end,nodes[n]));q=[(0,a)];cost={a:0};prev={}
 while q:
  d,u=heapq.heappop(q)
  if d!=cost[u]:continue
  if u==b:break
  for v,c,name in graph.get(u,[]):
   nd=d+c
   if nd<cost.get(v,1e20):cost[v]=nd;prev[v]=(u,name);heapq.heappush(q,(nd,v))
 if b not in cost:
  b=min(cost,key=lambda n:dist(end,nodes[n]))
  if dist(end,nodes[b])>500:raise ValueError('No connected route within 500m')
 ids=[b];names=[]
 while ids[-1]!=a:
  u,name=prev[ids[-1]];names.append(name);ids.append(u)
 ids.reverse();names.reverse();streets=[]
 for n in names:
  if not streets or streets[-1]!=n:streets.append(n)
 return [nodes[n] for n in ids],streets,cost[b]
spec=[('A','Residents · Highlands','civilian',[-118.568,34.079],[-118.516,34.028]),('B','Residents · Village','civilian',[-118.522,34.048],[-118.49,34.022]),('C','Residents · Brentwood','civilian',[-118.49,34.049],[-118.457,34.034]),('E23','Engine 23','engine',[-118.5544,34.0422],[-118.562,34.069]),('E69','Engine 69','engine',[-118.5225,34.0451],[-118.545,34.052])]
spec += [
 ('A2','Residents · Marquez','civilian',[-118.561,34.048],[-118.514,34.026]),
 ('A3','Residents · Las Lomas','civilian',[-118.551,34.056],[-118.511,34.026]),
 ('A4','Residents · Via de la Paz','civilian',[-118.536,34.048],[-118.498,34.026]),
 ('B2','Residents · Swarthmore','civilian',[-118.523,34.046],[-118.486,34.026]),
 ('B3','Residents · Haverford','civilian',[-118.528,34.04],[-118.49,34.024]),
 ('B4','Residents · Amalfi','civilian',[-118.516,34.058],[-118.476,34.033]),
 ('B5','Residents · Riviera','civilian',[-118.505,34.052],[-118.479,34.033]),
 ('C2','Residents · Brentwood Park','civilian',[-118.488,34.057],[-118.466,34.034]),
 ('C3','Residents · Westgate','civilian',[-118.478,34.049],[-118.46,34.026]),
 ('C4','Residents · Montana','civilian',[-118.497,34.034],[-118.47,34.025]),
 ('E19','Engine 19','engine',[-118.4795,34.0585],[-118.512,34.053]),
 ('E59','Engine 59','engine',[-118.4445,34.0366],[-118.505,34.05]),
 ('E37','Engine 37','engine',[-118.449,34.06],[-118.514,34.06]),
 ('E71','Engine 71','engine',[-118.435,34.08],[-118.49,34.058]),
 ('T23','Truck 23','engine',[-118.554,34.042],[-118.555,34.06]),
 ('T69','Truck 69','engine',[-118.522,34.045],[-118.517,34.058]),
]
spec += [
 ('A5','Residents · Bienveneda','civilian',[-118.543,34.055],[-118.49,34.025]),
 ('A6','Residents · Muskingum','civilian',[-118.539,34.05],[-118.482,34.024]),
 ('B6','Residents · Iliff','civilian',[-118.519,34.049],[-118.477,34.03]),
 ('B7','Residents · Kagawa','civilian',[-118.517,34.052],[-118.485,34.021]),
 ('B8','Residents · Alma Real','civilian',[-118.526,34.037],[-118.486,34.024]),
 ('B9','Residents · San Remo','civilian',[-118.506,34.045],[-118.465,34.028]),
 ('C5','Residents · Bristol','civilian',[-118.492,34.054],[-118.463,34.025]),
 ('C6','Residents · 26th Street','civilian',[-118.49,34.04],[-118.475,34.018]),
 ('E99','Engine 99','engine',[-118.4404,34.1318],[-118.481,34.06]),
 ('E109','Engine 109','engine',[-118.4921,34.1307],[-118.495,34.055]),
 ('E59B','Engine 59B','engine',[-118.4445,34.0366],[-118.52,34.048]),
 ('T37','Truck 37','engine',[-118.449,34.06],[-118.506,34.052]),
 ('T19','Truck 19','engine',[-118.4795,34.0585],[-118.529,34.044]),
 ('SM1','Santa Monica Engine 1','engine',[-118.4925,34.0194],[-118.519,34.048]),
 ('SM5','Santa Monica Engine 5','engine',[-118.4567,34.0142],[-118.503,34.049]),
 ('E71B','Engine 71B','engine',[-118.435,34.08],[-118.514,34.052]),
]
out=[]
for id,label,kind,a,b in spec:
 pts,streets,length=path(a,b)
 item=dict(id=id,label=label,kind=kind,coordinates=pts,streets=streets,length=length)
 if kind=='engine':item['returnCoordinates']=path(pts[-1],pts[0])[0]
 out.append(item);print(id,round(length))
Path('frontend/public/data/motion-routes.json').write_text(json.dumps(out,separators=(',',':')))
