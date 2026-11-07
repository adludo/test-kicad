#!/usr/bin/python3
"""Check actual KiCad exports against upstream, including physical pad geometry."""
import collections
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for kind in ('CONFIG','CACHE','DATA'):
    path=Path('/workspace/.kicad-env')/kind.lower();path.mkdir(parents=True,exist_ok=True)
    os.environ['XDG_'+kind+'_HOME']=str(path)

def parse(s):
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]',s)
    stack=[];root=[];current=root
    for t in tokens:
        if t=='(':
            v=[];current.append(v);stack.append(current);current=v
        elif t==')': current=stack.pop()
        else: current.append(json.loads(t) if t.startswith('"') else t)
    assert not stack
    return root[0]
def children(s,k): return [v for v in s if isinstance(v,list) and v and v[0]==k]
def child(s,k): return children(s,k)[0]
def export(path,out):
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(out),str(path)],check=True)
    return ET.parse(out).getroot()

maps=list(csv.DictReader((ROOT/'pin-map.csv').open()))
new_to_old={(r['reference'],r['new_pin']):r['original_pin'] for r in maps}
old_to_new={(r['reference'],r['original_pin']):r['new_pin'] for r in maps}
netmap={r['new_net']:r['original_net'] for r in csv.DictReader((ROOT/'net-map.csv').open())}
assert sorted(int(n[1:]) for n in netmap)==list(range(1,len(netmap)+1))
summary={}
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    a=export(ROOT/'upstream/sfp-experimenter.kicad_sch',tmp/'old.xml')
    b=export(ROOT/'sfp-sequential.kicad_sch',tmp/'new.xml')
    ac={c.get('ref'):c for c in a.findall('./components/comp')}
    bc={c.get('ref'):c for c in b.findall('./components/comp')}
    assert set(ac)==set(bc), (set(ac)-set(bc),set(bc)-set(ac))
    for ref in ac:
        assert ac[ref].findtext('value')==bc[ref].findtext('value'),ref
        for f in ac[ref].findall('./fields/field'):
            name=f.get('name')
            if name not in ('Footprint','Datasheet','Description'):
                other=bc[ref].find(f'./fields/field[@name="{name}"]')
                assert other is not None and (other.text or '')==(f.text or ''),(ref,name)
    def edges(root,new=False):
        out={}
        for net in root.findall('./nets/net'):
            name=netmap[net.get('name').removeprefix('/')] if new else net.get('name')
            ns=set()
            for n in net.findall('node'):
                ref,p=n.get('ref'),n.get('pin')
                ns.add((ref,new_to_old[(ref,p)] if new else p))
            out[name]=ns
        return out
    assert edges(a)==edges(b,True),'Changed electrical connectivity'
    # Include unconnected source pins, not merely connected netlist nodes.
    def inventory(root):
        parts={(p.get('lib'),p.get('part')):p for p in root.findall('./libparts/libpart')}
        result=set()
        for c in root.findall('./components/comp'):
            l=c.find('libsource');p=parts[(l.get('lib'),l.get('part'))]
            result.update((c.get('ref'),i.get('num')) for i in p.findall('./pins/pin'))
        return result
    assert inventory(a)=={(r['reference'],r['original_pin']) for r in maps}
    assert inventory(b)==set(new_to_old)
    # ERC must actually execute, with exactly the inherited four power errors.
    def erc(path,out):
        run=subprocess.run(['kicad-cli','sch','erc','--exit-code-violations','-o',str(out),str(path)],check=False)
        assert run.returncode==5, ('Unexpected ERC status',run.returncode)
        text=out.read_text()
        return re.findall(r'^\[([^]]+)\]',text,re.M),text
    oldcats,oldt=erc(ROOT/'upstream/sfp-experimenter.kicad_sch',tmp/'old.rpt')
    cats,t=erc(ROOT/'sfp-sequential.kicad_sch',tmp/'new.rpt')
    assert cats==['power_pin_not_driven']*4,cats
    def power_nets(t,root,new=False):
        lookup={(n.get('ref'),n.get('pin')):(netmap[net.get('name').removeprefix('/')] if new else net.get('name')) for net in root.findall('./nets/net') for n in net.findall('node')}
        errors=[]
        for section in t.split('[power_pin_not_driven]:')[1:]:
            match=re.search(r'Symbol (\S+) Pin (\S+)',section)
            assert match
            ref,pin=match.groups()
            errors.append('GND' if ref.startswith('#GND') and not new else lookup[(ref,pin)])
        return sorted(errors)
    assert power_nets(oldt,a)==power_nets(t,b,True)
    (ROOT/'erc-report.rpt').write_text(t)

sch=parse((ROOT/'sfp-sequential.kicad_sch').read_text())
lib=child(sch,'lib_symbols')
for sym in children(lib,'symbol'):
    ps=[p for unit in children(sym,'symbol') for p in children(unit,'pin')]
    nums=[int(child(p,'number')[1]) for p in ps]
    assert sorted(nums)==list(range(1,len(ps)+1)),sym[1]
    sides=collections.Counter(int(child(p,'at')[3]) for p in ps)
    assert set(sides)<= {0,180},sym[1]
    assert abs(sides[0]-sides[180])<=1,sym[1]
    assert len(ps)==sum(sides.values())
# Verify every physical pad at its normalized position, including NPTH holes.
source=pcbnew.LoadBoard(str(ROOT/'upstream/sfp-experimenter.kicad_pcb'))
plugin=pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
def pad_signature(p):
    pos=p.GetPosition();size=p.GetSize();drill=p.GetDrillSize();offset=p.GetOffset()
    return (pos.x,pos.y,size.x,size.y,drill.x,drill.y,offset.x,offset.y,p.GetShape(),p.GetAttribute(),p.GetOrientationDegrees(),p.GetLayerSet().FmtHex())
count=0
for fp in source.GetFootprints():
    ref=fp.GetReference()
    fp.SetPosition(pcbnew.VECTOR2I(0,0));fp.SetOrientationDegrees(0)
    other=plugin.FootprintLoad(str(ROOT/'Sequential.pretty'),ref)
    assert other,ref
    original=collections.Counter((old_to_new[(ref,p.GetNumber())] if p.GetNumber() else '',pad_signature(p)) for p in fp.Pads())
    revised=collections.Counter((p.GetNumber(),pad_signature(p)) for p in other.Pads())
    assert original==revised,ref
    count+=1
summary={'board_components':len(ac),'schematic_only_shield_annotations':1,'pins':len(maps),'nets':len(netmap),'footprints_with_verified_pad_geometry':count,'connectivity':'identical after documented inverse remap','numbering':'all symbols contiguous, unique 1..N; nets N1..N25','balance':'all symbols have opposite-side counts differing by at most one','erc_errors':4,'erc_warnings':0,'erc_errors_inherited_from_source':True}
(ROOT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
