---
title: OpenTag3D Format Design
---

# OpenTag3D Format Design

[OpenTag3D](https://opentag3d.info/) is a vendor-neutral filament tag standard. Unlike
[OpenSpool](openspool.md), which stores JSON, OpenTag3D stores a fixed memory map as the
payload of an NDEF record with MIME type `application/opentag3d`.

The built-in reader parses OpenTag3D tags on extended firmware. No configuration is
needed — a tag is recognised by its MIME type, so OpenSpool and OpenTag3D tags can be
mixed freely across spools.

## Supported Versions

| Tag version | Memory map | Notes |
|---|---|---|
| 1.000 – 1.003 | Core `0x00`–`0x6F`, extended `0x70`–`0xBA` | Legacy layout |
| 2.000 – 2.001 | Single block `0x00`–`0xDF` | Current layout, all fields rearranged |

The tag version is read from the first two bytes as an integer with three implied decimal
places (`1003` → `1.003`), and selects the memory map. A newer *minor* version than the
parser knows is read with the known map and a warning in the Klipper log. A newer *major*
version is rejected, as required by the OpenTag3D reader guidelines.

Trailing bytes missing from a short payload are treated as `0x00`.

## Tag Requirements

- NTAG215 or NTAG216 — the U1 hardware cannot read ISO 15693 tags
- The OpenTag3D record must be the first `application/opentag3d` NDEF record
- The reader retrieves the whole tag, 540 bytes on an NTAG215 and 924 on an NTAG216,
  so the record may sit anywhere in tag memory
- NTAG213 is read by the firmware, but its 144 bytes of user memory cannot hold a
  compliant payload and the specification dropped NTAG213 in 2.000. Use it for
  OpenSpool, not for OpenTag3D

## Field Mapping

Temperatures on the tag are stored in degrees Celsius divided by 5 and are multiplied
back out on read.

| OpenTag3D field | `filament_detect` field | Rule |
|---|---|---|
| `material` | `MAIN_TYPE` | uppercased |
| `material_mod` | `SUB_TYPE` | `Basic` when empty |
| `manufacturer` | `VENDOR`, `MANUFACTURER` | `Generic` when empty |
| `color_1` | `RGB_1`, `ALPHA` | RGBA; a zero alpha byte is read as `0xFF` |
| `color_2`–`color_4` | `RGB_2`–`RGB_4` | all-zero entries are skipped; `COLOR_NUMS` is the count of populated colors |
| `diameter` | `DIAMETER` | micrometres on the tag, hundredths of a mm in `filament_detect` |
| `weight` | `WEIGHT` | grams |
| `measured_length` | `LENGTH` | metres |
| `print_temp`, `min_print_temp`, `max_print_temp` | `HOTEND_MIN_TEMP`, `HOTEND_MAX_TEMP` | min/max when populated, otherwise `print_temp` for both |
| `bed_temp`, `min_bed_temp`, `max_bed_temp` | `BED_TEMP` | `bed_temp`, falling back to `min_bed_temp` then `max_bed_temp` |
| `max_dry_temp` | `DRYING_TEMP` | |
| `dry_time` | `DRYING_TIME` | hours |
| `mfg_date` | `MF_DATE` | `YYYYMMDD`; `19700101` when unset |
| `sku` (2.x) | `SKU` | numeric SKUs only, otherwise `0` |
| everything else | – | read but not exposed by `filament_detect` |

`FIRST_LAYER_TEMP` and `OTHER_LAYER_TEMP` are set to `HOTEND_MIN_TEMP`, matching the
OpenSpool parser.

## Snapmaker Orca Naming Convention

Snapmaker Orca matches filaments as `<brand> <type> <subtype>`, which for OpenTag3D is
`<manufacturer> <material> <material_mod>` — for example a tag carrying `Polar Filament`,
`PLA` and `Silk` appears as `Polar Filament PLA Silk`. Spools whose name Snapmaker Orca
does not recognise are hidden there; see
[Enabling OpenRFID](rfid.md#enabling-openrfid) for the generic vendor behaviour.

## Testing

`overlays/firmware-extended/13-patch-rfid/test` contains sample NTAG215 dumps and a
generator for building more:

```bash
cd overlays/firmware-extended/13-patch-rfid/test
python3 -m app.cli opentag3d-v1003-pla-silk.bin
python3 -m app.cli opentag3d-v2001-pla-silk.bin

python3 make_opentag3d_fixture.py 2.001 my-tag.bin
```
