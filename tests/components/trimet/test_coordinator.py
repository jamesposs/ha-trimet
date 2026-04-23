"""Tests for the TriMet coordinator."""

from __future__ import annotations

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
from custom_components.trimet.models import parse_arrivals_response


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
