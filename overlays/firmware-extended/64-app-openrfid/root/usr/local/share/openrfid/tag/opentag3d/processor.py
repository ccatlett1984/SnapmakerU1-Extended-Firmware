from filament import GenericFilament
from filament.valid_materials import VALID_BASE_MATERIALS
from reader.scan_result import ScanResult
from tag.ndef_tag_processor import NdefRecord, NdefTagProcessor
from . import constants as Constants


class OpenTag3DTagProcessor(NdefTagProcessor):
    """Reads OpenTag3D filament tags.

    Unlike OpenSpool, which stores JSON, OpenTag3D stores a fixed memory map as
    the payload of an NDEF record with MIME type 'application/opentag3d'. The
    memory map is selected from the tag version held in the first two bytes.
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def process_ndef(self, scan_result: ScanResult, ndef_records: list[NdefRecord]) -> GenericFilament | None:
        for record in ndef_records:
            if record.mime_type == Constants.OPENTAG3D_MIME_TYPE:
                parse = self.__opentag3d_parse_payload(record.payload)

                if parse is not None:
                    return parse

        self.logger.error("OpenTag3D processing failed: No valid OpenTag3D NDEF record found")
        return None

    # ------------------------------------------------------------------ #
    # memory map helpers
    # ------------------------------------------------------------------ #

    def __field_bytes(self, payload: bytes, offset: int, length: int) -> bytes:
        # Missing trailing bytes are 0x00 per the specification
        chunk = payload[offset:offset + length]
        if len(chunk) < length:
            chunk = chunk + bytes(length - len(chunk))
        return chunk

    def __read_field(self, payload: bytes, memory_map: dict, field_id: str):
        entry = memory_map.get(field_id)
        if entry is None:
            return None

        offset, length, field_type = entry
        raw = self.__field_bytes(payload, offset, length)

        if field_type == "int":
            return int.from_bytes(raw, "big")

        if field_type == "str":
            return raw.decode("utf-8", errors="ignore").split("\x00")[0].strip()

        if field_type == "rgba":
            return (raw[0], raw[1], raw[2], raw[3])

        if field_type == "date":
            return ((raw[0] << 8) | raw[1], raw[2], raw[3])

        return None

    def __read_int(self, payload: bytes, memory_map: dict, field_id: str, default: int = 0) -> int:
        value = self.__read_field(payload, memory_map, field_id)
        return default if value is None else value

    def __read_str(self, payload: bytes, memory_map: dict, field_id: str, default: str = "") -> str:
        value = self.__read_field(payload, memory_map, field_id)
        return default if not value else value

    def __select_memory_map(self, tag_version: int) -> dict | None:
        major = tag_version // 1000
        minor = tag_version % 1000

        if major not in Constants.OPENTAG3D_KNOWN_VERSIONS:
            self.logger.error(
                "OpenTag3D parsing failed: unsupported tag version %d.%03d", major, minor)
            return None

        if minor > Constants.OPENTAG3D_KNOWN_VERSIONS[major]:
            self.logger.warning(
                "OpenTag3D tag version %d.%03d is newer than the supported %d.%03d, "
                "parsing with the known memory map",
                major, minor, major, Constants.OPENTAG3D_KNOWN_VERSIONS[major])

        return (Constants.OPENTAG3D_MEMORY_MAP_V1 if major == 1
                else Constants.OPENTAG3D_MEMORY_MAP_V2)

    # ------------------------------------------------------------------ #
    # payload -> GenericFilament
    # ------------------------------------------------------------------ #

    def __opentag3d_parse_payload(self, payload: bytes) -> GenericFilament | None:
        if payload is None or not isinstance(payload, (bytes, bytearray)):
            self.logger.error("OpenTag3D payload parsing failed: Invalid payload parameter")
            return None

        try:
            payload = bytes(payload)

            tag_version = self.__read_int(payload, Constants.OPENTAG3D_MEMORY_MAP_V1, "tag_version")
            memory_map = self.__select_memory_map(tag_version)
            if memory_map is None:
                return None

            self.logger.debug("OpenTag3D tag version %d.%03d, payload %d bytes",
                              tag_version // 1000, tag_version % 1000, len(payload))

            material = self.__read_str(payload, memory_map, "material", "PLA").upper()
            material_mod = self.__read_str(payload, memory_map, "material_mod")
            manufacturer = self.__read_str(payload, memory_map, "manufacturer", "Generic")

            # GenericFilament raises on an unrecognised type, which would abort
            # the whole scan rather than letting another processor try, so the
            # check happens here instead.
            if material not in VALID_BASE_MATERIALS:
                self.logger.error(
                    "OpenTag3D parsing failed: '%s' is not a recognised base material", material)
                return None

            colors = []
            for index in range(1, 5):
                color = self.__read_field(payload, memory_map, "color_%d" % index)
                if color is None or color == (0, 0, 0, 0):
                    continue
                red, green, blue, alpha = color
                # A zero alpha byte means the field was never written, not transparent
                if not alpha:
                    alpha = 0xFF
                colors.append((alpha << 24) | (red << 16) | (green << 8) | blue)

            if not colors:
                colors = [0xFFFFFFFF]

            # Stored in micrometres
            diameter = self.__read_int(payload, memory_map, "diameter")
            diameter_mm = (diameter / 1000.0) if diameter else 1.75

            scale = Constants.OPENTAG3D_TEMP_SCALE
            print_temp = self.__read_int(payload, memory_map, "print_temp") * scale
            min_print_temp = self.__read_int(payload, memory_map, "min_print_temp") * scale
            max_print_temp = self.__read_int(payload, memory_map, "max_print_temp") * scale
            hotend_min = min_print_temp if min_print_temp else print_temp
            hotend_max = max_print_temp if max_print_temp else print_temp

            bed_temp = self.__read_int(payload, memory_map, "bed_temp") * scale
            if not bed_temp:
                min_bed_temp = self.__read_int(payload, memory_map, "min_bed_temp") * scale
                max_bed_temp = self.__read_int(payload, memory_map, "max_bed_temp") * scale
                bed_temp = min_bed_temp if min_bed_temp else max_bed_temp

            mfg_date = self.__read_field(payload, memory_map, "mfg_date")
            if mfg_date and mfg_date[0]:
                manufacturing_date = "%04d-%02d-%02d" % mfg_date
            else:
                manufacturing_date = "0001-01-01"

            modifiers = [material_mod] if material_mod else []

            return GenericFilament(
                source_processor=self.name,
                unique_id=GenericFilament.generate_unique_id(
                    "OpenTag3D", manufacturer, material, material_mod, colors[0]),
                manufacturer=manufacturer,
                type=material,
                modifiers=modifiers,
                colors=colors,
                diameter_mm=diameter_mm,
                weight_grams=self.__read_int(payload, memory_map, "weight"),
                hotend_min_temp_c=hotend_min,
                hotend_max_temp_c=hotend_max,
                bed_temp_c=bed_temp,
                drying_temp_c=self.__read_int(payload, memory_map, "max_dry_temp") * scale,
                drying_time_hours=self.__read_int(payload, memory_map, "dry_time"),
                manufacturing_date=manufacturing_date,
                td=self.__read_int(payload, memory_map, "td") * Constants.OPENTAG3D_TD_SCALE,
            )

        except Exception as e:
            self.logger.exception("OpenTag3D payload parsing failed: %s", str(e))
            return None
