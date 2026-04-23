"""Tests for TriMet sensor entities."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN


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
    assert state.attributes["next_route"] == "Blue"
    assert state.attributes["next_route_id"] == "90"
    assert state.attributes["next_destination"] == "Hillsboro"
    assert state.attributes["next_vehicle_type"] == "max"
    assert state.attributes["live_prediction"] is True
    assert state.attributes["service_active"] is True
    assert state.attributes["summary"] == "Blue to Hillsboro in 4 min"
    assert len(state.attributes["matching_arrivals"]) == 2
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
    assert state.attributes["matching_arrivals"] == []
    assert state.attributes["service_active"] is False
    assert state.attributes["summary"] == "No matching arrivals"
