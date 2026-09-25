# Add OpenTag3D tag support

## Summary

Enables parsing of [OpenTag3D](https://opentag3d.info/) filament tags on the U1 by adopting
OpenRFID's own `opentag3d_tag_processor`.

The parser is upstream as of
[OpenRFID#27](https://github.com/suchmememanyskill/OpenRFID/pull/27), so this overlay ships
no OpenTag3D code of its own — it bumps the pinned revision, enables the processor, and
carries a single one-line reader-independent patch that is itself an open upstream PR.

## Changes

**Modified**

- `64-app-openrfid/pre-scripts/01-install-openrfid.sh` — `GIT_SHA` bumped to
  `a13bc9e181374e182f61db4e69abf9fa1786cc29`, which brings `src/tag/opentag3d/` and its
  `main.py` registration (OpenRFID#27) and, separately, upstream's own fix for the NTAG
  read: the reader now sizes the read from the tag's capability container instead of
  assuming NTAG215, so an NTAG216 is no longer truncated at 540 of its 924 bytes. That
  truncation is what made a Polar Filament NTAG216 unreadable here, so the pin has to be
  at or past this commit for OpenTag3D to work at all.

- `openrfid_u1_base.cfg` — enables `[opentag3d_tag_processor]`.

- `filament_protocol_ndef.py` — fixes an unrelated existing bug: the malformed
  capability-container path returned a 2-tuple where every caller unpacks three values, so
  a damaged tag raised `ValueError` instead of reporting a parse error. No OpenTag3D
  changes on the built-in path.

- `docs/design/opentag3d.md`, `docs/design/rfid.md`, `docs/design/filament_detect.md` —
  format design, readers table, and the `filament_detect` mapping.

**New**

- `64-app-openrfid/patches/02-bed-temp-range-fallback.patch`

  The spec stores a bed target alongside a min/max pair, and upstream reads only the
  target, so a tag that fills in just the range reports a bed temperature of 0 —
  indistinguishable from absent, because the `success_exporter` template drops
  non-positive temperatures. This falls back to the range, mirroring upstream's own
  handling of the hotend.

  One line, applied with `patch -F 0`, which is what `scripts/create_firmware.sh` uses.
  It is an open upstream PR, so it is temporary: delete it here and move `GIT_SHA` past it
  once it merges.

## Field mapping

The tag-to-`GenericFilament` mapping is upstream's and is documented in
[docs/design/opentag3d.md](docs/design/opentag3d.md). The `GenericFilament`-to-
`filament_detect` mapping is this overlay's `success_exporter` webhook template, documented
in [docs/design/filament_detect.md](docs/design/filament_detect.md) — it carries ten fields,
so diameter, weight, length, drying settings, manufacturing date and SKU are decoded from
the tag but not published.

## Testing

Upstream carries the parser's own tests plus a Polar Filament NTAG216 fixture
(`test/test_opentag3d.py`, `test/tags/OpenTag3D/`), and the patched `processor.py` is
covered by the regression test that accompanies the upstream PR.

A full `PROFILE=extended` image was built from this tree (35 overlays, patch applied at
zero fuzz) and the packed squashfs inspected:

```
usr/local/share/openrfid/tag/opentag3d/   __init__.py  processor.py  schema.py  schemas/v2.json
main.py:25                                from tag.opentag3d import OpenTag3DTagProcessor
main.py:63                                case "opentag3d_tag_processor":
tag/opentag3d/processor.py:102            bed_temp_c=data["bed_temp"] or data["min_bed_temp"] or ...
reader/fm175xx/rfid.py:718                if cc[0] != 0xE1 or page_count is None:
extended/openrfid_u1_base.cfg:71          [opentag3d_tag_processor]
```

Upstream's processor is present and registered by upstream's own `main.py`, the reader is
upstream's capability-container version, and none of the overlay's former OpenTag3D files
remain.

**Confirmed on hardware.** That image was flashed to a U1 and a Polar Filament NTAG216
scanned on slot 0. The reader sized the read from the tag's capability container
(`E1 10 6D 00` — 231 pages) and returned all 924 bytes, and upstream's processor parsed the
216-byte `application/opentag3d` record out of it:

```
root: Polar Filament PLA Pure Filament (processed by opentag3d_tag_processor):
- Color (ARGB): #FF14ADDB
- Diameter: 1.75 mm
- Weight: 1000 grams
- Hotend Temp: 205.0C - 245.0C
- Bed Temp: 60.0C
- Drying: 65.0C for 0.0 hours
- Manufactured on: 2026-04-03
root: Successfully read tag with UID 533B3919640001 on reader slot_0_reader
```

`filament_detect` slot 0 then reported `VENDOR` `Polar Filament`, `MAIN_TYPE` `PLA`,
`SUB_TYPE` `Pure`, `HOTEND_MIN_TEMP` 205, `HOTEND_MAX_TEMP` 245, `BED_TEMP` 60, `ALPHA` 255,
`RGB_1` `0x14ADDB`, `CARD_TYPE` `NTAG`, `CARD_UID` `533B3919640001` — the full ten-field
webhook contract, end to end.

This tag populates `bed_temp` directly, so it does not exercise the patched line; that is
covered by the regression test in the upstream PR.

### Note for reviewers building locally

`cache_git.sh` returns early when its target directory already exists, so bumping `GIT_SHA`
does not re-fetch on a warm cache — `tmp/cache/OpenRFID` has to be removed first. It guards
on `$CI`, so CI is unaffected. Without that, a local build silently uses the old revision,
and because the OpenTag3D parser arrives with the pin rather than with a patch, the symptom
is tags simply not parsing.

---

I have read `CONTRIBUTING.md` and agree to the contributor terms. This work is my own and is
submitted under GPL-3.0.
