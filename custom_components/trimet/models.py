"""Normalized models and parsers for TriMet arrivals."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import math
import re
from typing import Any

from .const import (
    ATTR_ARRIVALS,
    CONF_APPROACH_TIME_MINUTES,
    CONF_ALLOWED_DIRECTIONS,
    CONF_ALLOWED_ROUTES,
    CONF_SENSOR_MODE,
    CONF_ALLOWED_VEHICLE_TYPES,
    CONF_DUE_SOON_MINUTES,
    CONF_FRIENDLY_NAME,
    CONF_MAX_ARRIVALS,
    CONF_MONITOR_ID,
    CONF_STOP_ID,
    DEFAULT_APPROACH_TIME_MINUTES,
    DEFAULT_DUE_SOON_MINUTES,
    DEFAULT_MAX_ARRIVALS,
    SENSOR_MODE_NEXT_ARRIVAL,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
    SUPPORTED_VEHICLE_TYPES,
    SUPPORTED_SENSOR_MODES,
    VEHICLE_TYPE_BUS,
    VEHICLE_TYPE_MAX,
    VEHICLE_TYPE_OTHER,
    VEHICLE_TYPE_STREETCAR,
    VEHICLE_TYPE_WES,
)


class VehicleType(StrEnum):
    """Normalized vehicle types used by the integration."""

    BUS = VEHICLE_TYPE_BUS
    MAX = VEHICLE_TYPE_MAX
    STREETCAR = VEHICLE_TYPE_STREETCAR
    WES = VEHICLE_TYPE_WES
    OTHER = VEHICLE_TYPE_OTHER


class SensorMode(StrEnum):
    """Primary sensor behavior modes."""

    NEXT_ARRIVAL = SENSOR_MODE_NEXT_ARRIVAL
    NEXT_CATCHABLE_ARRIVAL = SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL


@dataclass(slots=True, frozen=True)
class StopInfo:
    """A normalized TriMet stop."""

    stop_id: str
    name: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True, frozen=True)
class Arrival:
    """A normalized TriMet arrival."""

    stop_id: str
    route_id: str
    route_name: str | None
    destination: str | None
    direction: str | None
    vehicle_type: VehicleType
    scheduled_at: datetime
    estimated_at: datetime | None
    live_prediction: bool
    status: str | None
    canceled: bool
    drop_off_only: bool
    vehicle_id: str | None = None

    @property
    def effective_time(self) -> datetime:
        """Return the best available arrival timestamp."""
        return self.estimated_at or self.scheduled_at

    def minutes_until(self, reference: datetime) -> int:
        """Return whole minutes until the arrival, rounded up."""
        seconds = (self.effective_time - reference).total_seconds()
        return max(0, math.ceil(seconds / 60))

    @property
    def boardable(self) -> bool:
        """Whether this arrival should count for rider-facing entities."""
        return not self.canceled and not self.drop_off_only


@dataclass(slots=True, frozen=True)
class TriMetFeed:
    """Normalized arrival data for all fetched stops."""

    query_time: datetime | None
    last_updated: datetime
    stops: Mapping[str, StopInfo]
    arrivals_by_stop: Mapping[str, tuple[Arrival, ...]]

    @classmethod
    def empty(cls, when: datetime | None = None) -> "TriMetFeed":
        """Create an empty feed object."""
        now = when or datetime.now(UTC)
        return cls(query_time=now, last_updated=now, stops={}, arrivals_by_stop={})


@dataclass(slots=True, frozen=True)
class MonitorConfig:
    """A persisted monitor configuration."""

    monitor_id: str
    friendly_name: str
    stop_id: str
    allowed_routes: tuple[str, ...]
    allowed_directions: tuple[str, ...]
    allowed_vehicle_types: tuple[str, ...]
    due_soon_minutes: int = DEFAULT_DUE_SOON_MINUTES
    approach_time_minutes: int = DEFAULT_APPROACH_TIME_MINUTES
    sensor_mode: str = SENSOR_MODE_NEXT_ARRIVAL
    max_arrivals: int = DEFAULT_MAX_ARRIVALS

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MonitorConfig":
        """Build a monitor from stored config entry data."""
        return cls(
            monitor_id=str(data[CONF_MONITOR_ID]),
            friendly_name=str(data[CONF_FRIENDLY_NAME]),
            stop_id=str(data[CONF_STOP_ID]),
            allowed_routes=normalize_text_list(data.get(CONF_ALLOWED_ROUTES), uppercase=True),
            allowed_directions=normalize_text_list(
                data.get(CONF_ALLOWED_DIRECTIONS), lowercase=True
            ),
            allowed_vehicle_types=normalize_vehicle_types(
                data.get(CONF_ALLOWED_VEHICLE_TYPES)
            ),
            due_soon_minutes=int(data.get(CONF_DUE_SOON_MINUTES, DEFAULT_DUE_SOON_MINUTES)),
            approach_time_minutes=int(
                data.get(CONF_APPROACH_TIME_MINUTES, DEFAULT_APPROACH_TIME_MINUTES)
            ),
            sensor_mode=normalize_sensor_mode(data.get(CONF_SENSOR_MODE)),
            max_arrivals=int(data.get(CONF_MAX_ARRIVALS, DEFAULT_MAX_ARRIVALS)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert a monitor back to config entry storage."""
        return {
            CONF_MONITOR_ID: self.monitor_id,
            CONF_FRIENDLY_NAME: self.friendly_name,
            CONF_STOP_ID: self.stop_id,
            CONF_ALLOWED_ROUTES: list(self.allowed_routes),
            CONF_ALLOWED_DIRECTIONS: list(self.allowed_directions),
            CONF_ALLOWED_VEHICLE_TYPES: list(self.allowed_vehicle_types),
            CONF_DUE_SOON_MINUTES: self.due_soon_minutes,
            CONF_APPROACH_TIME_MINUTES: self.approach_time_minutes,
            CONF_SENSOR_MODE: self.sensor_mode,
            CONF_MAX_ARRIVALS: self.max_arrivals,
        }

    @property
    def sensor_mode_enum(self) -> SensorMode:
        """Return the configured sensor mode as an enum."""
        return SensorMode(normalize_sensor_mode(self.sensor_mode))

    def matches(self, arrival: Arrival) -> bool:
        """Return whether an arrival matches this monitor."""
        if arrival.stop_id != self.stop_id:
            return False
        if not arrival.boardable:
            return False
        if self.allowed_routes and arrival.route_id.upper() not in self.allowed_routes:
            return False
        if self.allowed_directions:
            direction = normalize_single_text(arrival.direction, lowercase=True)
            if direction not in self.allowed_directions:
                return False
        if self.allowed_vehicle_types and arrival.vehicle_type.value not in self.allowed_vehicle_types:
            return False
        return True


@dataclass(slots=True, frozen=True)
class MonitorSnapshot:
    """A computed, monitor-specific view of the shared feed."""

    monitor: MonitorConfig
    stop: StopInfo
    matching_arrivals: tuple[Arrival, ...]
    reference_time: datetime
    last_updated: datetime

    @property
    def next_arrival(self) -> Arrival | None:
        """Return the next matching arrival."""
        return self.matching_arrivals[0] if self.matching_arrivals else None

    @property
    def catchable_arrivals(self) -> tuple[Arrival, ...]:
        """Return arrivals that can be reached in time."""
        return tuple(
            arrival
            for arrival in self.matching_arrivals
            if arrival.minutes_until(self.reference_time)
            >= self.monitor.approach_time_minutes
        )

    @property
    def skipped_arrivals(self) -> tuple[Arrival, ...]:
        """Return arrivals that are too soon to catch."""
        return tuple(
            arrival
            for arrival in self.matching_arrivals
            if arrival.minutes_until(self.reference_time)
            < self.monitor.approach_time_minutes
        )

    @property
    def next_catchable_arrival(self) -> Arrival | None:
        """Return the next arrival that can still be caught."""
        return self.catchable_arrivals[0] if self.catchable_arrivals else None

    @property
    def primary_arrival(self) -> Arrival | None:
        """Return the arrival used for the primary sensor."""
        if self.monitor.sensor_mode_enum is SensorMode.NEXT_CATCHABLE_ARRIVAL:
            return self.next_catchable_arrival
        return self.next_arrival

    @property
    def primary_minutes(self) -> int | None:
        """Return minutes for the configured primary arrival."""
        primary_arrival = self.primary_arrival
        if primary_arrival is None:
            return None
        return primary_arrival.minutes_until(self.reference_time)

    @property
    def service_active(self) -> bool:
        """Return whether matching service is currently available."""
        return bool(self.matching_arrivals)

    @property
    def summary(self) -> str:
        """Return a human-readable summary string."""
        primary_arrival = self.primary_arrival
        if primary_arrival is None:
            if (
                self.monitor.sensor_mode_enum is SensorMode.NEXT_CATCHABLE_ARRIVAL
                and self.matching_arrivals
            ):
                departures_considered = min(
                    len(self.matching_arrivals), self.monitor.max_arrivals
                )
                return (
                    "No catchable arrivals in the next "
                    f"{departures_considered} departures"
                )
            return "No matching arrivals"

        line = _display_line(primary_arrival)
        minutes = primary_arrival.minutes_until(self.reference_time)
        destination = primary_arrival.destination or "service"
        return f"{line} to {destination} in {minutes} min"

    def _serialize_arrival(self, arrival: Arrival) -> dict[str, Any]:
        """Serialize one arrival for state attributes."""
        minutes = arrival.minutes_until(self.reference_time)
        serialized = {
            "line": _display_line(arrival),
            "destination": arrival.destination or "service",
            "minutes": minutes,
            "catchable": minutes >= self.monitor.approach_time_minutes,
            "live": arrival.live_prediction,
        }
        direction = _humanize_direction(arrival.direction)
        if direction is not None:
            serialized["direction"] = direction
        serialized["vehicle_type"] = arrival.vehicle_type.value
        return serialized

    def _serialize_arrivals(
        self, arrivals: Sequence[Arrival], *, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Serialize arrivals for state attributes."""
        selected_arrivals = arrivals if limit is None else arrivals[:limit]
        return [self._serialize_arrival(arrival) for arrival in selected_arrivals]

    def as_main_sensor_attributes(self) -> dict[str, Any]:
        """Return the shared attribute payload for the main sensor."""
        next_arrival = self.next_arrival
        primary_arrival = self.primary_arrival
        next_catchable_arrival = self.next_catchable_arrival
        arrivals = self._serialize_arrivals(
            self.matching_arrivals, limit=self.monitor.max_arrivals
        )

        attributes: dict[str, Any] = {
            "stop_id": self.monitor.stop_id,
            "stop_name": self.stop.name or self.stop.description or self.monitor.stop_id,
            "approach_time_minutes": self.monitor.approach_time_minutes,
            "sensor_mode": self.monitor.sensor_mode,
            "line": _display_line(primary_arrival) if primary_arrival else None,
            "destination": (
                (primary_arrival.destination or "service")
                if primary_arrival
                else None
            ),
            "vehicle_type": (
                primary_arrival.vehicle_type.value if primary_arrival else None
            ),
            "next_arrival_minutes": next_arrival.minutes_until(self.reference_time)
            if next_arrival
            else None,
            "next_catchable_arrival_minutes": (
                next_catchable_arrival.minutes_until(self.reference_time)
                if next_catchable_arrival
                else None
            ),
            ATTR_ARRIVALS: arrivals,
            "service_active": self.service_active,
            "summary": self.summary,
        }
        if self.monitor.allowed_routes:
            attributes["configured_lines"] = list(self.monitor.allowed_routes)
        if self.monitor.allowed_directions:
            attributes["configured_directions"] = list(self.monitor.allowed_directions)
        if self.monitor.allowed_vehicle_types:
            attributes["configured_vehicle_types"] = list(
                self.monitor.allowed_vehicle_types
            )
        return attributes


def normalize_text_list(
    value: str | Sequence[str] | None,
    *,
    uppercase: bool = False,
    lowercase: bool = False,
) -> tuple[str, ...]:
    """Normalize a string or list of strings into a unique tuple."""
    if value is None:
        return ()

    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = [str(item) for item in value]

    normalized: list[str] = []
    seen: set[str] = set()

    for raw_item in raw_items:
        item = raw_item.strip()
        if not item:
            continue
        if uppercase:
            item = item.upper()
        elif lowercase:
            item = item.lower()
        if item in seen:
            continue
        normalized.append(item)
        seen.add(item)

    return tuple(normalized)


def normalize_vehicle_types(value: str | Sequence[str] | None) -> tuple[str, ...]:
    """Normalize configured vehicle types."""
    normalized = normalize_text_list(value, lowercase=True)
    return tuple(item for item in normalized if item in SUPPORTED_VEHICLE_TYPES)


def normalize_sensor_mode(value: Any) -> str:
    """Normalize the configured primary sensor mode."""
    normalized = normalize_single_text(
        str(value) if value is not None else None, lowercase=True
    )
    if normalized in SUPPORTED_SENSOR_MODES:
        return normalized
    return SENSOR_MODE_NEXT_ARRIVAL


def _display_line(arrival: Arrival | None) -> str | None:
    """Return a compact, human-readable line label."""
    if arrival is None:
        return None

    route_name = normalize_single_text(arrival.route_name)
    route_id = normalize_single_text(arrival.route_id)

    if arrival.vehicle_type is VehicleType.BUS:
        return route_id or route_name

    if arrival.vehicle_type is VehicleType.WES and route_name:
        if "wes" in route_name.lower():
            return "WES"

    if route_name:
        cleaned = route_name
        cleaned = re.sub(r"(?i)^portland streetcar\s+", "", cleaned)
        cleaned = re.sub(r"(?i)^max\s+", "", cleaned)
        cleaned = re.sub(r"(?i)\s+streetcar$", "", cleaned)
        cleaned = re.sub(r"(?i)\s+line$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
        if cleaned:
            return cleaned

    return route_id or route_name or "Service"


def _humanize_direction(value: str | None) -> str | None:
    """Return a readable direction string."""
    normalized = normalize_single_text(value)
    if normalized is None:
        return None

    collapsed = re.sub(r"[^a-z]", "", normalized.lower())
    mapping = {
        "n": "Northbound",
        "s": "Southbound",
        "e": "Eastbound",
        "w": "Westbound",
        "nb": "Northbound",
        "sb": "Southbound",
        "eb": "Eastbound",
        "wb": "Westbound",
        "northbound": "Northbound",
        "southbound": "Southbound",
        "eastbound": "Eastbound",
        "westbound": "Westbound",
    }
    return mapping.get(collapsed, normalized)


def normalize_single_text(
    value: str | None, *, uppercase: bool = False, lowercase: bool = False
) -> str | None:
    """Normalize one string value."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if uppercase:
        return normalized.upper()
    if lowercase:
        return normalized.lower()
    return normalized


def parse_arrivals_response(payload: Mapping[str, Any]) -> TriMetFeed:
    """Parse a TriMet arrivals API response."""
    result = payload.get("resultSet")
    if not isinstance(result, Mapping):
        raise ValueError("Response did not contain a resultSet object")

    query_time = _parse_timestamp(result.get("queryTime"))
    last_updated = query_time or datetime.now(UTC)

    routes = {
        str(route.get("route")): route
        for route in _as_list(result.get("route"))
        if isinstance(route, Mapping) and route.get("route") is not None
    }

    stops: dict[str, StopInfo] = {}
    for location in _as_list(result.get("location")):
        if not isinstance(location, Mapping) or location.get("locid") is None:
            continue

        stop_id = str(location["locid"])
        stops[stop_id] = StopInfo(
            stop_id=stop_id,
            name=_string_or_none(location.get("desc")),
            description=_string_or_none(location.get("desc")),
            latitude=_float_or_none(location.get("lat")),
            longitude=_float_or_none(location.get("lng")),
        )

    arrivals_by_stop: dict[str, list[Arrival]] = {}

    for raw_arrival in _as_list(result.get("arrival")):
        if not isinstance(raw_arrival, Mapping):
            continue

        stop_id = str(raw_arrival.get("locid", ""))
        if not stop_id:
            continue

        route_id = str(raw_arrival.get("route", ""))
        route_meta = routes.get(route_id, {})

        scheduled_at = _parse_timestamp(raw_arrival.get("scheduled"))
        if scheduled_at is None:
            continue

        estimated_at = _parse_timestamp(raw_arrival.get("estimated"))
        status = _string_or_none(raw_arrival.get("status"))

        arrival = Arrival(
            stop_id=stop_id,
            route_id=route_id,
            route_name=_string_or_none(route_meta.get("desc")),
            destination=_string_or_none(raw_arrival.get("fullSign"))
            or _string_or_none(raw_arrival.get("shortSign")),
            direction=_string_or_none(raw_arrival.get("dir")),
            vehicle_type=_normalize_vehicle_type(raw_arrival, route_meta),
            scheduled_at=scheduled_at,
            estimated_at=estimated_at,
            live_prediction=estimated_at is not None and status != "scheduled",
            status=status,
            canceled=status == "canceled",
            drop_off_only=bool(raw_arrival.get("dropOffOnly")),
            vehicle_id=_string_or_none(raw_arrival.get("vehicleID")),
        )
        arrivals_by_stop.setdefault(stop_id, []).append(arrival)

    sorted_arrivals_by_stop = {
        stop_id: tuple(sorted(arrivals, key=lambda item: item.effective_time))
        for stop_id, arrivals in arrivals_by_stop.items()
    }

    return TriMetFeed(
        query_time=query_time,
        last_updated=last_updated,
        stops=stops,
        arrivals_by_stop=sorted_arrivals_by_stop,
    )


def merge_feeds(feeds: Iterable[TriMetFeed]) -> TriMetFeed:
    """Merge chunked TriMet feeds into one payload."""
    feed_list = list(feeds)
    if not feed_list:
        return TriMetFeed.empty()

    stops: dict[str, StopInfo] = {}
    arrivals_by_stop: dict[str, list[Arrival]] = {}
    query_times: list[datetime] = []
    last_updated = feed_list[0].last_updated

    for feed in feed_list:
        if feed.query_time:
            query_times.append(feed.query_time)
        if feed.last_updated > last_updated:
            last_updated = feed.last_updated

        stops.update(feed.stops)
        for stop_id, arrivals in feed.arrivals_by_stop.items():
            arrivals_by_stop.setdefault(stop_id, []).extend(arrivals)

    return TriMetFeed(
        query_time=max(query_times) if query_times else None,
        last_updated=last_updated,
        stops=stops,
        arrivals_by_stop={
            stop_id: tuple(sorted(arrivals, key=lambda item: item.effective_time))
            for stop_id, arrivals in arrivals_by_stop.items()
        },
    )


def _normalize_vehicle_type(
    arrival: Mapping[str, Any], route: Mapping[str, Any]
) -> VehicleType:
    """Map TriMet route metadata to a stable vehicle type."""
    route_type = normalize_single_text(_string_or_none(route.get("type")), uppercase=True)
    route_subtype = normalize_single_text(
        _string_or_none(route.get("routeSubType")), lowercase=True
    )

    if bool(arrival.get("streetCar")) or route_subtype == "streetcar":
        return VehicleType.STREETCAR
    if route_subtype == "light rail":
        return VehicleType.MAX
    if route_subtype == "commuter rail":
        return VehicleType.WES
    if route_type == "B" or route_subtype in {"bus", "brt", "shuttle"}:
        return VehicleType.BUS
    return VehicleType.OTHER


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a TriMet millisecond timestamp."""
    if value in (None, ""):
        return None
    try:
        timestamp_ms = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _as_list(value: Any) -> list[Any]:
    """Normalize a TriMet list-or-object field."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _string_or_none(value: Any) -> str | None:
    """Return a string if the value is not empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    """Convert a value to float when possible."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
