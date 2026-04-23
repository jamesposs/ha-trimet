"""Shared entity helpers for TriMet entities."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TriMetConfigEntry
from .coordinator import TriMetDataUpdateCoordinator
from .models import MonitorConfig, MonitorSnapshot


class TriMetMonitorEntity(CoordinatorEntity[TriMetDataUpdateCoordinator]):
    """Base class for TriMet monitor entities."""

    _attr_has_entity_name = False

    def __init__(
        self,
        entry: TriMetConfigEntry,
        monitor_id: str,
        entity_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry.runtime_data.coordinator)
        self._monitor_id = monitor_id
        self._attr_unique_id = f"{entry.entry_id}_{monitor_id}_{entity_suffix}"

    @property
    def monitor(self) -> MonitorConfig | None:
        """Return the current monitor."""
        return self.coordinator.get_monitor(self._monitor_id)

    @property
    def snapshot(self) -> MonitorSnapshot | None:
        """Return the current monitor snapshot."""
        return self.coordinator.get_monitor_snapshot(self._monitor_id)

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.monitor is not None
