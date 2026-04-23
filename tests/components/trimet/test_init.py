"""Tests for TriMet setup and unload."""

from __future__ import annotations

from custom_components.trimet.const import DOMAIN


async def test_setup_and_unload_entry(hass, mock_config_entry, mock_fetch_arrivals) -> None:
    """Test config entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data is not None
    assert mock_config_entry.runtime_data.coordinator.last_update_success is True
    assert mock_fetch_arrivals.await_count == 1

    states = hass.states.async_all(DOMAIN)
    assert len(states) == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_all(DOMAIN) == []
