"""Tests for the TriMet coordinator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except ImportError:  # pragma: no cover
    from tests.common import MockConfigEntry

from custom_components.trimet.api import (
    TriMetAuthenticationError,
    TriMetConnectionError,
)
from custom_components.trimet.const import (
    CONF_MONITORS,
    CONF_POLL_INTERVAL_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
)
from custom_components.trimet.coordinator import TriMetDataUpdateCoordinator
from custom_components.trimet.models import (
    Arrival,
    MonitorConfig,
    MonitorSnapshot,
    StopInfo,
    VehicleType,
    parse_arrivals_response,
)


class StubApi:
    """Simple API stub for coordinator tests."""

    def __init__(self, *, feed=None, error: Exception | None = None) -> None:
        self.feed = feed
        self.error = error
        self.requested_stop_ids: set[str] | None = None

    async def async_fetch_arrivals(self, stop_ids: set[str]):
        self.requested_stop_ids = stop_ids
        if self.error is not None:
            raise self.error
        return self.feed


async def test_coordinator_filters_route_direction_and_vehicle_type(
    hass, sample_feed, mock_config_entry
) -> None:
    """Test local filtering from the shared feed."""
    api = StubApi(feed=sample_feed)
    coordinator = TriMetDataUpdateCoordinator(hass, api, mock_config_entry)

    await coordinator.async_refresh()

    assert api.requested_stop_ids == {"1234"}
    snapshot = coordinator.get_monitor_snapshot("monitor_blue")
    assert snapshot is not None
    assert len(snapshot.matching_arrivals) == 2
    assert snapshot.next_arrival is not None
    assert snapshot.next_arrival.route_id == "90"
    assert snapshot.next_arrival.direction == "Southbound"
    assert snapshot.next_arrival.vehicle_type.value == "max"
    assert snapshot.next_catchable_arrival is not None
    assert snapshot.primary_minutes == 4


async def test_coordinator_computes_catchable_arrivals(
    hass, sample_feed, mock_config_entry
) -> None:
    """Test decision-oriented catchable arrival selection."""
    monitor = mock_config_entry.options[CONF_MONITORS][0]
    monitor["approach_time_minutes"] = 5
    monitor["sensor_mode"] = SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL
    api = StubApi(feed=sample_feed)
    coordinator = TriMetDataUpdateCoordinator(hass, api, mock_config_entry)

    await coordinator.async_refresh()

    snapshot = coordinator.get_monitor_snapshot("monitor_blue")
    assert snapshot is not None
    assert snapshot.next_arrival is not None
    assert snapshot.next_arrival.minutes_until(snapshot.reference_time) == 4
    assert snapshot.next_catchable_arrival is not None
    assert snapshot.next_catchable_arrival.minutes_until(snapshot.reference_time) == 9
    assert len(snapshot.catchable_arrivals) == 1
    assert len(snapshot.skipped_arrivals) == 1
    assert snapshot.primary_minutes == 9
    assert snapshot.summary == "Blue to Hillsboro in 9 min"


def test_parse_arrivals_response_preserves_stop_name_from_arrival_when_needed(
    sample_api_response,
) -> None:
    """Test readable stop names survive even if the location block is sparse."""
    sample_api_response["resultSet"]["location"] = [{"locid": 1234}]
    sample_api_response["resultSet"]["arrival"][0]["locDesc"] = "Hollywood TC Platform A"
    sample_api_response["resultSet"]["arrival"][1]["locDesc"] = "Hollywood TC Platform A"

    feed = parse_arrivals_response(sample_api_response)

    assert feed.stops["1234"].name == "Hollywood TC Platform A"
    assert feed.stops["1234"].description == "Hollywood TC Platform A"


def test_parse_arrivals_response_uses_location_desc_and_location_id(
    sample_api_response,
) -> None:
    """Test location desc/id win for stop names and direction fallback."""
    sample_api_response["resultSet"]["location"] = [
        {
            "id": 10777,
            "desc": "NW 21st & Northrup",
            "dir": "Westbound",
            "lat": 45.531346,
            "lng": -122.694455,
        }
    ]
    sample_api_response["resultSet"]["arrival"] = [
        {
            "locid": 10777,
            "route": 193,
            "shortSign": "Portland Streetcar NS Line to NW 23rd Ave",
            "fullSign": "Portland Streetcar NS Line to NW 23rd Ave",
            "dir": 0,
            "routeColor": "72A130",
            "scheduled": sample_api_response["resultSet"]["queryTime"] + 8 * 60_000,
            "estimated": sample_api_response["resultSet"]["queryTime"] + 8 * 60_000,
            "status": "estimated",
            "streetCar": True,
        }
    ]

    feed = parse_arrivals_response(sample_api_response)
    arrival = feed.arrivals_by_stop["10777"][0]

    assert feed.stops["10777"].name == "NW 21st & Northrup"
    assert feed.stops["10777"].description == "NW 21st & Northrup"
    assert arrival.direction == "Westbound"
    assert arrival.destination == "NW 23rd Ave"
    assert arrival.route_color == "#72A130"


def test_parse_arrivals_response_normalizes_delay_and_status_fields(
    sample_api_response,
) -> None:
    """Test delay-related normalized fields across TriMet status variants."""
    query_time = sample_api_response["resultSet"]["queryTime"]
    sample_api_response["resultSet"]["arrival"] = [
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 5 * 60_000,
            "estimated": query_time + 5 * 60_000,
            "status": "estimated",
        },
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 6 * 60_000,
            "estimated": query_time + 10 * 60_000,
            "status": "estimated",
        },
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 12 * 60_000,
            "status": "scheduled",
        },
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 15 * 60_000,
            "estimated": query_time + 19 * 60_000,
            "status": "delayed",
            "reason": "Traffic issue",
        },
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 20 * 60_000,
            "status": "canceled",
            "reason": "Operator unavailable",
        },
    ]

    feed = parse_arrivals_response(sample_api_response)
    on_time, late, scheduled, uncertain, canceled = feed.arrivals_by_stop["1234"]

    assert on_time.live is True
    assert on_time.delay_minutes == 0
    assert on_time.delayed is False
    assert late.live is True
    assert late.delay_minutes == 4
    assert late.delayed is True
    assert scheduled.live is False
    assert scheduled.delay_minutes is None
    assert scheduled.status == "scheduled"
    assert uncertain.live is False
    assert uncertain.uncertain is True
    assert uncertain.reason == "Traffic issue"
    assert uncertain.delay_minutes == 4
    assert canceled.canceled is True
    assert canceled.boardable is False


async def test_coordinator_marks_failed_update_on_connection_error(
    hass, mock_config_entry
) -> None:
    """Test unavailable behavior when TriMet cannot be reached."""
    api = StubApi(error=TriMetConnectionError("offline"))
    coordinator = TriMetDataUpdateCoordinator(hass, api, mock_config_entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_coordinator_raises_auth_failed(hass) -> None:
    """Test auth failures bubble up correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="TriMet",
        data={
            CONF_API_KEY: "bad-key",
            CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
        },
        options={CONF_MONITORS: []},
    )
    api = StubApi(error=TriMetAuthenticationError("bad key"))
    coordinator = TriMetDataUpdateCoordinator(hass, api, entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_update_failed(hass, mock_config_entry) -> None:
    """Test response and connection errors become UpdateFailed."""
    api = StubApi(error=TriMetConnectionError("offline"))
    coordinator = TriMetDataUpdateCoordinator(hass, api, mock_config_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_excludes_canceled_arrivals_from_matching_and_catchable_logic(
    hass, sample_api_response, mock_config_entry
) -> None:
    """Test canceled arrivals do not drive the monitor snapshot."""
    query_time = sample_api_response["resultSet"]["queryTime"]
    sample_api_response["resultSet"]["arrival"] = [
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 4 * 60_000,
            "status": "canceled",
            "reason": "Operator unavailable",
        },
        {
            "locid": 1234,
            "route": 90,
            "fullSign": "Hillsboro",
            "dir": "Southbound",
            "routeColor": "0065BD",
            "scheduled": query_time + 9 * 60_000,
            "estimated": query_time + 9 * 60_000,
            "status": "estimated",
        },
    ]
    mock_config_entry.options[CONF_MONITORS][0]["approach_time_minutes"] = 5
    mock_config_entry.options[CONF_MONITORS][0][
        "sensor_mode"
    ] = SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL
    api = StubApi(feed=parse_arrivals_response(sample_api_response))
    coordinator = TriMetDataUpdateCoordinator(hass, api, mock_config_entry)

    await coordinator.async_refresh()

    snapshot = coordinator.get_monitor_snapshot("monitor_blue")
    assert snapshot is not None
    assert len(snapshot.matching_arrivals) == 1
    assert snapshot.next_arrival is not None
    assert snapshot.next_arrival.status == "estimated"
    assert snapshot.next_arrival.minutes_until(snapshot.reference_time) == 9
    assert snapshot.next_catchable_arrival is not None
    assert snapshot.next_catchable_arrival.minutes_until(snapshot.reference_time) == 9


def test_monitor_snapshot_summary_formats_canceled_arrivals() -> None:
    """Test canceled summaries remain readable if exposed in the future."""
    reference_time = datetime(2024, 4, 22, 12, 0, tzinfo=UTC)
    arrival = Arrival(
        stop_id="1234",
        route_id="193",
        route_name="NS Line Streetcar",
        destination="NW 23rd Ave",
        direction="Westbound",
        vehicle_type=VehicleType.STREETCAR,
        scheduled_at=reference_time,
        estimated_at=None,
        status="canceled",
        reason="Operator unavailable",
        live=False,
        delay_minutes=None,
        delayed=False,
        canceled=True,
        uncertain=False,
        drop_off_only=False,
        route_color="#72A130",
    )
    snapshot = MonitorSnapshot(
        monitor=MonitorConfig(
            monitor_id="monitor_ns",
            friendly_name="Streetcar",
            stop_id="1234",
            allowed_routes=(),
            allowed_directions=(),
            allowed_vehicle_types=(),
        ),
        stop=StopInfo(stop_id="1234", name="NW 21st & Northrup"),
        matching_arrivals=(arrival,),
        reference_time=reference_time,
        last_updated=reference_time,
    )

    assert snapshot.summary == "NS to NW 23rd Ave canceled"
