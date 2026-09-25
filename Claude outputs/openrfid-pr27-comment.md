Thanks for this — using `spec.json` as the backbone is the right call, and it's a better foundation than what I wrote independently.

For context: I implemented an OpenTag3D processor for the Snapmaker U1 extended firmware overlay ([paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)), carried as a local patch against a pinned OpenRFID. Once this merges I'd rather delete mine and depend on yours. Comparing the two, there are a few things mine handles that this doesn't, and I'd rather contribute them upstream than keep carrying a fork.

**v1 memory map.** `SCHEMAS.get(version // 1000)` returns `None` for v1, and the comment notes it's pending. I have a v1 map validated field by field against the published `spec.json` at v1.003, including the manufacturer gap at `0x1B`. As a `schemas/v1.json` it should drop into your decoder without touching the processor. I only have v2.001 tags in hand (Polar Filament), so the v1 map is spec-validated rather than hardware-tested — worth stating plainly.

**Four defensive cases in `__to_filament`.** None of these change behaviour for a well-formed tag; they only matter for partially written ones, which we do see in the wild:

- A zero alpha byte almost always means "never written" rather than "transparent". Keeping it produces a fully transparent primary colour, which downstream of us becomes an ARGB value with alpha 0 and renders invisible. Forcing `0xFF` when alpha is 0 fixed that.
- No usable colours at all → default to opaque white rather than an empty list.
- `diameter` of 0 → default to 1.75 mm.
- `bed_temp` of 0 → fall back to `min_bed_temp`, then `max_bed_temp`.

One thing yours does better than mine, for the record: deriving `unique_id` from the tag UID rather than from a content hash. Mine collides across two physically distinct but identical spools; yours doesn't. I'll be adopting that.

Happy to send these as a PR against your branch now, or as a follow-up after this merges — whichever you prefer.
