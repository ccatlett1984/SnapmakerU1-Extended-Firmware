# RFID Tag CLI Test Tool

This CLI tool allows you to test OpenSpool JSON payloads, OpenTag3D tag dumps, and NDEF
binary data parsing.

## Usage

```bash
python3 -m app.cli <file>
```

The CLI automatically detects the file type:

- `.json` files are parsed as OpenSpool JSON payloads
- Other files are parsed as NDEF binary data

## Testing Examples

```bash
python3 -m app.cli openspool-pla-basic.json
python3 -m app.cli openspool-petg-rapid.json
python3 -m app.cli openspool-silk-multicolor.json
python3 -m app.cli openspool-abs-transparent.json
python3 -m app.cli openspool-tpu-flexible.json
```

## OpenTag3D

OpenTag3D tags are memory mapped rather than JSON, so the fixtures are NTAG215 dumps
holding an `application/opentag3d` NDEF record:

```bash
python3 -m app.cli opentag3d-v1003-pla-silk.bin
python3 -m app.cli opentag3d-v2001-pla-silk.bin
```

`make_opentag3d_fixture.py` builds further dumps for any supported tag version:

```bash
python3 make_opentag3d_fixture.py 1.003 my-v1-tag.bin
python3 make_opentag3d_fixture.py 2.001 my-v2-tag.bin
```

A dump captured from a real tag works too, as long as it starts at page 0.

## Snapmaker Orca Naming Convention

For proper recognition in Snapmaker Orca, filaments are named: `<brand> <type> <subtype>`

Examples:

- `Generic PLA Basic`
- `Elegoo PETG Rapid`
- `Overture PLA Silk`
