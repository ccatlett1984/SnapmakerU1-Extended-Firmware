# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-PackageHomePage: https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware
# SPDX-FileCopyrightText: Copyright (c) 2026 @paxx12

# OpenTag3D memory-mapped tag parser.
#
# Specification: https://opentag3d.info/spec
# Supported tag versions: 1.000 - 1.003 (legacy layout), 2.000 - 2.001 (current layout)
#
# The payload is the body of an NDEF record with MIME type
# 'application/opentag3d'. All integers are unsigned big endian, all strings
# are UTF-8 and NUL padded. Missing trailing bytes are treated as 0x00.

import logging
from . import filament_protocol

OPENTAG3D_MIME_TYPE = 'application/opentag3d'

# Highest minor version of each major version this parser was written against.
# A newer minor version is parsed with a warning, a newer major version is
# rejected, as required by the specification's reader guidelines.
OPENTAG3D_KNOWN_VERSIONS = {1: 3, 2: 1}

# id: (offset, length, type)
#
# type is one of:
#   'int'   unsigned big endian integer
#   'str'   UTF-8, NUL padded
#   'rgba'  4 x 1 byte, red / green / blue / alpha
#   'date'  2 byte year, 1 byte month, 1 byte day
#
# Scaling is applied by the mapping code below, not here, so the offsets stay
# a literal transcription of the specification memory map.

# OpenTag3D 1.000 - 1.003, core 0x00-0x6F and extended 0x70-0xBA
OPENTAG3D_MEMORY_MAP_V1 = {
    'tag_version':          (0x00, 2, 'int'),
    'material':             (0x02, 5, 'str'),
    'material_mod':         (0x07, 5, 'str'),
    'manufacturer':         (0x1B, 16, 'str'),
    'color_1':              (0x4B, 4, 'rgba'),
    'color_2':              (0x50, 4, 'rgba'),
    'color_3':              (0x54, 4, 'rgba'),
    'color_4':              (0x58, 4, 'rgba'),
    'diameter':             (0x5C, 2, 'int'),
    'weight':               (0x5E, 2, 'int'),
    'print_temp':           (0x60, 1, 'int'),
    'bed_temp':             (0x61, 1, 'int'),
    'mfg_date':             (0xA0, 4, 'date'),
    'measured_length':      (0xB0, 2, 'int'),
    'max_dry_temp':         (0xB2, 1, 'int'),
    'dry_time':             (0xB3, 1, 'int'),
    'min_print_temp':       (0xB4, 1, 'int'),
    'max_print_temp':       (0xB5, 1, 'int'),
    'min_bed_temp':         (0xB6, 1, 'int'),
    'max_bed_temp':         (0xB7, 1, 'int'),
}

# OpenTag3D 2.000 - 2.001, single 0x00-0xDF block
OPENTAG3D_MEMORY_MAP_V2 = {
    'tag_version':          (0x00, 2, 'int'),
    'material':             (0x02, 5, 'str'),
    'material_mod':         (0x07, 5, 'str'),
    'manufacturer':         (0x0C, 16, 'str'),
    'color_1':              (0x3C, 4, 'rgba'),
    'color_2':              (0x40, 4, 'rgba'),
    'color_3':              (0x44, 4, 'rgba'),
    'color_4':              (0x48, 4, 'rgba'),
    'sku':                  (0x6C, 16, 'str'),
    'mfg_date':             (0x84, 4, 'date'),
    'diameter':             (0x8C, 2, 'int'),
    'print_temp':           (0x90, 1, 'int'),
    'min_print_temp':       (0x91, 1, 'int'),
    'max_print_temp':       (0x92, 1, 'int'),
    'bed_temp':             (0x94, 1, 'int'),
    'min_bed_temp':         (0x95, 1, 'int'),
    'max_bed_temp':         (0x96, 1, 'int'),
    'max_dry_temp':         (0x9A, 1, 'int'),
    'dry_time':             (0x9B, 1, 'int'),
    'weight':               (0x9E, 2, 'int'),
    'measured_length':      (0xA2, 2, 'int'),
}

# Temperatures are stored in degrees Celsius divided by 5
OPENTAG3D_TEMP_SCALE = 5


def _field_bytes(payload, offset, length):
    # Missing trailing bytes are 0x00 per the specification
    chunk = payload[offset:offset + length]
    if len(chunk) < length:
        chunk = chunk + bytes(length - len(chunk))
    return chunk


def _read_field(payload, memory_map, field_id):
    entry = memory_map.get(field_id)
    if entry is None:
        return None

    offset, length, field_type = entry
    raw = _field_bytes(payload, offset, length)

    if field_type == 'int':
        value = 0
        for byte in raw:
            value = (value << 8) | int(byte)
        return value

    if field_type == 'str':
        text = raw.decode('utf-8', errors='ignore')
        return text.split('\x00')[0].strip()

    if field_type == 'rgba':
        return (int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3]))

    if field_type == 'date':
        year = (int(raw[0]) << 8) | int(raw[1])
        return (year, int(raw[2]), int(raw[3]))

    return None


def _read_int(payload, memory_map, field_id, default=0):
    value = _read_field(payload, memory_map, field_id)
    return default if value is None else value


def _read_str(payload, memory_map, field_id, default=''):
    value = _read_field(payload, memory_map, field_id)
    return default if not value else value


def _rgb_int(color):
    return (color[0] << 16) | (color[1] << 8) | color[2]


def opentag3d_select_memory_map(tag_version):
    major = tag_version // 1000
    minor = tag_version % 1000

    if major not in OPENTAG3D_KNOWN_VERSIONS:
        logging.error(
            "OpenTag3D payload parsing failed: unsupported tag version %d.%03d",
            major, minor)
        return None

    if minor > OPENTAG3D_KNOWN_VERSIONS[major]:
        logging.warning(
            "OpenTag3D tag version %d.%03d is newer than the supported "
            "%d.%03d, parsing with the known memory map",
            major, minor, major, OPENTAG3D_KNOWN_VERSIONS[major])

    return OPENTAG3D_MEMORY_MAP_V1 if major == 1 else OPENTAG3D_MEMORY_MAP_V2


def opentag3d_parse_payload(payload, card_uid=[]):
    if None == payload or not isinstance(payload, (bytes, bytearray)):
        logging.error("OpenTag3D payload parsing failed: Invalid payload parameter")
        return filament_protocol.FILAMENT_PROTO_PARAMETER_ERR, None

    try:
        payload = bytes(payload)

        tag_version = _read_int(payload, OPENTAG3D_MEMORY_MAP_V1, 'tag_version')
        memory_map = opentag3d_select_memory_map(tag_version)
        if memory_map is None:
            return filament_protocol.FILAMENT_PROTO_ERR, None

        logging.info("OpenTag3D tag version %d.%03d, payload %d bytes",
                     tag_version // 1000, tag_version % 1000, len(payload))

        material = _read_str(payload, memory_map, 'material', 'PLA')
        material_mod = _read_str(payload, memory_map, 'material_mod', 'Basic')
        manufacturer = _read_str(payload, memory_map, 'manufacturer', 'Generic')

        info = dict(filament_protocol.FILAMENT_INFO_STRUCT)
        info['VERSION'] = 1
        info['VENDOR'] = manufacturer
        info['MANUFACTURER'] = manufacturer
        info['MAIN_TYPE'] = material.upper()
        info['SUB_TYPE'] = material_mod
        info['TRAY'] = 0

        colors = []
        for index in range(1, filament_protocol.FILAMENT_PROTO_COLOR_NUMS_MAX + 1):
            color = _read_field(payload, memory_map, 'color_%d' % index)
            if color is None or color == (0, 0, 0, 0):
                continue
            colors.append(color)

        if not colors:
            colors = [(0xFF, 0xFF, 0xFF, 0xFF)]

        info['COLOR_NUMS'] = len(colors)
        for index, color in enumerate(colors, start=1):
            info['RGB_%d' % index] = _rgb_int(color)

        # A zero alpha byte means the field was never written, not transparent
        info['ALPHA'] = colors[0][3] if colors[0][3] else 0xFF
        info['ARGB_COLOR'] = info['ALPHA'] << 24 | info['RGB_1']

        # Stored in micrometres, FILAMENT_INFO_STRUCT wants hundredths of a mm
        diameter = _read_int(payload, memory_map, 'diameter')
        info['DIAMETER'] = diameter // 10 if diameter else 175

        info['WEIGHT'] = _read_int(payload, memory_map, 'weight')
        info['LENGTH'] = _read_int(payload, memory_map, 'measured_length')

        print_temp = _read_int(payload, memory_map, 'print_temp') * OPENTAG3D_TEMP_SCALE
        min_print_temp = _read_int(payload, memory_map, 'min_print_temp') * OPENTAG3D_TEMP_SCALE
        max_print_temp = _read_int(payload, memory_map, 'max_print_temp') * OPENTAG3D_TEMP_SCALE
        info['HOTEND_MIN_TEMP'] = min_print_temp if min_print_temp else print_temp
        info['HOTEND_MAX_TEMP'] = max_print_temp if max_print_temp else print_temp

        bed_temp = _read_int(payload, memory_map, 'bed_temp') * OPENTAG3D_TEMP_SCALE
        min_bed_temp = _read_int(payload, memory_map, 'min_bed_temp') * OPENTAG3D_TEMP_SCALE
        max_bed_temp = _read_int(payload, memory_map, 'max_bed_temp') * OPENTAG3D_TEMP_SCALE
        if not bed_temp:
            bed_temp = min_bed_temp if min_bed_temp else max_bed_temp
        info['BED_TEMP'] = bed_temp
        info['BED_TYPE'] = 0

        info['DRYING_TEMP'] = _read_int(payload, memory_map, 'max_dry_temp') * OPENTAG3D_TEMP_SCALE
        info['DRYING_TIME'] = _read_int(payload, memory_map, 'dry_time')

        info['FIRST_LAYER_TEMP'] = info['HOTEND_MIN_TEMP']
        info['OTHER_LAYER_TEMP'] = info['HOTEND_MIN_TEMP']

        sku = _read_str(payload, memory_map, 'sku')
        info['SKU'] = int(sku) if sku.isdigit() else 0

        mfg_date = _read_field(payload, memory_map, 'mfg_date')
        if mfg_date and mfg_date[0]:
            info['MF_DATE'] = '%04d%02d%02d' % mfg_date
        else:
            info['MF_DATE'] = '19700101'

        info['RSA_KEY_VERSION'] = 0
        info['OFFICIAL'] = True
        info['CARD_UID'] = card_uid

        return filament_protocol.FILAMENT_PROTO_OK, info

    except Exception as e:
        logging.exception("OpenTag3D payload parsing failed: %s", str(e))
        return filament_protocol.FILAMENT_PROTO_ERR, None
