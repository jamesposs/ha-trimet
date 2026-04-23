"""Shared fixtures for TriMet tests."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except ImportError:  # pragma: no cover
    from tests.common import MockConfigEntry

from custom_components.trimet.const import (
    CONF_APPROACH_TIME_MINUTES,
    CONF_ALLOWED_DIRECTIONS,
    CONF_ALLOWED_ROUTES,
    CONF_ALLOWED_VEHICLE_TYPES,
    CONF_DUE_SOON_MINUTES,
    CONF_FRIENDLY_NAME,
    CONF_MAX_ARRIVALS,
    CONF_MONITOR_ID,
    CONF_MONITORS,
    CONF_POLL_INTERVAL_SECONDS,
    CONF_SENSOR_MODE,
    CONF_STOP_ID,
    DEFAULT_APPROACH_TIME_MINUTES,
    DEFAULT_DUE_SOON_MINUTES,
    DEFAULT_MAX_ARRIVALS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    NAME,
    SENSOR_MODE_NEXT_ARRIVAL,
)
from custom_components.trimet.models import parse_arrivals_response

QUERY_TIME_MS = 1713787200000
SAMPLE_API_RESPONSE = {
    "resultSet": {
        "queryTime": QUERY_TIME_MS,
        "location": [
            {
                "locid": 1234,
                "desc": "Hollywood/NE 42nd Ave TC MAX Station",
                "lat": 45.5405,
                "lng": -122.6194,
            },
            {
                "locid": 5678,
                "desc": "SW 5th & Oak",
                "lat": 45.5203,
                "lng": -122.6764,
            },
        ],
        "route": [
            {
                "route": 90,
                "desc": "Blue",
                "type": "R",
                "routeSubType": "Light Rail",
            },
            {
                "route": 33,
                "desc": "McLoughlin/King Rd",
                "type": "B",
                "routeSubType": "Bus",
            },
            {
                "route": 193,
                "desc": "NS Line Streetcar",
                "type": "R",
                "routeSubType": "Streetcar",
            },
        ],
        "arrival": [
            {
                "locid": 1234,
                "route": 90,
                "fullSign": "Hillsboro",
                "dir": "Southbound",
                "scheduled": QUERY_TIME_MS + 5 * 60_000,
                "estimated": QUERY_TIME_MS + 4 * 60_000,
                "status": "estimated",
                "vehicleID": 9001,
            },
            {
                "locid": 1234,
                "route": 90,
                "fullSign": "Hillsboro",
                "dir": "Southbound",
                "scheduled": QUERY_TIME_MS + 11 * 60_000,
                "estimated": QUERY_TIME_MS + 9 * 60_000,
                "status": "estimated",
                "vehicleID": 9002,
            },
            {
                "locid": 1234,
                "route": 33,
                "fullSign": "Downtown Portland",
                "dir": "Northbound",
                "scheduled": QUERY_TIME_MS + 6 * 60_000,
                "estimated": QUERY_TIME_MS + 6 * 60_000,
                "status": "estimated",
                "vehicleID": 3301,
            },
            {
                "locid": 1234,
                "route": 193,
                "fullSign": "NW 23rd",
                "dir": "Westbound",
                "scheduled": QUERY_TIME_MS + 3 * 60_000,
                "estimated": QUERY_TIME_MS + 3 * 60_000,
                "status": "estimated",
                "streetCar": True,
                "vehicleID": 1931,
            },
            {
                "locid": 5678,
                "route": 33,
                "fullSign": "Milwaukie",
                "dir": "Southbound",
                "scheduled": QUERY_TIME_MS + 8 * 60_000,
                "estimated": QUERY_TIME_MS + 7 * 60_000,
                "status": "estimated",
                "vehicleID": 3302,
            },
        ],
    }
}


def make_monitor_dict(
    *,
    monitor_id: str = "monitor_blue",
    name: str = "Hollywood Blue",
    stop_id: str = "1234",
    routes: list[str] | None = None,
    directions: list[str] | None = None,
    vehicle_types: list[str] | None = None,
    due_soon_minutes: int = DEFAULT_DUE_SOON_MINUTES,
    approach_time_minutes: int = DEFAULT_APPROACH_TIME_MINUTES,
    sensor_mode: str = SENSOR_MODE_NEXT_ARRIVAL,
    max_arrivals: int = DEFAULT_MAX_ARRIVALS,
) -> dict[str, object]:
    """Create a stored monitor dict for tests."""
    return {
        CONF_MONITOR_ID: monitor_id,
        CONF_FRIENDLY_NAME: name,
        CONF_STOP_ID: stop_id,
        CONF_ALLOWED_ROUTES: routes or ["90"],
        CONF_ALLOWED_DIRECTIONS: directions or ["southbound"],
        CONF_ALLOWED_VEHICLE_TYPES: vehicle_types or ["max"],
        CONF_DUE_SOON_MINUTES: due_soon_minutes,
        CONF_APPROACH_TIME_MINUTES: approach_time_minutes,
        CONF_SENSOR_MODE: sensor_mode,
        CONF_MAX_ARRIVALS: max_arrivals,
    }


@pytest.fixture
def sample_api_response() -> dict:
    """Return a fresh copy of a sample TriMet response."""
    return deepcopy(SAMPLE_API_RESPONSE)


@pytest.fixture
def sample_feed(sample_api_response):
    """Return normalized sample feed data."""
    return parse_arrivals_response(sample_api_response)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a default config entry with one MAX monitor."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={
            CONF_API_KEY: "test-api-key",
            CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
        },
        options={
            CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
            CONF_MONITORS: [make_monitor_dict()],
        },
    )


@pytest.fixture
def mock_fetch_arrivals(sample_feed):
    """Patch API fetches to return the sample feed."""
    with patch(
        "custom_components.trimet.api.TriMetApiClient.async_fetch_arrivals",
        new=AsyncMock(return_value=sample_feed),
    ) as mock_fetch:
        yield mock_fetch
