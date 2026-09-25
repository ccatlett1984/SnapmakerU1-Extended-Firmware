# OpenTag3D: fall back to the bed temperature range when the target is unset

## Summary

`bed_temp_c` is read from the tag's bed target only. A tag that populates the min/max pair
but leaves the target at 0 reports a bed temperature of 0 rather than a usable value.

This mirrors the handling already applied to the hotend a few lines above:

```python
hotend_min_temp_c = data["min_print_temp"] or data["print_temp"]
hotend_max_temp_c = data["max_print_temp"] or data["print_temp"]
```

so the bed becomes:

```python
bed_temp_c=data["bed_temp"] or data["min_bed_temp"] or data["max_bed_temp"],
```

One line, plus a regression test.

## Why

The spec carries `bed_temp` alongside `min_bed_temp` and `max_bed_temp`, and nothing
requires a writer to fill in all three. `GenericFilament` has a single bed value, so the
adapter already has to choose — and it chooses the range over the target for the hotend.
Doing the same for the bed keeps one policy rather than two.

Downstream this is the difference between a printer receiving a bed temperature and
receiving nothing: the Snapmaker U1 integration drops non-positive temperatures from its
`filament_detect` payload, so a 0 is indistinguishable from absent.

## Testing

```
$ pytest
57 passed, 1 skipped
```

New test, using the bundled Polar Filament fixture, checks target → min → max precedence
and that all three unset still yields 0:

```python
def test_bed_temp_falls_back_to_range(processor, scan, payload):
    payload[148] = 0
    payload[149:151] = bytes([11, 13])
    assert processor.process_tag(scan, tag(record(payload))).bed_temp_c == 55
    payload[149] = 0
    assert processor.process_tag(scan, tag(record(payload))).bed_temp_c == 65
    payload[150] = 0
    assert processor.process_tag(scan, tag(record(payload))).bed_temp_c == 0
```

## Note

Separately, `__reader_a_ultralight_read_all_data` assumes NTAG215 and caps at 540 bytes,
which truncates an NTAG216 at 540 of its 924. I have a change that reads until the tag stops
answering and truncates to the largest fully covered page count. Happy to raise it as its own
PR if that is of interest; it is independent of this one.
