---
title: lane_data Slicer Sync
---

# lane_data Slicer Sync

`lane_data` publishes the filament loaded in each extruder into Moonraker's
database, where slicers look for it. It is a Moonraker component shipped by the
`31-feature-afc-lite` overlay, alongside the AFC-Lite Klipper stub.

Read it with:

```bash
curl -s 'http://<host>/server/database/item?namespace=lane_data'
```

## Why a database namespace

The [AFC-Lite stub](../afc-lite.md) exposes filament state as a Klipper object,
which is what Fluidd and Mainsail read. Moonraker's database is a separate
store, and a Klipper object does not populate it — which is why `[AFC]` reports
`lane_data_enabled: False`.

OrcaSlicer reads the database, not the Klipper object. Its
`MoonrakerPrinterAgent::fetch_moonraker_filament_data` issues
`GET /server/database/item?namespace=lane_data`, so without this component a
slicer sees nothing and falls through to its Happy Hare probe
(`/printer/objects/query?mmu`), which the U1 also does not answer.

The namespace is registered as protected: readable over HTTP, not writable by
clients.

## Fields

Per lane, keyed `lane1`…`laneN`. The first five are the only ones OrcaSlicer
2.4 reads.

| Field | Type | Source | Notes |
|---|---|---|---|
| `lane` | **string** | lane index | 0-based tool number. Must be a JSON string — the slicer reads it with a strict string accessor and silently drops lanes carrying a number |
| `material` | string | `filament_type` (+ `filament_sub_type`) | Matched against presets by type; see below |
| `color` | string | `filament_color_rgba` | `#RRGGBBAA`. Six digits gain an `FF` alpha; anything not normalising to eight hex digits becomes transparent |
| `nozzle_temp` | int | `HOTEND_MAX_TEMP` | Becomes the slicer's `nozzle_temp_max`, so it is the **maximum**, not the minimum. Omitted from the slicer payload when 0 |
| `bed_temp` | int | `BED_TEMP` | Omitted from the slicer payload when 0 |
| `filament_name` | string | vendor + type + sub type | Not read by OrcaSlicer 2.4 |
| `vendor` | string | `filament_vendor` | Not read by OrcaSlicer 2.4 |
| `spool_id` | int | `filament_spool_id` | Not read by OrcaSlicer 2.4 |
| `tool` | string | lane index | `T0`…`TN` |
| `loaded` | bool | `filament_exist` | |

Temperatures come from `filament_detect.info[channel]`; everything else from
`print_task_config`.

## Material matching

The slicer resolves `material` through `filament_id_by_type`, which takes the
first visible, compatible, system base preset whose `filament_type` matches
exactly. Failing that it strips the modifier after the first space and retries —
so `PLA Silk` falls back to `PLA`. Dash-separated types such as `PA-CF` are
treated as distinct materials, not modifiers, and are never split.

Because of that fallback, `material_includes_subtype` is safe to leave on: a
combined `PLA Silk` picks up a silk-specific preset where one exists and
degrades to the base type where one does not.

Vendor and sub type play no part in the match. Preset *name* plays no part
either — that is a Snapmaker Orca convention, not a mainline one.

## Configuration

```ini
[lane_data]
extruder_count: 4
material_includes_subtype: True
```

| Option | Default | Effect |
|---|---|---|
| `extruder_count` | `4` | Number of lanes published |
| `material_includes_subtype` | `True` | Append the sub type to `material` |

## Limitations

- Diameter, weight, drying settings and manufacturing date are not published.
  They are not in `print_task_config`, are not writable through
  `filament_detect/set`, and no slicer reads them from `lane_data`.
- There is no `filament_id` or `setting_id`, so a slicer cannot match a
  user-defined preset by identity. Upstream work to support that is open but
  unmerged; when it lands, those fields would be the place to add.
