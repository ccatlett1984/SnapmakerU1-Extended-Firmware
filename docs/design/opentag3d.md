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

Parsing is OpenRFID's own `opentag3d_tag_processor`, upstream since
[OpenRFID#27](https://github.com/suchmememanyskill/OpenRFID/pull/27). This overlay ships no
OpenTag3D code of its own; it pins the OpenRFID revision and enables the processor in
`openrfid_u1_base.cfg`.

## Supported Versions

| Tag version | Memory map | Status |
|---|---|---|
| 2.000 – 2.001 | Single block `0x00`–`0xDF` | Parsed, from the bundled `schemas/v2.json` |
| 1.000 – 1.003 | Core `0x00`–`0x6F`, extended `0x70`–`0xBA` | **Rejected** — no v1 schema upstream yet |

The tag version is read from the first two bytes as an unsigned big-endian integer with
three implied decimal places (`2001` → `2.001`), and selects the schema by major version.
A newer *minor* version than the bundled schema is decoded with it and a warning in the
log, as the OpenTag3D reader guidelines require. A major version with no schema — which
today means every 1.x tag — is rejected and the scan falls through to the next processor.

Adding 1.x upstream is more than a schema file: the official v1.003 spec splits fields
across a `core` block (`0x00`-`0x6F`) and an `extended` block (`0x70`-`0xBA`), and every
field beyond the basics - `min_print_temp`, `max_print_temp`, `max_dry_temp`, `dry_time`,
`mfg_date` - sits in `extended`. `decode_payload` iterates `core` only, so it would also
need to walk address-ranged blocks.

Trailing bytes missing from a short payload are zero-filled per field, so a payload that
ends partway through an integer still decodes.

## Tag Requirements

- NTAG215 or NTAG216 — the U1 hardware cannot read ISO 15693 tags
- The record is found by MIME type anywhere in the NDEF message, not by position; the
  first `application/opentag3d` record that parses wins
- OpenRFID retrieves the whole tag, 540 bytes on an NTAG215 and 924 on an NTAG216. Its
  reader sizes the read from the tag's capability container, so an NTAG216 is no longer
  truncated at 540 bytes
- NTAG213 is read, but its 144 bytes of user memory cannot hold a compliant payload and
  the specification dropped NTAG213 in 2.000. Use it for OpenSpool, not for OpenTag3D

## Field Mapping

Scaling is declared in the schema, not in the parser: temperatures are stored in degrees
Celsius divided by 5, diameter in micrometres, and TD ×10, and `decode_payload` converts
each to physical units before the mapping below.

| OpenTag3D field | `GenericFilament` | Rule |
|---|---|---|
| `material` | `type` | passed through; `GenericFilament` raises if it is not in `VALID_BASE_MATERIALS`, which the processor catches and reports as a parse failure |
| `material_mod` | `modifiers` | single-element list, empty when unset. `GenericFilament` moves `CF` and `GF` out of the list and on to `type` as `-CF` / `-GF` |
| `manufacturer` | `manufacturer` | passed through, including empty |
| `color_1`–`color_4` | `colors` | `0xAARRGGBB`. The primary is always kept, even when fully transparent; secondaries are skipped when all four bytes are zero |
| `diameter` | `diameter_mm` | millimetres after schema scaling; `0` is carried through as `0.0` |
| `weight` | `weight_grams` | grams, excluding the spool |
| `print_temp`, `min_print_temp`, `max_print_temp` | `hotend_min_temp_c`, `hotend_max_temp_c` | min/max when populated, otherwise `print_temp` for both; a max below the min is rejected as a parse failure |
| `bed_temp` | `bed_temp_c` | `bed_temp` only — `min_bed_temp` and `max_bed_temp` are not consulted |
| `max_dry_temp` | `drying_temp_c` | |
| `dry_time` | `drying_time_hours` | hours |
| `mfg_date` | `manufacturing_date` | ISO 8601; `0001-01-01` when the tag's date bytes are all zero |
| `td` | `td` | opaque thickness |
| everything else | – | decoded but not carried by `GenericFilament` |

`unique_id` is derived from the physical tag UID, so two identical spools remain distinct.

`GenericFilament` has no SKU or length field, so `sku`, `serial`, `barcode` and
`measured_length` are decoded but not exposed.

OpenRFID maps `GenericFilament` on to `filament_detect`; see
[External RFID Support](filament_detect.md).

## Snapmaker Orca Naming Convention

Snapmaker Orca matches filaments as `<brand> <type> <subtype>`, which for OpenTag3D is
`<manufacturer> <material> <material_mod>` — for example a tag carrying `Polar Filament`,
`PLA` and `Pure` appears as `Polar Filament PLA Pure`. Spools whose name Snapmaker Orca
does not recognise are hidden there; see
[Enabling OpenRFID](rfid.md#enabling-openrfid) for the generic vendor behaviour.

Mainline OrcaSlicer matches on `filament_type` and vendor instead of on the preset name.

## Testing

Upstream carries the parser's tests and a Polar Filament NTAG216 dump:

```bash
pytest test/test_opentag3d.py
```

Fixtures live in `test/tags/OpenTag3D/` — a raw payload, the full decoded field
expectations, and the resulting `GenericFilament`.
