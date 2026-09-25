# fm175xx: read NTAG213 and NTAG216 instead of assuming NTAG215

## Summary

`__reader_a_ultralight_read_all_data` is hard-coded to NTAG215's geometry. It loops to
`FM175XX_NTAG215_TOTAL_PAGES` and allocates `FM175XX_NTAG215_TOTAL_SIZE`, so:

- **NTAG216 is silently truncated** to 540 of its 924 bytes. An NDEF record living in the
  upper 384 bytes is invisible, with no error to say so.
- **NTAG213 fails outright.** Reads past page 44 are NAKed, and the recovery branch cannot
  fire (see below), so the whole read returns `FM175XX_CARD_READ_ERR`.

It now reads until the tag stops answering and truncates to the largest recognised page
count that was fully covered — 180 bytes for an NTAG213, 540 for an NTAG215, 924 for an
NTAG216.

## The recovery branch was dead code

```python
if (page_no - 4) in Constants.FM175XX_ULTRALIGHT_VALID_END_PAGES:
```

`FM175XX_ULTRALIGHT_VALID_END_PAGES` is `[135, 44]`, and `page_no` comes from
`range(0, 135, 4)`, so it takes values `0, 4, … 132` and `page_no - 4` ranges over
`-4 … 128`. It can never equal 135 (135 + 4 is not a multiple of 4) and never reaches 44
in a failing iteration, because the loop stops at 132 before a 44-page tag's first NAK at
page 48 would be attempted. So any tag that NAKs mid-read falls through to
`FM175XX_CARD_READ_ERR`, and any tag larger than an NTAG215 is quietly cut short.

This replaces the constant with `FM175XX_ULTRALIGHT_KNOWN_PAGE_COUNTS` and a check that can
actually fire.

## Why truncate rather than trust the read length

A READ returns four pages and rolls over within addressable memory, so the last successful
read on any tag overruns the final page. Truncating to a known page count discards those
roll-over bytes, which would otherwise be handed back as if they were tag memory.

Plain Ultralight is deliberately **not** in the recognised list, so it stays rejected as it
was before. An Ultralight EV1 MF0UL21 has 41 pages and, because of roll-over, answers every
read a 44-page tag would; accepting 44 would return 176 bytes whose tail is roll-over rather
than memory. `FM175XX_ULTRALIGHT_TOTAL_PAGES` is left in place but is no longer referenced —
happy to remove it if you would rather not keep an unused constant.

## Testing

```
$ pytest
66 passed, 1 skipped
```

New `test/test_fm175xx_ultralight_read.py` drives the real function with the page-read
helper replaced by a simulated tag that models both behaviours that matter — a READ returns
four pages and rolls over within addressable memory, and an address past the last page is
NAKed. No hardware is constructed or touched.

It asserts that an NTAG213, NTAG215 and NTAG216 each come back at their exact size **and
byte-identical to the simulated tag's memory** — the roll-over check, since a naive
implementation returns the right length with the wrong tail. It also asserts that 0-, 4-,
16-, 20-, 41- and 44-page tags are still rejected, 41 included specifically because it is a
real size that roll-over makes look like 44.

## Scope

Only the Ultralight/NTAG path changes. `__reader_a_m1_read_all_data` and the Mifare Classic
path are untouched, as is every caller — `read_mifare_ultralight` still receives a byte list
and simply gets a correctly sized one.
