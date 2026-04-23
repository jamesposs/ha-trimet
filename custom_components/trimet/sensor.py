"""Sensor platform for TriMet."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TriMetConfigEntry
from .entity import TriMetMonitorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TriMetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TriMet sensor entities."""
    del hass
    entities: list[SensorEntity] = []
    for monitor in entry.runtime_data.coordinator.iter_monitors():
        entities.append(TriMetNextArrivalSensor(entry, monitor.monitor_id))
        entities.append(TriMetSummarySensor(entry, monitor.monitor_id))
    async_add_entities(entities)


class TriMetNextArrivalSensor(TriMetMonitorEntity, SensorEntity):
    """Minutes until the next matching arrival."""

    _attr_icon = "mdi:train-bus"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, entry: TriMetConfigEntry, monitor_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(entry, monitor_id, "next_arrival")

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        monitor = self.monitor
        return f"{monitor.friendly_name} Next Arrival" if monitor else None

    @property
    def native_value(self) -> int | None:
        """Return the next arrival in minutes."""
        snapshot = self.snapshot
        next_arrival = snapshot.next_arrival if snapshot else None
        if snapshot is None or next_arrival is None:
            return None
        return next_arrival.minutes_until(snapshot.reference_time)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        snapshot = self.snapshot
        if snapshot is None:
            return {}
        return snapshot.as_main_sensor_attributes()


class TriMetSummarySensor(TriMetMonitorEntity, SensorEntity):
    """Human-readable summary of the next matching arrival."""

    _attr_icon = "mdi:format-list-text"

    def __init__(self, entry: TriMetConfigEntry, monitor_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(entry, monitor_id, "summary")

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        monitor = self.monitor
        return f"{monitor.friendly_name} Summary" if monitor else None

    @property
    def native_value(self) -> str | None:
        """Return a friendly summary string."""
        snapshot = self.snapshot
        next_arrival = snapshot.next_arrival if snapshot else None
        if snapshot is None:
            return None
        if next_arrival is None:
            return "No matching arrivals"

        route_name = next_arrival.route_name or next_arrival.route_id
        minutes = next_arrival.minutes_until(snapshot.reference_time)
        destination = next_arrival.destination or "service"
        return f"{route_name} to {destination} in {minutes} min"
