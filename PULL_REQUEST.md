# Add OpenTag3D tag support

## Summary

Enables parsing of [OpenTag3D](https://opentag3d.info/) filament tags on the U1 by adopting
OpenRFID's own `opentag3d_tag_processor`.

The parser is upstream as of
[OpenRFID#27](https://github.com/suchmememanyskill/OpenRFID/pull/27), so this overlay ships
no OpenTag3D code of its own — it bumps the pinned revision, enables the processor, and
carries a single one-line reader-independent patch that is itself an open upstream PR.

## Motivation

Before this, OpenTag3D was unreadable on the U1. OpenRFID's processor chain had no
OpenTag3D processor, so a tag fell all the way through and the spool was reported UID-only.
From a real scan:

```
tag_processor:openspool_tag_processor: NDEF MIME record found: mime_type='application/opentag3d', payload_len=216
tag_processor:openspool_tag_processor: OpenSpool processing failed: No valid OpenSpool NDEF record found
root: Detected tag with UID 533B3919640001 on reader slot_0_reader but failed to read data
```

The format is in active use — Polar Filament ships 2.x tags, and SpoolKid and SimplyPrint
both read and write it — and the tag hardware requirement is already satisfied by the NTAG
support in the `13-patch-rfid` overlay.

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

**Not yet confirmed on hardware.** An end-to-end scan-to-`filament_detect` round trip was
observed with this overlay's previous in-tree processor, but not since switching to
OpenRFID's. That check is outstanding.

### Note for reviewers building locally

`cache_git.sh` returns early when its target directory already exists, so bumping `GIT_SHA`
does not re-fetch on a warm cache — `tmp/cache/OpenRFID` has to be removed first. It guards
on `$CI`, so CI is unaffected. Without that, a local build silently uses the old revision,
and because the OpenTag3D parser arrives with the pin rather than with a patch, the symptom
is tags simply not parsing.

## Known limitations

- **OpenTag3D 1.x tags are rejected.** Upstream bundles `schemas/v2.json` only, and a major
  version with no schema is refused. Adding 1.x upstream needs both a v1 schema and a
  decoder that walks v1's `extended` block, so it is a larger change than a single JSON
  file.
- **NTAG213 cannot carry OpenTag3D.** Its 144 bytes of user memory cannot hold a compliant
  payload, and the specification dropped NTAG213 in 2.000. It reads fine for OpenSpool.
- **The built-in Snapmaker reader still caps NTAG reads at 540 bytes.** Only OpenRFID's
  reader sizes reads from the tag. An OpenSpool record sitting behind large unrelated NDEF
  records on an NTAG216 remains invisible to the built-in path.
- **Upstream's parser is less defensive than the one it replaces** in three remaining
  places: a zero alpha byte is treated as transparent rather than unwritten, an absent
  colour yields an empty list rather than opaque white, and a zero diameter is carried
  through as `0.0`. None affects a well-formed tag. The transparent-alpha behaviour is
  deliberate and covered by an upstream test, so it is a discussion rather than a patch; the
  other two invent values, which upstream's adapter avoids by design. The fourth,
  `bed_temp`, is patched here because it follows a policy upstream already applies.

---

I have read `CONTRIBUTING.md` and agree to the contributor terms. This work is my own and is
submitted under GPL-3.0.
