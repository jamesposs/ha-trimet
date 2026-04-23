"""The TriMet integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TriMetApiClient
from .const import CONF_POLL_INTERVAL_SECONDS, LOGGER, PLATFORMS
from .coordinator import TriMetDataUpdateCoordinator

type TriMetConfigEntry = ConfigEntry["TriMetRuntimeData"]


@dataclass(slots=True)
class TriMetRuntimeData:
    """Runtime data stored on the config entry."""

    api: TriMetApiClient
    coordinator: TriMetDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: TriMetConfigEntry) -> bool:
    """Set up TriMet from a config entry."""
    session = async_get_clientsession(hass)
    api = TriMetApiClient(session=session, api_key=entry.data[CONF_API_KEY])
    coordinator = TriMetDataUpdateCoordinator(hass=hass, api=api, entry=entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TriMetRuntimeData(api=api, coordinator=coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_handle_entry_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TriMetConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_handle_entry_update(
    hass: HomeAssistant, entry: TriMetConfigEntry
) -> None:
    """Reload the integration after an options update."""
    LOGGER.debug(
        "Reloading TriMet entry %s after updated options or poll interval %s",
        entry.entry_id,
        entry.options.get(CONF_POLL_INTERVAL_SECONDS, entry.data.get(CONF_POLL_INTERVAL_SECONDS)),
    )
    await hass.config_entries.async_reload(entry.entry_id)
