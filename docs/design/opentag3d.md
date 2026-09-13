---
title: OpenTag3D Format Design
---

# OpenTag3D Format Design

[OpenTag3D](https://opentag3d.info/) is a vendor-neutral filament tag standard. Unlike
[OpenSpool](openspool.md), which stores JSON, OpenTag3D stores a fixed memory map as the
payload of an NDEF record with MIME type `application/opentag3d`.

OpenTag3D tags are read by [OpenRFID](rfid.md#readers), which must be enabled. A tag is
recognised by its MIME type, so OpenSpool and OpenTag3D tags can be mixed freely across
spools. The built-in Snapmaker reader does not parse OpenTag3D.

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
- OpenRFID retrieves the whole tag, 540 bytes on an NTAG215 and 924 on an NTAG216, so
  the record may sit anywhere in tag memory
- NTAG213 is read, but its 144 bytes of user memory cannot hold a compliant payload and
  the specification dropped NTAG213 in 2.000. Use it for OpenSpool, not for OpenTag3D

## Field Mapping

Temperatures on the tag are stored in degrees Celsius divided by 5 and are multiplied
back out on read.

| OpenTag3D field | `GenericFilament` | Rule |
|---|---|---|
| `material` | `type` | uppercased; rejected if not in `VALID_BASE_MATERIALS` |
| `material_mod` | `modifiers` | single-element list, empty when unset |
| `manufacturer` | `manufacturer` | `Generic` when empty |
| `color_1`–`color_4` | `colors` | `0xAARRGGBB`; all-zero entries skipped, a zero alpha byte read as `0xFF` |
| `diameter` | `diameter_mm` | micrometres on the tag, mm in `GenericFilament` |
| `weight` | `weight_grams` | grams |
| `print_temp`, `min_print_temp`, `max_print_temp` | `hotend_min_temp_c`, `hotend_max_temp_c` | min/max when populated, otherwise `print_temp` for both |
| `bed_temp`, `min_bed_temp`, `max_bed_temp` | `bed_temp_c` | `bed_temp`, falling back to `min_bed_temp` then `max_bed_temp` |
| `max_dry_temp` | `drying_temp_c` | |
| `dry_time` | `drying_time_hours` | hours |
| `mfg_date` | `manufacturing_date` | ISO 8601; `0001-01-01` when unset |
| `td` | `td` | opaque thickness, stored x10 |
| everything else | – | read but not carried by `GenericFilament` |

`GenericFilament` has no SKU or length field, so `sku`, `serial`, `barcode` and
`measured_length` are not exposed.

OpenRFID maps `GenericFilament` on to `filament_detect` through its webhook exporters;
see [External RFID Support](filament_detect.md).

## Snapmaker Orca Naming Convention

Snapmaker Orca matches filaments as `<brand> <type> <subtype>`, which for OpenTag3D is
`<manufacturer> <material> <material_mod>` — for example a tag carrying `Polar Filament`,
`PLA` and `Pure` appears as `Polar Filament PLA Pure`. Spools whose name Snapmaker Orca
does not recognise are hidden there; see
[Enabling OpenRFID](rfid.md#enabling-openrfid) for the generic vendor behaviour.

## Testing

`test/opentag3d/` in the OpenRFID tree holds sample NTAG dumps:

```bash
python3 -m test.opentag3d
```
