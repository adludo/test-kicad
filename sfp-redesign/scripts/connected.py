#!/usr/bin/python3
"""Add an explicitly wired single-sheet view; reuses the overview's symbols/maps."""
import copy
import csv
import json
import os
from pathlib import Path
import re
import uuid

ROOT=Path(__file__).resolve().parents[1]
def kids(s,k):return [v for v in s if isinstance(v,list) and v and v[0]==k]
def kid(s,k):return kids(s,k)[0]
# Keep lexical strings distinct from bare atoms for lossless serialization.
class Quoted(str):pass
def read(s):
    stack=[];root=[];cur=root
    for t in re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]',s):
        if t=='(':
            v=[];cur.append(v);stack.append(cur);cur=v
        elif t==')':cur=stack.pop()
        else:cur.append(Quoted(json.loads(t)) if t.startswith('"') else t)
    return root[0]
def write(v,d=0):
    if not isinstance(v,list):return json.dumps(v) if isinstance(v,Quoted) else str(v)
    if not any(isinstance(x,list) for x in v):return '('+' '.join(write(x) for x in v)+')'
    out='('
    for x in v:
        out+= ('\n'+'  '*(d+1) if isinstance(x,list) else (' ' if out!='(' else ''))+write(x,d+1)
    return out+'\n'+'  '*d+')'
Q=Quoted
NS=uuid.UUID('1555e8a6-c989-41ba-9c4f-40408eb5fb32')
def uid(s):return Q(str(uuid.uuid5(NS,s)))
def effects(size=1):return ['effects',['font',['size',str(size),str(size)]]]
def point(x,y):return ['xy',str(round(x,4)),str(round(y,4))]
base=read((ROOT/'sfp-sequential.kicad_sch').read_text())
lib=copy.deepcopy(kid(base,'lib_symbols'))
defs={s[1]:s for s in kids(lib,'symbol')}
rootid=uid('root')
out=['kicad_sch',['version','20250114'],['generator',Q('eeschema')],['generator_version',Q('9.0')],['uuid',rootid],['paper',Q('User'),'1189','1400'],['title_block',['title',Q('SFP experimenter - all components connected')],['rev',Q('1')]],lib]
def text(s,x,y,size=1.5):out.append(['text',Q(s),['at',str(x),str(y),'0'],effects(size)+[['justify','left']],['uuid',uid(s)]])
seq=0
def wire(a,b):
    global seq
    if a==b:return
    seq+=1
    out.append(['wire',['pts',point(*a),point(*b)],['stroke',['width','0'],['type','default']],['uuid',uid('wire'+str(seq))]])
def junction(x,y):out.append(['junction',['at',str(round(x,4)),str(round(y,4))],['diameter','0'],['color','0','0','0','0'],['uuid',uid(f'j{x},{y}')]])
netnames={r['new_net']:r['original_net'] for r in csv.DictReader((ROOT/'net-map.csv').open())}
pins={(r['reference'],r['new_pin']):r for r in csv.DictReader((ROOT/'pin-map.csv').open())}
netx={n:round(525.78+(int(n[1:])-1)*5.08,4) for n in netnames}
taps={n:[] for n in netnames}
ys=[55.88,57.15]
text('SFP EXPERIMENTER - SINGLE VIEW, ALL COMPONENTS CONNECTED',20,18,3)
text('Every connection is wired. Dots join wires; crossings without dots do not. N1-N25 correspond to the existing pin/net maps.',20,27,1.7)
text('Logical pin IDs; bracketed pin names identify the original contacts. All footprints and electrical intent match the overview.',20,34,1.7)
for inst in kids(base,'symbol'):
    ref=next(p[2] for p in kids(inst,'property') if p[1]=='Reference')
    definition=defs[kid(inst,'lib_id')[1]]
    ps=[p for u in kids(definition,'symbol') for p in kids(u,'pin')]
    left=[p for p in ps if kid(p,'at')[3]=='0']
    side=0 if ys[0]<=ys[1] else 1
    # The large SFP block gets extra space; small symbols remain legible at 1:1.
    extent=max([abs(float(kid(p,'at')[2])) for p in ps]+[2.54])+2.54
    x=254.0 if side==0 else 932.18
    y=ys[side]+extent+7.62
    ys[side]=y+extent+max(1,len(left))*2.54+15.24
    oldat=kid(inst,'at');ox,oy=map(float,oldat[1:3]);dx,dy=x-ox,y-oy
    new=copy.deepcopy(inst);kid(new,'at')[1:3]=[str(x),str(round(y,4))]
    kid(new,'uuid')[1]=uid(ref)
    for p in kids(new,'property'):
        at=kid(p,'at');at[1]=str(round(float(at[1])+dx,4));at[2]=str(round(float(at[2])+dy,4))
    new[:]=[v for v in new if not(isinstance(v,list) and v[0]=='instances')]
    new.append(['instances',['project',Q('sfp-connected'),['path',Q('/'+rootid),['reference',ref],['unit','1']]]])
    out.append(new)
    outer_index=0
    for p in ps:
        at=kid(p,'at');px=x+float(at[1]);py=y-float(at[2]);num=kid(p,'number')[1]
        net=pins[(ref,num)]['net']
        if net=='NC':
            out.append(['no_connect',['at',str(px),str(py)],['uuid',uid(ref+num+'nc')]])
            continue
        # Inner-side pins run directly toward the central backbone; outer-side
        # pins wrap below their own component on separate routing tracks.
        inner=(side==0 and at[3]=='180') or (side==1 and at[3]=='0')
        if inner:
            routey=py
            wire((px,py),(netx[net],routey))
        else:
            outer_index+=1
            bendx=x+(-1 if side==0 else 1)*(55.88+outer_index*2.54)
            routey=round(y+extent+outer_index*2.54,4)
            wire((px,py),(bendx,py));wire((bendx,py),(bendx,routey));wire((bendx,routey),(netx[net],routey))
        taps[net].append(routey)
    if ref=='#M1':text('Mechanical shield; source has no electrical pin',x-45,y+15,1.1)
end=max(ys)
assert end<1370,ys
for net,rows in taps.items():
    x=netx[net]
    # Split backbone at each junction so connectivity is explicit to KiCad.
    rows=sorted(set(rows));previous=45.72
    for y in rows:
        wire((x,previous),(x,y));junction(x,y);previous=y
    # End at the last connected tap, with no dangling wire tail.
    out.append(['label',Q(net),['at',str(x),'45.72','90'],effects(1.2),['uuid',uid(net+'label')]])
# Key in otherwise unused outer margins; do not use labels for connectivity.
for i,(net,name) in enumerate(netnames.items()):text(net+' = '+name,20,55+i*5.08,1.2)
text('Original: sysmocom GmbH (2018, 2019); KiCad port: shabaz (2024). Derived design: CC-BY-SA, same as source.',20,1380,1.6)
out.append(['sheet_instances',['path',Q('/'),['page',Q('1')]]])
(ROOT/'sfp-connected.kicad_sch').write_text(write(out)+'\n')
if not (ROOT/'sfp-connected.kicad_pro').exists():(ROOT/'sfp-connected.kicad_pro').write_text('{}\n')
print('Wired mapping created; column heights:',ys)
