# SFP experimenter — sequential schematic

Open **[sfp-connected.pdf](sfp-connected.pdf)** for the readable connected mapping, or **sfp-connected.kicad_pro** to edit it. The former meter-scale wire-backbone drawing is replaced by **eight standard A4 landscape pages**: an index plus seven functional sheets. Keep all `connected-*.kicad_sch` child files beside the root schematic.

| PDF page | Function |
| --- | --- |
| 1 | Hierarchy / page index |
| 2 | DC input, protection and 3.3 V regulator |
| 3 | Host connectors and control pull-ups |
| 4 | LVDS transmitter, receiver and termination |
| 5 | SFP power filtering |
| 6 | TX fault and loss-of-signal indicators |
| 7 | Decoupling, mounting holes, fiducials and shield annotation |
| 8 | SFP electrical pins and cage contacts |

Each net is continuously wired **within its sheet**. Global N1–N25 interfaces join sheets; a local legend explains signal meanings. Junction dots identify connections and undotted crossings remain separate. The drawing has larger pin typography, short regional wiring and clear label stubs instead of a central bus farm. All eight exported pages were rendered and inspected at full-page desktop scale; the pin IDs, references, values and principal paths remain distinguishable without zooming deep into a corner.

Open **[sfp-sequential.pdf](sfp-sequential.pdf)** for the complete single-sheet mapping, or open **sfp-sequential.kicad_pro** in KiCad 9 to edit it. Keep the adjacent symbol library, footprint library and library tables together with the project.

This redraw follows the repository's AGENTS.md: sequential pin IDs on each component, balanced opposite sides (difference at most one for odd pin counts), functional groups, named nets, and explicit remap documentation. SFP1's former four units are consolidated into one 40-pin symbol: pins 1–20 on the left, 21–40 on the right, increasing top to bottom on both sides. The mechanical cage contacts are included. Component references, values, manufacturer fields and electrical pin types are retained. Nets use a single N1–N25 series, with the original names in the sheet legend and [net-map.csv](net-map.csv).

## Pin numbering and physical interfaces

**The displayed IDs are logical connection IDs. They are not replacement manufacturer pinouts.** Use [pin-map.csv](pin-map.csv) to translate to physical contacts when wiring an existing board. Bracketed names on multi-pin symbols show the old contact IDs. The original PCB in `upstream/` is an unchanged reference, not a PCB for the new schematic. Do not update it from this schematic; footprints in this project deliberately use remapped pad IDs.

| Component/interface | Original pin → new ID |
| --- | --- |
| SFP1 electrical contacts | 1–20 unchanged |
| SFP1 cage A contacts | A1–A8 → 21–28; A10–A12 → 29–31 |
| SFP1 cage B contacts | B1–B8 → 32–39; B10 → 40 |
| J1, J2 | 1–5 unchanged; displayed as 3 left / 2 right |
| J3 | 1–4 unchanged; displayed as 2 left / 2 right |
| J4, J5 (SMA) | BG1 → 1; BG2 → 2; C (signal) → 3; TG1 → 4; TG2 → 5 |
| J6 (barrel jack) | 1 → 1; 1-1 → 2; 2 → 3; 3 → 4 |
| Q1, Q2 | B → 1; C → 2; E → 3 |
| D1, D2, LED1, LED2 | A → 1; C → 2 |
| C1, C3, C6, C9 (polarized) | + → 1; − → 2 |
| H1–H4 | B3,2 → 1 |
| Other components | Existing numeric IDs unchanged |

The `Sequential.pretty` library is extracted from the upstream PCB, one footprint per reference. Pad numbers are remapped with the same table; pad position, orientation, size, drill, shape, offset and copper layers are checked against the source. Unnumbered mechanical pads are retained. No footprint geometry is invented. `Original Footprint` properties record the source assignments. External 3D model files referenced by the original footprints are not bundled.

The source's `#M1` shield cover has **no electrical pin**, despite a nearby ground graphic. It is retained as a schematic-only annotation with a mechanical-ground note; no new electrical connection is invented. Fiducials likewise have no electrical pins. Their zero-pin symbols do not require numbering.

## Validation

The actual exported KiCad netlists match after reversing the documented pin/net remaps: **54 board components, 162 pins and 25 nets**. The verifier also checks values and manufacturer fields, the complete pin inventory including unconnected pins, contiguous unique numbering, opposite-side balance and all 54 footprints' physical pad geometry. See [validation.json](validation.json).

**ERC is not clean:** it reports four `power_pin_not_driven` errors, on GND, VCC_3V3, SFP VCCR and SFP VCCT. The same four nets have these errors in the source. This redraw preserves their original electrical types and does not add assertions of a power source. The source's 133 missing-library warnings are resolved by the included libraries; the redraw has zero ERC warnings. See [erc-report.rpt](erc-report.rpt). An inherited ERC condition is not reported as a passing ERC run.

Rebuild and verify with the installed KiCad 9.0.2 and Debian `/usr/bin/python3` (which includes pcbnew):

```sh
cd /workspace/test-kicad/sfp-redesign
mkdir -p /workspace/.kicad-env/config /workspace/.kicad-env/cache /workspace/.kicad-env/data
export XDG_CONFIG_HOME=/workspace/.kicad-env/config
export XDG_CACHE_HOME=/workspace/.kicad-env/cache
export XDG_DATA_HOME=/workspace/.kicad-env/data
/usr/bin/python3 scripts/regenerate.py
/usr/bin/python3 scripts/verify.py
kicad-cli sch export pdf -o sfp-sequential.pdf sfp-sequential.kicad_sch
kicad-cli sch export pdf -o sfp-connected.pdf sfp-connected.kicad_sch
```

Regeneration updates the overview and the entire connected hierarchy. The verifier compares the full hierarchical netlist with the source and overview, checks all references/annotations and unchanged symbol definitions, and independently exports each child with all labels removed. Each child must preserve exactly its expected local pin-to-pin connections; labels may bridge sheets but cannot conceal missing local wires. Standalone checks rebase child instance paths only in temporary copies.

The verifier succeeds only when the electrical, numbering and geometry comparisons pass and ERC contains exactly the four inherited power errors, on the same nets. The connected hierarchy has zero ERC warnings; see [connected-erc-report.rpt](connected-erc-report.rpt). KiCad's ERC command itself returns its violations status; no exclusions or rule suppressions are added. Physical-contact remaps are unchanged. No PCB fabrication or real-hardware test was performed.

## Source and attribution

Source: [shabaz123/sfp-experimenter](https://github.com/shabaz123/sfp-experimenter), commit `0dac77c7e530f5151acdf2d07b71f8a3bb2f96de`. `upstream/` contains unchanged schematic, PCB and README snapshots for provenance and repeatable comparisons.

Original design © 2018, 2019 sysmocom GmbH; KiCad port by shabaz, March 2024. The upstream repository identifies the license as **CC-BY-SA, same as the original source**, without specifying a version. The imported design, derived schematic and extracted libraries retain that license and attribution. Original design link: https://gitea.osmocom.org/electronics/osmo-small-hardware/src/branch/master/sfp-breakout . This derivative changes layout, symbol geometry and connection/pad IDs as documented above; it preserves electrical connectivity.
