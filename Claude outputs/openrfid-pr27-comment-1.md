Nice to see this land. I'm switching the Snapmaker U1 extended firmware overlay ([paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)) over to it — we'd been carrying an independently written OpenTag3D processor as a local patch, and it's now deleted in favour of yours. Using `spec.json` as the backbone was the better call; adding a version is a JSON file rather than a code change.

Comparing the two before dropping mine, there are a few things mine handled that the merged version doesn't. I'd rather contribute them here than re-grow a fork, so tell me if you'd take any of these as a follow-up PR.

**v1 memory map.** `SCHEMAS.get(version // 1000)` returns `None` for v1 and the comment marks it pending. I have a v1 map validated field by field against the published `spec.json` at v1.003, including the manufacturer gap at `0x1B`. It should drop in as `schemas/v1.json` with no processor changes. I only have v2.001 tags in hand (Polar Filament), so it's spec-validated rather than hardware-tested — worth saying plainly.

**Four defensive cases in `__to_filament`.** None of these change behaviour for a well-formed tag; they only matter for partially written ones, which do turn up:

- A zero alpha byte almost always means "never written" rather than "transparent". Keeping it yields a fully transparent primary colour, which downstream of us becomes an ARGB value with alpha 0 and renders invisible. Forcing `0xFF` when alpha is 0 fixed that.
- No usable colours at all → default to opaque white rather than an empty list.
- `diameter` of 0 → default to 1.75 mm.
- `bed_temp` of 0 → fall back to `min_bed_temp`, then `max_bed_temp`.

One thing yours does better than mine, for the record: deriving `unique_id` from the tag UID rather than a content hash. Mine collides across two physically distinct but identical spools; yours doesn't.

Separately, we also carry a small reader-side patch making `__reader_a_ultralight_read_all_data` handle NTAG213/215/216 rather than assuming NTAG215 — it reads until the tag stops answering and truncates to the largest known page count. Happy to raise that as its own PR if it's of interest; it's independent of this one.
