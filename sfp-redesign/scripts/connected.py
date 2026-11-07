#!/usr/bin/python3
"""Build the readable functional hierarchy using the overview's symbols and pin maps."""
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
# Standard A4 functional sheets, routed on a 1.27 mm orthogonal grid.
import heapq
from collections import defaultdict
G=1.27
def grid(v):return round(float(v)/G)
def coord(v):return str(round(v*G,4))
base=read((ROOT/'sfp-sequential.kicad_sch').read_text())
lib=kid(base,'lib_symbols');defs={s[1]:s for s in kids(lib,'symbol')}
instances={next(p[2] for p in kids(s,'property') if p[1]=='Reference'):s for s in kids(base,'symbol')}
pinrows=list(csv.DictReader((ROOT/'pin-map.csv').open()))
netby={(r['reference'],r['new_pin']):r['net'] for r in pinrows}
netnames={r['new_net']:r['original_net'] for r in csv.DictReader((ROOT/'net-map.csv').open())}
short={'N1':'LOS','N2':'TX_FAULT','N3':'3.3 V','N4':'GND','N5':'DC jack input','N6':'TX input','N7':'TD+','N8':'TD-','N9':'RD+','N10':'RD-','N11':'RX output','N12':'Fault LED cathode','N13':'LOS LED cathode','N14':'Fault transistor base','N15':'Fault transistor collector','N16':'LOS transistor base','N17':'LOS transistor collector','N18':'MOD_DEF0','N19':'SCL','N20':'SDA','N21':'RATE_SEL','N22':'TX_DISABLE','N23':'VCCR','N24':'VCCT','N25':'Protected DC input'}
pages=[
 ('power','Power input and 3.3 V regulation', [('J6',45,55),('D1',105,55),('U1',175,55),('J3',240,55),('D2',65,110),('C3',105,110),('C4',145,110),('C6',195,110),('C8',240,110)]),
 ('control','Host control and pull-up resistors',[('J1',65,65),('J2',65,125),('R1',145,45),('R2',195,45),('R3',245,45),('R4',170,115),('R5',235,115)]),
 ('lvds','LVDS transmit and receive',[('J4',45,55),('IC1',130,55),('J5',45,125),('IC2',130,125),('R11',205,100),('R6',205,130),('R12',250,130)]),
 ('filters','SFP supply filtering',[('L1',65,55),('C1',125,55),('C2',190,55),('L2',65,120),('C5',125,120),('C7',190,120),('C9',245,120)]),
 ('status','TX fault and loss-of-signal indicators',[('R8',50,60),('Q1',110,60),('R9',180,60),('LED1',245,60),('R7',50,125),('Q2',110,125),('R10',180,125),('LED2',245,125)]),
 ('decoupling','Decoupling and mechanical features',[(r,45+i%4*65,45+i//4*30) for i,r in enumerate(['C10','C11','C12','C13','C14','C15','C16','C17','H1','H2','H3','H4','FID1','FID2','FID3','#M1'])]),
 ('sfp','SFP electrical and cage contact map',[('SFP1',150,100)])]
rootid=uid('readable-root')
def text(s,x,y,size=1.5):return ['text',Q(s),['at',str(x),str(y),'0'],effects(size)+[['justify','left']],['uuid',uid(s+str(x)+str(y))]]
def wire(a,b,key):return ['wire',['pts',['xy',coord(a[0]),coord(a[1])],['xy',coord(b[0]),coord(b[1])]],['stroke',['width','0'],['type','default']],['uuid',uid(key)]]
for pg,title,placements in pages:
    sheetid=uid(pg);page=['kicad_sch',['version','20250114'],['generator',Q('eeschema')],['generator_version',Q('9.0')],['uuid',sheetid],['paper',Q('A4')],['title_block',['title',Q(title)],['rev',Q('2')]]]
    localdefs=['lib_symbols'];obstacles=set();terminals=defaultdict(list);pinloc={};labels={};pindirs={}
    for ref,xx,yy in placements:
        inst=copy.deepcopy(instances[ref]);definition=copy.deepcopy(defs[kid(inst,'lib_id')[1]])
        # Legible pin typography; shared definitions remain consistent across views.
        for unit in kids(definition,'symbol'):
            for pin in kids(unit,'pin'):
                for field in ('name','number'):kid(kid(kid(pin,field),'effects'),'font')[1]=['size','1.27','1.27']
        localdefs.append(definition)
        oldat=kid(inst,'at');ox,oy=map(float,oldat[1:3]);x,y=grid(xx),grid(yy)
        kid(inst,'at')[1:3]=[coord(x),coord(y)];kid(inst,'uuid')[1]=uid(pg+ref)
        for p in kids(inst,'property'):
            at=kid(p,'at');at[1]=coord(grid(float(at[1])-ox)+x);at[2]=coord(grid(float(at[2])-oy)+y)
            if p[1] in ('Reference','Value'):kid(kid(p,'effects'),'font')[1]=['size','1.5','1.5']
        inst[:]=[v for v in inst if not(isinstance(v,list) and v[0]=='instances')]
        inst.append(['instances',['project',Q('sfp-connected'),['path',Q('/'+rootid+'/'+uid('sheet-'+pg)),['reference',Q(ref)],['unit','1']]]])
        page.append(inst)
        ps=[p for u in kids(definition,'symbol') for p in kids(u,'pin')]
        half=grid(33.02 if ref=='SFP1' else (10.16 if len(ps)!=2 else 2.54))
        height=max([abs(grid(kid(p,'at')[2])) for p in ps]+[0])+2
        for gx in range(x-half-1,x+half+2):
            for gy in range(y-height,y+height+1):obstacles.add((gx,gy))
        # Keep routing clear of reference/value text.
        for gy in (y-height-3,y+height+3):
            for gx in range(x-max(half,12),x+max(half,12)+1):
                for dy in (-1,0,1):obstacles.add((gx,gy+dy))
        for p in ps:
            at=kid(p,'at');pos=(x+grid(at[1]),y-grid(at[2]));num=kid(p,'number')[1];net=netby[(ref,num)]
            pinloc[(ref,num)]=pos;pindirs[pos]=at[3]
            if net=='NC':page.append(['no_connect',['at',coord(pos[0]),coord(pos[1])],['uuid',uid(pg+ref+num+'nc')]])
            else:terminals[net].append(pos)
    page.insert(7,localdefs)
    # Route each net into one local connected tree. Crossings are allowed only
    # as perpendicular straight segments, never at a foreign bend or endpoint.
    edges=defaultdict(set);occupied=defaultdict(dict)
    def adj(net):
        a=defaultdict(set)
        for p,q in edges[net]:a[p].add(q);a[q].add(p)
        return a
    # Protect other pins from incidental connections by routing foreign nets.
    ownership={p:n for n,ts in terminals.items() for p in ts}
    for net in sorted(terminals,key=lambda n:(len(terminals[n]),int(n[1:]))):
        ts=terminals[net];forced=(pg=='sfp' and net=='N4')
        tree={(grid(230),grid(150))} if forced else {ts[0]}
        for start in (ts if forced else ts[1:]):
            if start in tree:continue
            todo=[(0,0,start,None)];cost={(start,None):0};prev={};goal=None;serial=0
            while todo:
                _,_,p,d=heapq.heappop(todo);g=cost[(p,d)]
                if p in tree:goal=(p,d);break
                for nd,(dx,dy) in enumerate(((1,0),(-1,0),(0,1),(0,-1))):
                    q=(p[0]+dx,p[1]+dy)
                    if not (15<=q[0]<=219 and 24<=q[1]<=126):continue
                    if q in obstacles and q not in ts:continue
                    if q in ownership and ownership[q]!=net:continue
                    foreign=occupied.get(p,{})
                    # At a crossing continue straight through the existing segment.
                    if foreign and net not in foreign and d is not None and nd!=d:continue
                    bad=False;penalty=0
                    for other,dirs in occupied.get(q,{}).items():
                        if other==net:continue
                        axis=nd//2
                        if len(dirs)!=2 or dirs not in ({0,1},{2,3}) or (0 if dirs=={0,1} else 1)==axis:bad=True;break
                        penalty+=8
                    if bad:continue
                    ng=g+1+(3 if d is not None and nd!=d else 0)+penalty
                    if ng<cost.get((q,nd),1e20):
                        cost[(q,nd)]=ng;prev[(q,nd)]=(p,d);serial+=1
                        h=min(abs(q[0]-t[0])+abs(q[1]-t[1]) for t in tree)
                        heapq.heappush(todo,(ng+h,serial,q,nd))
            if goal is None:raise RuntimeError((pg,net,start,'no route'))
            chain=[goal[0]];state=goal
            while state in prev:state=prev[state];chain.append(state[0])
            for p,q in zip(chain,chain[1:]):edges[net].add(tuple(sorted((p,q))));tree.update((p,q))
            a=adj(net)
            for p,neighbors in a.items():occupied[p][net]={(0 if q[0]>p[0] else 1) if q[1]==p[1] else (2 if q[1]>p[1] else 3) for q in neighbors}
        # One global interface label per net on a sheet, not one per component.
        at=ts[0]
        labels[net]=at
    for net in terminals:
        # Remove routing-seed tails; every wire ends at a pin or a junction.
        while not (pg=='sfp' and net=='N4'):
            graph=adj(net)
            leaves=[p for p,ns in graph.items() if len(ns)==1 and p not in terminals[net]]
            if not leaves:break
            for p in leaves:
                q=next(iter(graph[p]));edges[net].discard(tuple(sorted((p,q))))
        a=adj(net);stops={p for p,ns in a.items() if len(ns)!=2 or len({q[0] for q in ns})!=1 and len({q[1] for q in ns})!=1};stops.update(terminals[net])
        seen=set()
        for p in sorted(stops):
            for q in a[p]:
                edge=tuple(sorted((p,q)))
                if edge in seen:continue
                seen.add(edge);last=p;cur=q
                while cur not in stops:
                    nxt=next(v for v in a[cur] if v!=last);seen.add(tuple(sorted((cur,nxt))));last,cur=cur,nxt
                page.append(wire(p,cur,pg+net+str(p)+str(cur)))
        for p,neighbors in a.items():
            if len(neighbors)>2:page.append(['junction',['at',coord(p[0]),coord(p[1])],['diameter','0'],['color','0','0','0','0'],['uuid',uid(pg+net+str(p))]])
        # Give interface labels their own clear stubs instead of covering pins.
        if pg=='sfp' and net=='N4':
            end=(grid(230),grid(150));angle='0'
        elif len(terminals[net])==1:
            at=terminals[net][0];sgn=-1 if pindirs[at]=='0' else 1
            end=(at[0]+sgn*7,at[1]);angle='0' if sgn<0 else '180'
            page.append(wire(at,end,pg+net+'stub'))
        else:
            choices=[]
            for at,neighbors in a.items():
                if len(neighbors)!=2:continue
                if min(abs(at[0]-p[0])+abs(at[1]-p[1]) for p in pinloc.values())<7:continue
                for dx,dy in ((0,-6),(0,6),(-6,0),(6,0)):
                    end=(at[0]+dx,at[1]+dy)
                    trail={(at[0]+int(dx*k/6),at[1]+int(dy*k/6)) for k in range(1,7)}
                    box={(end[0]+xx,end[1]+yy) for xx in (range(0,8) if dx>0 else range(-7,1)) for yy in range(-2,3)}
                    if any(p in obstacles or p in occupied for p in trail|box):continue
                    choices.append((at[1],at[0],at,end,'180' if dx>0 else '0'))
            if not choices:raise RuntimeError((pg,net,'no clear label stub'))
            _,_,at,end,angle=min(choices)
            # Split the existing wire at the new T-junction for KiCad's graph.
            for segment in list(page):
                if not isinstance(segment,list) or not segment or segment[0]!='wire':continue
                pts=kid(segment,'pts')[1:]
                p0=tuple(grid(v) for v in pts[0][1:]);p1=tuple(grid(v) for v in pts[1][1:])
                if at in (p0,p1):continue
                if (p0[0]==at[0]==p1[0] and min(p0[1],p1[1])<at[1]<max(p0[1],p1[1])) or (p0[1]==at[1]==p1[1] and min(p0[0],p1[0])<at[0]<max(p0[0],p1[0])):
                    page.remove(segment);page.append(wire(p0,at,pg+net+'split1'));page.append(wire(at,p1,pg+net+'split2'));break
            page.append(wire(at,end,pg+net+'stub'))
            page.append(['junction',['at',coord(at[0]),coord(at[1])],['diameter','0'],['color','0','0','0','0'],['uuid',uid(pg+net+'stubdot')]])
        page.append(['global_label',Q(net),['shape','passive'],['at',coord(end[0]),coord(end[1]),angle],effects(1.27)+[['justify','right']],['uuid',uid(pg+net+'label')],['property',Q('Intersheetrefs'),Q('${INTERSHEET_REFS}'),['at',coord(end[0]),coord(end[1]),'0'],effects(1.27)+[['hide','yes']]]])
    page.append(text(title,18,15,2.5))
    used=sorted(terminals,key=lambda n:int(n[1:]))
    for i in range(0,len(used),5):page.append(text(' | '.join(n+': '+short[n] for n in used[i:i+5]),18,170+i//5*5,1.27))
    page.append(text('Dots join wires; undotted crossings are separate. N interfaces connect across sheets.',18,192,1.27))
    if pg=='decoupling':page.append(text('#M1: mechanical shield / GND intent only; source graphic has no electrical pin.',18,185,1.27))
    (ROOT/('connected-'+pg+'.kicad_sch')).write_text(write(page)+'\n')
    print(pg, 'routed',len(terminals),'nets')
root=['kicad_sch',['version','20250114'],['generator',Q('eeschema')],['generator_version',Q('9.0')],['uuid',rootid],['paper',Q('A4')],['lib_symbols']]
root.append(text('SFP experimenter - readable connected mapping',18,18,3))
root.append(text('Seven functional sheets; all components, pins and physical remaps preserved.',18,28,1.5))
for i,(pg,title,_) in enumerate(pages):
    x=22+(i%2)*135;y=42+(i//2)*34
    root.append(['sheet',['at',str(x),str(y)],['size','120','25'],['stroke',['width','0.254'],['type','default']],['fill',['color','0','0','0','0']],['uuid',uid('sheet-'+pg)],['property',Q('Sheetname'),Q(str(i+2)+'. '+title),['at',str(x),str(y-2),'0'],effects(1.5)+[['justify','left']]],['property',Q('Sheetfile'),Q('connected-'+pg+'.kicad_sch'),['at',str(x),str(y+27),'0'],effects(1.27)+[['justify','left']]],['instances',['project',Q('sfp-connected'),['path',Q('/'+rootid),['page',Q(str(i+2))]]]]])
root.append(text('Cross-sheet net key and physical-contact remaps: net-map.csv / pin-map.csv.',18,187,1.5))
root.append(text('CC-BY-SA, same as source. sysmocom (2018/2019); KiCad port shabaz (2024).',18,193,1.27))
root.append(['sheet_instances',['path',Q('/'),['page',Q('1')]]])
(ROOT/'sfp-connected.kicad_sch').write_text(write(root)+'\n')
