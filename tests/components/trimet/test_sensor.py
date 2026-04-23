"""Tests for TriMet sensor entities."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN

from custom_components.trimet.const import (
    ATTR_CATCHABLE_ARRIVALS,
    ATTR_MATCHING_ARRIVALS,
    ATTR_SKIPPED_ARRIVALS,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
    SENSOR_MODE_NEXT_ARRIVAL,
)


async def test_primary_sensor_state_and_attributes(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test normal primary sensor state and attributes."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hollywood_blue")
    assert state is not None
    assert state.state == "4"
    assert state.attributes["stop_id"] == "1234"
    assert state.attributes["stop_name"] == "Hollywood/NE 42nd Ave TC MAX Station"
    assert state.attributes["configured_lines"] == ["90"]
    assert state.attributes["configured_directions"] == ["southbound"]
    assert state.attributes["configured_vehicle_types"] == ["max"]
    assert state.attributes["due_soon_threshold"] == 10
    assert state.attributes["approach_time_minutes"] == 0
    assert state.attributes["sensor_mode"] == SENSOR_MODE_NEXT_ARRIVAL
    assert state.attributes["next_route"] == "Blue"
    assert state.attributes["next_route_id"] == "90"
    assert state.attributes["next_destination"] == "Hillsboro"
    assert state.attributes["next_vehicle_type"] == "max"
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_arrival"]["catchable"] is True
    assert state.attributes["next_catchable_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival"]["catchable"] is True
    assert state.attributes["live_prediction"] is True
    assert state.attributes["service_active"] is True
    assert state.attributes["summary"] == "Blue to Hillsboro in 4 min"
    assert len(state.attributes[ATTR_MATCHING_ARRIVALS]) == 2
    assert len(state.attributes[ATTR_CATCHABLE_ARRIVALS]) == 2
    assert hass.states.get("sensor.hollywood_blue_summary") is None


async def test_main_sensor_becomes_unknown_when_no_arrivals_match(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test unknown state when filters remove all arrivals."""
    mock_config_entry.options["monitors"][0]["allowed_routes"] = ["12"]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hollywood_blue")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_MATCHING_ARRIVALS] == []
    assert state.attributes["service_active"] is False
    assert state.attributes["summary"] == "No matching arrivals"


async def test_catchable_mode_uses_first_catchable_arrival(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test catchable mode selects the first reachable departure."""
    monitor = mock_config_entry.options["monitors"][0]
    monitor["sensor_mode"] = SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL
    monitor["approach_time_minutes"] = 5
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hollywood_blue")
    assert state is not None
    assert state.state == "9"
    assert state.attributes["sensor_mode"] == SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival_minutes"] == 9
    assert state.attributes["summary"] == "Blue to Hillsboro in 9 min"
    assert [item["catchable"] for item in state.attributes[ATTR_MATCHING_ARRIVALS]] == [
        False,
        True,
    ]
    assert len(state.attributes[ATTR_CATCHABLE_ARRIVALS]) == 1
    assert len(state.attributes[ATTR_SKIPPED_ARRIVALS]) == 1


async def test_catchable_mode_becomes_unknown_when_no_departure_is_reachable(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test catchable mode goes unknown when all matching departures are too soon."""
    monitor = mock_config_entry.options["monitors"][0]
    monitor["sensor_mode"] = SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL
    monitor["approach_time_minutes"] = 15
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hollywood_blue")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival_minutes"] is None
    assert state.attributes[ATTR_CATCHABLE_ARRIVALS] == []
    assert len(state.attributes[ATTR_SKIPPED_ARRIVALS]) == 2
    assert state.attributes["service_active"] is True
    assert state.attributes["summary"] == "No catchable arrivals in the next 2 departures"
