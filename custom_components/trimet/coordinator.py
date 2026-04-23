"""Coordinator for shared TriMet arrival polling."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TriMetApiClient,
    TriMetAuthenticationError,
    TriMetConnectionError,
    TriMetResponseError,
)
from .const import (
    CONF_MONITORS,
    CONF_POLL_INTERVAL_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    LOGGER,
)
from .models import MonitorConfig, MonitorSnapshot, StopInfo, TriMetFeed


class TriMetDataUpdateCoordinator(DataUpdateCoordinator[TriMetFeed]):
    """Coordinate shared TriMet polling for all configured monitors."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: TriMetApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.entry = entry
        self.monitors = _load_monitors(entry)

        poll_interval = int(
            entry.options.get(
                CONF_POLL_INTERVAL_SECONDS,
                entry.data.get(CONF_POLL_INTERVAL_SECONDS, DEFAULT_POLL_INTERVAL_SECONDS),
            )
        )

        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=poll_interval),
            always_update=False,
        )

    async def _async_update_data(self) -> TriMetFeed:
        """Fetch fresh arrivals from TriMet."""
        stop_ids = {monitor.stop_id for monitor in self.monitors.values()}

        try:
            return await self.api.async_fetch_arrivals(stop_ids)
        except TriMetAuthenticationError as err:
            raise ConfigEntryAuthFailed("TriMet rejected the configured API key") from err
        except TriMetConnectionError as err:
            raise UpdateFailed(f"Unable to contact TriMet: {err}") from err
        except TriMetResponseError as err:
            raise UpdateFailed(f"Unexpected response from TriMet: {err}") from err

    def iter_monitors(self) -> Iterable[MonitorConfig]:
        """Iterate over configured monitors."""
        return self.monitors.values()

    def get_monitor(self, monitor_id: str) -> MonitorConfig | None:
        """Return one monitor by ID."""
        return self.monitors.get(monitor_id)

    def get_monitor_snapshot(self, monitor_id: str) -> MonitorSnapshot | None:
        """Build a monitor-specific view from the shared coordinator payload."""
        monitor = self.monitors.get(monitor_id)
        data = self.data

        if monitor is None or data is None:
            return None

        stop = data.stops.get(monitor.stop_id) or StopInfo(stop_id=monitor.stop_id, name=monitor.stop_id)
        arrivals = tuple(
            arrival
            for arrival in data.arrivals_by_stop.get(monitor.stop_id, ())
            if monitor.matches(arrival)
        )
        reference_time = data.query_time or data.last_updated
        return MonitorSnapshot(
            monitor=monitor,
            stop=stop,
            matching_arrivals=arrivals,
            reference_time=reference_time,
            last_updated=data.last_updated,
        )


def _load_monitors(entry: ConfigEntry) -> dict[str, MonitorConfig]:
    """Load persisted monitors from a config entry."""
    raw_monitors = entry.options.get(CONF_MONITORS, [])
    monitors: dict[str, MonitorConfig] = {}

    if not isinstance(raw_monitors, list):
        return monitors

    for raw_monitor in raw_monitors:
        if not isinstance(raw_monitor, dict):
            continue
        monitor = MonitorConfig.from_dict(raw_monitor)
        monitors[monitor.monitor_id] = monitor

    return monitors
