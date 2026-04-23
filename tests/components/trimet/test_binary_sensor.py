"""Tests for TriMet binary sensors."""

from __future__ import annotations


async def test_binary_sensor_states(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test due soon and service active sensors."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    due_soon = hass.states.get("binary_sensor.hollywood_blue_due_soon")
    assert due_soon is not None
    assert due_soon.state == "on"

    service_active = hass.states.get("binary_sensor.hollywood_blue_service_active")
    assert service_active is not None
    assert service_active.state == "on"


async def test_binary_sensors_turn_off_when_no_match(
    hass, mock_config_entry, mock_fetch_arrivals
) -> None:
    """Test binary sensors when no arrivals match filters."""
    mock_config_entry.options["monitors"][0]["allowed_vehicle_types"] = ["wes"]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    due_soon = hass.states.get("binary_sensor.hollywood_blue_due_soon")
    assert due_soon is not None
    assert due_soon.state == "off"

    service_active = hass.states.get("binary_sensor.hollywood_blue_service_active")
    assert service_active is not None
    assert service_active.state == "off"
