# Portland TriMet Arrivals for Home Assistant
<!-- GitHub repo description: A Home Assistant custom integration for Portland-area TriMet real-time arrivals and stop monitors. -->
<!-- Short tagline alternative: Portland TriMet arrivals and stop monitors for Home Assistant. -->

`ha-trimet` is an independent Home Assistant custom integration for TriMet real-time arrivals in the Portland metro area. It lets you create multiple stop monitors from one integration entry, polls TriMet once per refresh cycle for all configured stops, and exposes a clean monitor-first entity model that works well in standard Lovelace cards. This is a community integration and is not affiliated with or endorsed by TriMet.

## Features

- One config entry for your TriMet developer API key and global polling settings
- Multiple UI-managed stop monitors from the integration options flow
- Shared polling with `DataUpdateCoordinator`
- One primary sensor per configured monitor
- Per-monitor filtering by:
  - stop ID
  - route/line list
  - direction list
  - vehicle types (`bus`, `max`, `streetcar`, `wes`)
  - approach time to the stop
  - primary sensor mode (`next_arrival` or `next_catchable_arrival`)
  - due soon threshold
  - number of arrivals kept in attributes
- Optional helper entity:
  - due soon binary sensor

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository:
   - Repository URL: `https://github.com/jamesposs/ha-trimet`
   - Category: `Integration`
3. Install `Portland TriMet Arrivals`.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/trimet` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Configuration

### Before You Start

You need a TriMet developer API key from [developer.trimet.org](https://developer.trimet.org/).

### Add The Integration

1. In Home Assistant, go to `Settings` -> `Devices & services`.
2. Select `Add integration`.
3. Search for `Portland TriMet Arrivals`.
4. Enter:
   - your TriMet API key
   - an optional polling interval in seconds

### Add Or Edit Monitors

After setup, open the integration's `Configure` or `Options` flow to manage monitors.

Each monitor includes:

- Friendly name
- Stop ID
- Allowed routes/lines as a comma-separated list, or blank for all routes
- Allowed directions as a comma-separated list, or blank for all directions
- Allowed vehicle types as a comma-separated list using `bus`, `max`, `streetcar`, `wes`, or blank for all
- Approach time to the stop in minutes
- Primary sensor mode:
  - `next_arrival`
  - `next_catchable_arrival`
- Due soon threshold in minutes
- Number of matching arrivals to expose in attributes

## Entities

Each monitor creates one primary sensor and one optional helper binary sensor.

### Main Sensor

State: integer minutes until the configured primary arrival.

The primary sensor can either track the literal next matching arrival or the next catchable arrival after your configured approach time. When no arrivals match, the sensor becomes `unknown` instead of holding a stale value. In catchable mode, the sensor also becomes `unknown` when arrivals exist but none can be caught in time. When the API is unavailable, the entity becomes unavailable.

The main `arrivals` list is intentionally compact and easy to template. Each item includes `line`, `destination`, `minutes`, `catchable`, and `live`.

Important attributes include:

- `stop_id`
- `stop_name`
- `line`
- `destination`
- `vehicle_type`
- `approach_time_minutes`
- `next_arrival_minutes`
- `next_catchable_arrival_minutes`
- `arrivals`
- `service_active`
- `summary`

### Due Soon Binary Sensor

Turns on when the literal next matching arrival is at or below the monitor's threshold.

## Filtering Rules

Filtering is deterministic and always applied in this order:

1. Ignore canceled and drop-off-only arrivals.
2. Match stop ID.
3. Match route list if one is configured.
4. Match direction list if one is configured.
5. Match vehicle type list if one is configured.
6. Sort by the soonest effective arrival time.

Notes:

- Route filters match TriMet route numbers/IDs, not free-form labels.
- Direction filters compare the TriMet direction text case-insensitively.
- Vehicle type is normalized from TriMet route metadata into `bus`, `max`, `streetcar`, `wes`, or `other`.

## Notes And Limitations

- This integration uses TriMet's arrivals API and depends on that service being available.
- Monitor stop IDs are accepted as entered and validated indirectly through live API results.
- The current v1 monitor editor uses the integration options flow rather than dedicated config subentries, so large monitor lists are functional but not especially fancy.
- Changing the API key is not implemented in the options flow yet; remove and re-add the integration if needed.

## Development

The repository includes:

- HACS validation workflow
- `hassfest` workflow
- pytest-based tests under `tests/components/trimet`

## Disclaimer

TriMet is a trademark of Tri-County Metropolitan Transportation District of Oregon. This project is an independent community Home Assistant custom integration and is not affiliated with or endorsed by TriMet.
