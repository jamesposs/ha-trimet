"""Tests for TriMet sensor entities."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN

from custom_components.trimet.const import (
    ATTR_ARRIVALS,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
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
    assert state.attributes["line"] == "Blue"
    assert state.attributes["destination"] == "Hillsboro"
    assert state.attributes["vehicle_type"] == "max"
    assert state.attributes["approach_time_minutes"] == 0
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival_minutes"] == 4
    assert state.attributes["service_active"] is True
    assert state.attributes["summary"] == "Blue to Hillsboro in 4 min"
    assert "configured_lines" not in state.attributes
    assert "configured_directions" not in state.attributes
    assert "configured_vehicle_types" not in state.attributes
    assert "sensor_mode" not in state.attributes
    assert "due_soon_threshold" not in state.attributes
    assert "next_route" not in state.attributes
    assert "next_route_id" not in state.attributes
    assert "next_destination" not in state.attributes
    assert "next_vehicle_type" not in state.attributes
    assert "next_scheduled_at" not in state.attributes
    assert "next_estimated_at" not in state.attributes
    assert "live_prediction" not in state.attributes
    assert "next_arrival" not in state.attributes
    assert "next_catchable_arrival" not in state.attributes
    assert state.attributes[ATTR_ARRIVALS] == [
        {
            "line": "Blue",
            "destination": "Hillsboro",
            "minutes": 4,
            "catchable": True,
            "live": True,
        },
        {
            "line": "Blue",
            "destination": "Hillsboro",
            "minutes": 9,
            "catchable": True,
            "live": True,
        },
    ]
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
    assert state.attributes[ATTR_ARRIVALS] == []
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
    assert "sensor_mode" not in state.attributes
    assert state.attributes["line"] == "Blue"
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival_minutes"] == 9
    assert state.attributes["summary"] == "Blue to Hillsboro in 9 min"
    assert [item["catchable"] for item in state.attributes[ATTR_ARRIVALS]] == [
        False,
        True,
    ]
    assert len(state.attributes[ATTR_ARRIVALS]) == 2


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
    assert state.attributes["line"] is None
    assert state.attributes["next_arrival_minutes"] == 4
    assert state.attributes["next_catchable_arrival_minutes"] is None
    assert [item["catchable"] for item in state.attributes[ATTR_ARRIVALS]] == [
        False,
        False,
    ]
    assert state.attributes["service_active"] is True
    assert state.attributes["summary"] == "No catchable arrivals in the next 2 departures"


async def test_sensor_uses_compact_line_name_for_summary_and_arrivals(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test the primary sensor exposes a compact line label."""
    monitor = mock_config_entry.options["monitors"][0]
    monitor["allowed_routes"] = ["193"]
    monitor["allowed_directions"] = ["westbound"]
    monitor["allowed_vehicle_types"] = ["streetcar"]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hollywood_blue")
    assert state is not None
    assert state.state == "3"
    assert state.attributes["line"] == "NS"
    assert state.attributes["destination"] == "NW 23rd"
    assert state.attributes["vehicle_type"] == "streetcar"
    assert state.attributes["summary"] == "NS to NW 23rd in 3 min"
    assert state.attributes[ATTR_ARRIVALS] == [
        {
            "line": "NS",
            "destination": "NW 23rd",
            "minutes": 3,
            "catchable": True,
            "live": True,
        }
    ]
