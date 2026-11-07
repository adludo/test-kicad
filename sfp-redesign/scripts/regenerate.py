#!/usr/bin/python3
"""Rebuild the sequential schematic and physically equivalent footprint library.
Run with Debian's /usr/bin/python3 (pcbnew); KiCad CLI must be on PATH.
"""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for kind in ('CONFIG', 'CACHE', 'DATA'):
    path = Path('/workspace/.kicad-env') / kind.lower()
    path.mkdir(parents=True, exist_ok=True)
    os.environ['XDG_' + kind + '_HOME'] = str(path)
NS = uuid.UUID('b860a7a7-3d20-4ecb-88d3-5e8157c302e9')
def uid(s): return str(uuid.uuid5(NS, s))
def q(s): return json.dumps(str(s), ensure_ascii=False)
def formatted(s):
    # Preserve quoted strings exactly; lay out nested lists for normal KiCad review.
    tokens=iter(re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]',s))
    def read():
        out=[]
        for t in tokens:
            if t==')': return out
            out.append(read() if t=='(' else t)
        return out
    tree=read()[0]
    def emit(v,depth=0):
        if not any(isinstance(x,list) for x in v): return '('+' '.join(v)+')'
        parts=[]
        for x in v:
            if isinstance(x,list): parts.append('\n'+'  '*(depth+1)+emit(x,depth+1))
            else: parts.append((' ' if parts else '')+x)
        return '('+''.join(parts)+'\n'+'  '*depth+')'
    return emit(tree)+'\n'
def natural(s): return [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', s)]
def effects(size=1, extra=''): return f'(effects (font (size {size} {size})) {extra})'
def prop(name, value, x=0, y=0, hide=False):
    return f'(property {q(name)} {q(value)} (at {x} {y} 0) {effects(1, "(hide yes)" if hide else "")})'
with tempfile.TemporaryDirectory() as tmp:
    net = Path(tmp)/'source.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(net),'upstream/sfp-experimenter.kicad_sch'],check=True)
    original = ET.parse(net).getroot()
libparts = {(l.get('lib'), l.get('part')): l for l in original.findall('./libparts/libpart')}
components = {c.get('ref'): c for c in original.findall('./components/comp')}
nets = sorted(original.findall('./nets/net'), key=lambda n:n.get('name'))
netmap = {n.get('name'):f'N{i}' for i,n in enumerate(nets,1)}
nodes = {(n.get('ref'), n.get('pin')): netmap[net.get('name')] for net in nets for n in net.findall('node')}
pinmaps = {}
pins = {}
for ref,c in components.items():
    source = c.find('libsource')
    ps = libparts[(source.get('lib'),source.get('part'))].findall('./pins/pin')
    ps = sorted(ps, key=lambda p:natural(p.get('num')))
    pins[ref] = ps
    pinmaps[ref] = {p.get('num'):str(i) for i,p in enumerate(ps,1)}
# Preserve the schematic-only shield annotation: its original symbol has no pins.
components['#M1'] = ET.fromstring('<comp ref="#M1"><value>SHIELD-COVER</value><footprint/></comp>')
pins['#M1'] = []
pinmaps['#M1'] = {}

# Extract the exact source geometry, including unnamed mechanical pads. Only IDs change.
board = pcbnew.LoadBoard(str(ROOT/'upstream/sfp-experimenter.kicad_pcb'))
pretty = ROOT/'Sequential.pretty'
pretty.mkdir(exist_ok=True)
for fp in board.GetFootprints():
    ref = fp.GetReference()
    assert ref in components
    for pad in fp.Pads():
        old = pad.GetNumber()
        if old:
            assert old in pinmaps[ref], (ref,old)
            pad.SetNumber(pinmaps[ref][old])
    fp.SetPosition(pcbnew.VECTOR2I(0,0))
    fp.SetOrientationDegrees(0)
    fp.SetReference('REF**')
    fp.SetFPID(pcbnew.LIB_ID('Sequential', ref))
    pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(pretty),fp)
    assert (pretty/(ref+'.kicad_mod')).is_file(), ref

zones = [
 ('POWER INPUT / 3.3 V REGULATOR',15,30,180,112,['J6','D1','D2','U1','J3','C3','C4','C6','C8'],3,29),
 ('HOST CONTROL / PULL-UPS',200,30,180,112,['J1','J2','R1','R2','R3','R4','R5'],3,29),
 ('LVDS TRANSMIT / RECEIVE',15,147,180,158,['J4','IC1','J5','IC2','R6','R11','R12','C10','C11','C12','C13','C14','C15','C16','C17'],3,28),
 ('STATUS INDICATORS',200,147,180,112,['R8','Q1','LED1','R9','R7','Q2','LED2','R10'],3,29),
 ('SFP POWER FILTERING',200,264,180,112,['L1','C1','C2','L2','C5','C7','C9'],3,29),
 ('MOUNTING / FIDUCIALS / SHIELD',15,310,180,66,['H1','H2','H3','H4','FID1','FID2','FID3','#M1'],4,24),
 ('SFP INTERFACE: PINS 1-40',385,30,194,155,['SFP1'],1,0),
]
assert sorted(r for *_,rs,cols,pitch in zones for r in rs)==sorted(components)
rootid = uid('root')
libdefs=[]
instances=[]
graphics=[]
rows=[]
def text(s,x,y,size=1.2):
    graphics.append(f'(text {q(s)} (at {x} {y} 0) {effects(size,"(justify left)")} (uuid {q(uid("text"+s))}))')
def line(x1,y1,x2,y2):
    return f'(polyline (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0.254) (type default)) (fill (type none)))'
for heading,zx,zy,zw,zh,refs,cols,pitch in zones:
    text(heading,zx+3,zy+5,1.6)
    graphics.append(f'(rectangle (start {zx} {zy}) (end {zx+zw} {zy+zh}) (stroke (width 0.254) (type default)) (fill (type none)) (uuid {q(uid(heading))}))')
    for idx,ref in enumerate(refs):
        x=zx+zw/cols*(idx%cols+0.5)
        y=zy+24+(idx//cols)*pitch
        if ref=='SFP1': y=zy+83
        # All electrical positions on 1.27 mm grid.
        x=round(x/1.27)*1.27; y=round(y/1.27)*1.27
        ps=pins[ref]; n=len(ps); nl=(n+1)//2; nr=n//2
        half=33.02 if ref=='SFP1' else (10.16 if n!=2 else 2.54)
        height=max(2.54, (max(nl,nr)-1)*2.54+2.54)
        if ref=='SFP1': height=(nl-1)*2.54+2.54
        # Height is half-height; pin rows are spaced 5.08 mm.
        libname=ref.replace('#','')
        fpname = '' if ref=='#M1' else 'Sequential:'+ref
        value=components[ref].findtext('value','')
        base = prop('Reference',ref,0,height+3.81)+prop('Value',value,0,-height-3.81)+prop('Footprint',fpname,hide=True)+prop('Datasheet',components[ref].findtext('datasheet',''),hide=True)
        shape=f'(rectangle (start {-half} {height}) (end {half} {-height}) (stroke (width 0.254) (type default)) (fill (type background)))'
        if n==2 and ref.startswith('C'):
            shape=line(-half,0,-.635,0)+line(.635,0,half,0)+line(-.635,-2.54,-.635,2.54)+line(.635,-2.54,.635,2.54)
            if '+' in pinmaps[ref]:
                shape+=line(-2.54,1.27,-1.27,1.27)+line(-1.905,.635,-1.905,1.905)
        if n==2 and (ref.startswith('D') or ref.startswith('LED')):
            shape=line(-half,0,-1.27,0)+line(1.27,0,half,0)
            shape+=line(-1.27,-2.54,-1.27,2.54)+line(-1.27,2.54,1.27,0)+line(1.27,0,-1.27,-2.54)+line(1.27,-2.54,1.27,2.54)
            if ref.startswith('LED'):
                shape+=line(0,3.175,1.27,4.445)+line(1.27,4.445,.635,4.445)+line(1.27,4.445,1.27,3.81)
        if n==2 and ref.startswith('L') and not ref.startswith('LED'):
            shape=''.join(f'(arc (start {-2.54+i*1.27} 0) (mid {-1.905+i*1.27} 0.8) (end {-1.27+i*1.27} 0) (stroke (width 0.254) (type default)) (fill (type none)))' for i in range(4))
        symbolpins=[]
        for i,p in enumerate(ps):
            left=i<nl; j=i if left else i-nl; count=nl if left else nr
            py=(count-1)*2.54-j*5.08
            px=-(half+5.08) if left else half+5.08
            new=str(i+1); old=p.get('num'); pname=p.get('name'); typ=p.get('type')
            if old!=new: pname += ' ['+old+']'
            # Small passives expose polarity with pin names, not anonymous numbers.
            if n==2: pname='~'
            symbolpins.append(f'(pin {typ} line (at {px} {py} {0 if left else 180}) (length 5.08) (name {q(pname)} {effects(.85)}) (number {q(new)} {effects(.85)}))')
            net=nodes.get((ref,old))
            # Each original pin must have either a net or an explicit no-connect.
            wx=x+px; wy=y-py; end=wx+(-3.81 if left else 3.81)
            if net:
                graphics.append(f'(wire (pts (xy {wx} {wy}) (xy {end} {wy})) (stroke (width 0) (type default)) (uuid {q(uid(ref+new+"wire"))}))')
                graphics.append(f'(label {q(net)} (at {end} {wy} {0 if left else 180}) {effects(.85,"(justify left bottom)")} (uuid {q(uid(ref+new+"label"))}))')
            else:
                graphics.append(f'(no_connect (at {wx} {wy}) (uuid {q(uid(ref+new+"nc"))}))')
            rows.append([ref,old,new,p.get('name'),net or 'NC'])
        definition=f'(symbol {q("Sequential:"+libname)} (pin_names (offset 0.635)) (exclude_from_sim no) (in_bom yes) (on_board yes) {base} (symbol {q(libname+"_0_1")} {shape}) (symbol {q(libname+"_1_1")} {"".join(symbolpins)}))'
        libdefs.append(definition)
        instanceprops=prop('Reference',ref,x,y-height-3.81)+prop('Value',value,x,y+height+3.81)+prop('Footprint',fpname,x,y,True)+prop('Datasheet',components[ref].findtext('datasheet',''),x,y,True)
        for f in components[ref].findall('./fields/field'):
            if f.get('name') not in ['Reference','Value','Footprint','Datasheet','Description']:
                instanceprops+=prop(f.get('name'),f.text or '',x,y,True)
        instanceprops+=prop('Original Footprint',components[ref].findtext('footprint',''),x,y,True)
        instances.append(f'(symbol (lib_id {q("Sequential:"+libname)}) (at {x} {y} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid {q(uid(ref))}) {instanceprops} (instances (project "sfp-sequential" (path {q("/"+rootid)} (reference {q(ref)}) (unit 1)))))')
text('Shield cover: mechanical GND intent (source has no electrical pin)',19,372,0.9)
text('SFP EXPERIMENTER - SEQUENTIAL CONNECTION MAP',18,17,2.5)
text('NET KEY (identical N labels are electrically connected)',390,198,1.5)
for i,net in enumerate(nets):
    text(netmap[net.get('name')]+' = '+net.get('name'),390,207+i*5.08,1.1)
text('Numbers are logical IDs. Brackets show original physical contact names. See pin-map.csv before wiring.',18,386,1.3)
text('Footprints retain source geometry with matching remapped pads. No PCB layout is changed or supplied for this redesign.',18,392,1.3)
text('(C) 2018, 2019 sysmocom GmbH | KiCad port: shabaz, March 2024 | Redesign: 2026 | License: CC-BY-SA (same as source)',18,398,1.2)
sch=f'(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid {q(rootid)}) (paper "A2") (title_block (title "SFP experimenter - sequential mapping") (date "2026-11-07") (rev "1") (company "sysmocom / shabaz; sequential redraw")) (lib_symbols {"".join(libdefs)}) {"".join(graphics)} {"".join(instances)} (sheet_instances (path "/" (page "1"))))\n'
(ROOT/'sfp-sequential.kicad_sch').write_text(formatted(sch))
if not (ROOT/'sfp-sequential.kicad_pro').exists():
    (ROOT/'sfp-sequential.kicad_pro').write_text('{}\n')
# External library agrees exactly with embedded definitions.
external=[re.sub(r'^\(symbol "Sequential:', '(symbol "',d) for d in libdefs]
(ROOT/'Sequential.kicad_sym').write_text(formatted('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+''.join(external)+')'))
for kind,ext in [('sym','kicad_sym'),('fp','pretty')]:
    (ROOT/(kind+'-lib-table')).write_text(f'({kind}_lib_table (version 7) (lib (name "Sequential") (type "KiCad") (uri "${{KIPRJMOD}}/Sequential.{ext}") (options "") (descr "Source geometry, sequential connection IDs")))\n')
with (ROOT/'pin-map.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['reference','original_pin','new_pin','function','net']);w.writerows(rows)
with (ROOT/'net-map.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['new_net','original_net']);w.writerows((netmap[n.get('name')],n.get('name')) for n in nets)
print(f'Rebuilt {len(components)-1} board components, 1 shield annotation, {len(rows)} pins, {len(nets)} nets')
