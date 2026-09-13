#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-PackageHomePage: https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware
# SPDX-FileCopyrightText: Copyright (c) 2026 @paxx12

# Builds NTAG215 memory dumps holding an OpenTag3D NDEF record, for use as
# test fixtures with `python3 -m app.cli <file>`.
#
# The dumps mirror what fm175xx_reader.py hands to filament_protocol_ndef:
# 540 bytes starting at page 0, so the UID, capability container and NDEF TLV
# are all present.

import argparse
import struct

MIME_TYPE = b'application/opentag3d'
NTAG215_SIZE = 540
CAPABILITY_CONTAINER = bytes([0xE1, 0x10, 0x3E, 0x00])

# Sample spool: Polar Filament PLA Silk, 1.75mm, 1kg
SAMPLE = {
    'material': 'PLA',
    'material_mod': 'Silk',
    'manufacturer': 'Polar Filament',
    'color_1': (0xFF, 0xA6, 0x4D, 0xFF),
    'color_2': (0x00, 0x66, 0xCC, 0xFF),
    'diameter': 1750,
    'weight': 1000,
    'print_temp': 42,        # 210 C
    'min_print_temp': 38,    # 190 C
    'max_print_temp': 44,    # 220 C
    'bed_temp': 12,          # 60 C
    'min_bed_temp': 10,      # 50 C
    'max_bed_temp': 13,      # 65 C
    'max_dry_temp': 10,      # 50 C
    'dry_time': 8,
    'measured_length': 330,
    'mfg_date': (2026, 3, 14),
    'sku': '12345678',
}

# offset, length, type, field id
LAYOUT_V1 = [
    (0x00, 2, 'int', 'tag_version'),
    (0x02, 5, 'str', 'material'),
    (0x07, 5, 'str', 'material_mod'),
    (0x1B, 16, 'str', 'manufacturer'),
    (0x4B, 4, 'rgba', 'color_1'),
    (0x50, 4, 'rgba', 'color_2'),
    (0x5C, 2, 'int', 'diameter'),
    (0x5E, 2, 'int', 'weight'),
    (0x60, 1, 'int', 'print_temp'),
    (0x61, 1, 'int', 'bed_temp'),
    (0xA0, 4, 'date', 'mfg_date'),
    (0xB0, 2, 'int', 'measured_length'),
    (0xB2, 1, 'int', 'max_dry_temp'),
    (0xB3, 1, 'int', 'dry_time'),
    (0xB4, 1, 'int', 'min_print_temp'),
    (0xB5, 1, 'int', 'max_print_temp'),
    (0xB6, 1, 'int', 'min_bed_temp'),
    (0xB7, 1, 'int', 'max_bed_temp'),
]

LAYOUT_V2 = [
    (0x00, 2, 'int', 'tag_version'),
    (0x02, 5, 'str', 'material'),
    (0x07, 5, 'str', 'material_mod'),
    (0x0C, 16, 'str', 'manufacturer'),
    (0x3C, 4, 'rgba', 'color_1'),
    (0x40, 4, 'rgba', 'color_2'),
    (0x6C, 16, 'str', 'sku'),
    (0x84, 4, 'date', 'mfg_date'),
    (0x8C, 2, 'int', 'diameter'),
    (0x90, 1, 'int', 'print_temp'),
    (0x91, 1, 'int', 'min_print_temp'),
    (0x92, 1, 'int', 'max_print_temp'),
    (0x94, 1, 'int', 'bed_temp'),
    (0x95, 1, 'int', 'min_bed_temp'),
    (0x96, 1, 'int', 'max_bed_temp'),
    (0x9A, 1, 'int', 'max_dry_temp'),
    (0x9B, 1, 'int', 'dry_time'),
    (0x9E, 2, 'int', 'weight'),
    (0xA2, 2, 'int', 'measured_length'),
]

LAYOUTS = {
    1: (LAYOUT_V1, 0xBB),
    2: (LAYOUT_V2, 0xE0),
}


def encode_field(value, length, field_type):
    if field_type == 'int':
        return value.to_bytes(length, 'big')
    if field_type == 'str':
        return value.encode('utf-8')[:length].ljust(length, b'\x00')
    if field_type == 'rgba':
        return bytes(value)
    if field_type == 'date':
        return struct.pack('>HBB', *value)
    raise ValueError(f'unknown field type {field_type}')


def build_payload(version):
    major = version // 1000
    layout, size = LAYOUTS[major]

    payload = bytearray(size)
    payload[0:2] = version.to_bytes(2, 'big')

    for offset, length, field_type, field_id in layout:
        if field_id == 'tag_version' or field_id not in SAMPLE:
            continue
        payload[offset:offset + length] = encode_field(
            SAMPLE[field_id], length, field_type)

    return bytes(payload)


def build_ndef(payload):
    record = bytes([0xD2, len(MIME_TYPE), len(payload)]) + MIME_TYPE + payload
    return bytes([0x03, len(record)]) + record + bytes([0xFE])


def build_dump(version):
    dump = bytearray(NTAG215_SIZE)
    # page 0-1: UID with BCC0, page 2: BCC1 and lock bytes, page 3: CC
    dump[0:8] = bytes([0x04, 0xA1, 0xB2, 0x57, 0xC3, 0xD4, 0xE5, 0xF6])
    dump[12:16] = CAPABILITY_CONTAINER

    ndef = build_ndef(build_payload(version))
    dump[16:16 + len(ndef)] = ndef
    return bytes(dump)


def main():
    parser = argparse.ArgumentParser(
        description='Build an NTAG215 dump holding an OpenTag3D NDEF record')
    parser.add_argument('version', help='tag version, for example 1.003 or 2.001')
    parser.add_argument('output', help='output .bin file')
    args = parser.parse_args()

    version = int(args.version.replace('.', ''))
    if version // 1000 not in LAYOUTS:
        parser.error(f'unsupported major version in {args.version}')

    with open(args.output, 'wb') as handle:
        handle.write(build_dump(version))

    print(f'wrote {args.output} for OpenTag3D {args.version}')


if __name__ == '__main__':
    main()
