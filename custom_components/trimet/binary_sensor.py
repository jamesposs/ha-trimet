"""Binary sensor platform for TriMet."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TriMetConfigEntry
from .entity import TriMetMonitorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TriMetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TriMet binary sensor entities."""
    del hass
    entities: list[BinarySensorEntity] = []
    for monitor in entry.runtime_data.coordinator.iter_monitors():
        entities.append(TriMetDueSoonBinarySensor(entry, monitor.monitor_id))
    async_add_entities(entities)


class TriMetDueSoonBinarySensor(TriMetMonitorEntity, BinarySensorEntity):
    """Whether the next matching arrival is due soon."""

    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, entry: TriMetConfigEntry, monitor_id: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(entry, monitor_id, "due_soon")

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        monitor = self.monitor
        return f"{monitor.friendly_name} Due Soon" if monitor else None

    @property
    def is_on(self) -> bool | None:
        """Return whether the next arrival is within the monitor threshold."""
        snapshot = self.snapshot
        next_arrival = snapshot.next_arrival if snapshot else None
        if snapshot is None or next_arrival is None:
            return False

        return (
            next_arrival.minutes_until(snapshot.reference_time)
            <= snapshot.monitor.due_soon_minutes
        )
