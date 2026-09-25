# Fix Snapmaker filament sync: nozzle temperature, invented material types, and a crash on an empty spool colour

## Description

`SnapmakerPrinterAgent::fetch_filament_info` reads `print_task_config` and
`filament_detect` from the printer and publishes the result as AMS tray data.
Five problems in that path are fixed here. Each is independent; the commits can
be taken separately.

### 1. `nozzle_temp_max` is always 0

The agent reads the hotend temperature from `FIRST_LAYER_TEMP`:

```cpp
tray.nozzle_temp = nfc_slot.value("FIRST_LAYER_TEMP", 0);
```

`build_ams_payload` publishes `tray.nozzle_temp` as the tray's
**`nozzle_temp_max`**, so a first-layer temperature is the wrong quantity even
when it is present.

It is also usually absent. In the U1 firmware `FIRST_LAYER_TEMP` is derived
inside the native tag-protocol handler and is **not part of the writable field
set of `POST /printer/filament_detect/set`**. Every spool reported by an
external tag reader — OpenSpool, OpenTag3D, or any third-party integration that
writes through that endpoint — therefore leaves the field at its struct default,
and the slicer receives no nozzle temperature at all.

`HOTEND_MAX_TEMP` is populated on both the native and the external path, and is
the maximum the field is being used as. This PR reads that instead.

The same block only read temperatures when `VENDOR != "NONE"`, which discarded
perfectly good `HOTEND_MAX_TEMP` / `BED_TEMP` values for any slot set without a
vendor. `build_ams_payload` already omits non-positive temperatures from the
payload, so the guard is removed.

`nlohmann::json::value()` throws `type_error` when the key is present but of
another type (a firmware reporting `null` for an unpopulated field, for
example). Both reads now go through `MoonrakerPrinterAgent::safe_json_int`,
which already exists for exactly this. It and the other JSON accessors were
`private`, so the block moves to `protected` where the derived agents can reach
it rather than each duplicating its own.

Observed on a Snapmaker U1 with a spool loaded through an external tag reader:

```
FIRST_LAYER_TEMP HOTEND_MIN_TEMP HOTEND_MAX_TEMP BED_TEMP
---------------- --------------- --------------- --------
               0             205             245       60
```

### 2. Composed material types that do not exist

`combine_filament_type` maps sub types onto names such as `PLA SILK`,
`PLA MATTE`, `PLA WOOD`, `PLA MARBLE` and `PLA HIGH SPEED`. None of those are
values of `filament_type`, whose enum is populated from `MaterialType::all()`.
The consequences:

- `find_closest_color_preset_by_vendor_and_type` compares the composed name
  against `p.config.opt_string("filament_type")`, so it can never match and the
  vendor + colour search is dead for every one of those sub types;
- `filament_id_by_type` then strips the modifier after the first space and
  resolves `PLA` anyway.

The net effect is that a silk or matte spool silently loses the vendor-specific
preset match it would otherwise get. Returning the base type directly restores
it. The `-CF` / `-GF` mappings are kept — those *are* real `MaterialType`
values — but they no longer append a suffix the main type already carries, so a
spool reporting `MAIN_TYPE` `PA12-CF` with `SUB_TYPE` `CF` yields `PA12-CF`
rather than `PA12-CF-CF`.

### 3. Vendor matching excluded almost every user preset

`find_closest_color_preset_by_vendor_and_type` required
`filaments.get_preset_base(p) == &p`. That is true only for system presets,
defaults, and user presets with an empty `inherits` — so a profile created the
normal way, by duplicating a system preset, was silently skipped and fell
through to the type-only lookup. Matching a spool to a vendor-specific profile
is exactly what a user would create such a preset for.

The requirement is now simply that the preset carries a `filament_id`. A derived
preset inherits its parent's id (`Preset.cpp` assigns
`preset.filament_id = inherit_preset->filament_id` on every load path), which is
also the id the plate's filament carries, and
`DevMappingUtil::ams_filament_mapping` uses that id only to break ties between
equal colour distances. So derived presets resolve to a correct identity rather
than a fabricated one, and a preset with no id is still skipped.

### 4. Variants were indistinguishable once the sub type was dropped

With the sub type no longer composed into `filament_type`, every Snapmaker PLA
variant is vendor `Snapmaker`, type `PLA` — `Snapmaker PLA Basic @U1`,
`PLA Matte @U1`, `PLA Silk @U1`, `PLA Eco @U1` and so on — leaving colour as the
only discriminator. A matte spool could therefore resolve to whichever variant
happened to sit nearest in colour. The same applies to the Polymaker range
shipped for the U1, where `Panchroma PLA Silk`, `PLA Matte` and `PLA Marble` all
declare `filament_type: "PLA"`.

Orca's profiles carry the variant in the preset *name*, so the search now
prefers a candidate whose name contains the spool's `SUB_TYPE`, ranking by
colour within that preference and falling back to colour alone when no name
matches. This is a heuristic, and deliberately a tie-break rather than a filter:
a spool whose sub type matches no preset name behaves exactly as before.

The match is case-insensitive and whole-word — the sub type must not be flanked
by alphanumeric characters — so `CF` matches `Snapmaker PETG-CF` but not
`Scaffold` or `Fiberon PA12-CF10`, and a multi-word sub type such as `95A HF`
matches as a phrase.

### 5. Crash on an empty spool colour

```cpp
unsigned int target_color_value =
    std::stoul(color_rgba.substr(0, color_rgba.length() - 2), nullptr, 16);
```

With an empty `filament_color_rgba` entry, `length() - 2` underflows, `substr`
returns the empty string and `std::stoul` throws `std::invalid_argument`, which
nothing catches — the slicer aborts. It is reachable whenever a slot reports a
loaded spool with no colour *and* the user has a visible preset matching that
vendor and type, because the parse sits inside the per-preset loop.

The profile side has the same shape: `default_filament_colour` is parsed with an
unguarded `std::stoul`, and a value carrying an alpha channel (`#RRGGBBAA`) is
read as a 32-bit number and compared against a 24-bit one.

Both are replaced by a `parse_rgb` helper that skips a leading `#`, drops any
alpha channel, validates the digits and reports failure instead of throwing. An
unparseable spool colour now falls through to the type-only lookup rather than
ranking presets against garbage. A slot that reports an empty colour also falls
back to the existing `FFFFFFFF` default, which previously applied only when the
array index was out of range.

`best_color_distance` was declared `int` and initialised to `0xffffffff`; it is
compared against an `unsigned int` and is now typed as one.

## Verification

The parsing path was exercised against a real U1 payload with the surrounding
code stubbed. Against upstream `main`:

```
slot=0 type='PLA'       color=14ADDBFF nozzle=0 bed=60
slot=2 type='PETG SILK' color=FF0000FF nozzle=0 bed=0
slot=3 type='PA-CF'     color=         nozzle=0 bed=0
```

and, on a payload where a matching vendor preset exists and the slot reports no
colour:

```
terminate called after throwing an instance of 'std::invalid_argument'
  what():  stoul
Aborted
```

With this PR, on the same payloads:

```
slot=0 type='PLA'    color=14ADDBFF nozzle=245 bed=60  -> vendor preset matched
slot=2 type='PETG'   color=FF0000FF nozzle=250 bed=70
slot=3 type='PA-CF'  color=FFFFFFFF nozzle=0   bed=100
slot=0 type='PLA'    color=FFFFFFFF nozzle=230 bed=55  (no crash)
```

A matte spool whose colour is nearest the `Basic` profile now resolves to
`Snapmaker PLA Matte` rather than `Snapmaker PLA Basic`.

## Screenshots/Recordings

N/A — no UI change.

## Tests

No suite under `tests/` covers `src/slic3r/Utils` printer agents, and the code
path reaches `GUI::wxGetApp()`, so this change carries documented verification
rather than a new Catch2 suite — per `tests/AGENTS.md`, a test belongs to the
suite matching the production code it exercises, and there is none here.
Verified manually on a Snapmaker U1 reporting `filament_detect` and
`print_task_config`.
