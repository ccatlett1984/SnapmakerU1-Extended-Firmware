# OpenTag3D memory maps.
#
# Specification: https://opentag3d.info/spec
# Transcribed from _data/spec.json at tags v1.003 and v2.001 of
# https://github.com/GooborgStudios/OpenTag3D
#
# The payload is the body of an NDEF record with MIME type
# 'application/opentag3d'. All integers are unsigned big endian, all strings
# are UTF-8 and NUL padded. Missing trailing bytes are treated as 0x00.

OPENTAG3D_MIME_TYPE = "application/opentag3d"

# Highest minor version of each major version these maps were written against.
# A newer minor version is parsed with a warning, a newer major version is
# rejected, as required by the specification's reader guidelines.
OPENTAG3D_KNOWN_VERSIONS = {1: 3, 2: 1}

# Temperatures are stored in degrees Celsius divided by 5
OPENTAG3D_TEMP_SCALE = 5

# id: (offset, length, type)
#
# type is one of:
#   'int'   unsigned big endian integer
#   'str'   UTF-8, NUL padded
#   'rgba'  4 x 1 byte, red / green / blue / alpha
#   'date'  2 byte year, 1 byte month, 1 byte day
#
# Scaling is applied by the processor, not here, so the offsets stay a literal
# transcription of the specification memory map.

# OpenTag3D 1.000 - 1.003, core 0x00-0x6F and extended 0x70-0xBA.
# Note the reserved gap at 0x0C-0x1A: manufacturer sits at 0x1B, not 0x0C.
OPENTAG3D_MEMORY_MAP_V1 = {
    "tag_version":      (0x00, 2, "int"),
    "material":         (0x02, 5, "str"),
    "material_mod":     (0x07, 5, "str"),
    "manufacturer":     (0x1B, 16, "str"),
    "color_1":          (0x4B, 4, "rgba"),
    "color_2":          (0x50, 4, "rgba"),
    "color_3":          (0x54, 4, "rgba"),
    "color_4":          (0x58, 4, "rgba"),
    "diameter":         (0x5C, 2, "int"),
    "weight":           (0x5E, 2, "int"),
    "print_temp":       (0x60, 1, "int"),
    "bed_temp":         (0x61, 1, "int"),
    "td":               (0x64, 2, "int"),
    "mfg_date":         (0xA0, 4, "date"),
    "measured_length":  (0xB0, 2, "int"),
    "max_dry_temp":     (0xB2, 1, "int"),
    "dry_time":         (0xB3, 1, "int"),
    "min_print_temp":   (0xB4, 1, "int"),
    "max_print_temp":   (0xB5, 1, "int"),
    "min_bed_temp":     (0xB6, 1, "int"),
    "max_bed_temp":     (0xB7, 1, "int"),
}

# OpenTag3D 2.000 - 2.001, single 0x00-0xDF block, all fields rearranged
OPENTAG3D_MEMORY_MAP_V2 = {
    "tag_version":      (0x00, 2, "int"),
    "material":         (0x02, 5, "str"),
    "material_mod":     (0x07, 5, "str"),
    "manufacturer":     (0x0C, 16, "str"),
    "color_name":       (0x1C, 32, "str"),
    "color_1":          (0x3C, 4, "rgba"),
    "color_2":          (0x40, 4, "rgba"),
    "color_3":          (0x44, 4, "rgba"),
    "color_4":          (0x48, 4, "rgba"),
    "serial":           (0x4C, 32, "str"),
    "sku":              (0x6C, 16, "str"),
    "mfg_date":         (0x84, 4, "date"),
    "diameter":         (0x8C, 2, "int"),
    "print_temp":       (0x90, 1, "int"),
    "min_print_temp":   (0x91, 1, "int"),
    "max_print_temp":   (0x92, 1, "int"),
    "bed_temp":         (0x94, 1, "int"),
    "min_bed_temp":     (0x95, 1, "int"),
    "max_bed_temp":     (0x96, 1, "int"),
    "max_dry_temp":     (0x9A, 1, "int"),
    "dry_time":         (0x9B, 1, "int"),
    "weight":           (0x9E, 2, "int"),
    "measured_length":  (0xA2, 2, "int"),
    "td":               (0xA7, 1, "int"),
}

# td is opaque thickness in mm, stored x10 in 2.x and x10 in 1.x as well
OPENTAG3D_TD_SCALE = 0.1
