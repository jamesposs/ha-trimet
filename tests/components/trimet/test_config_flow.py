"""Tests for the TriMet config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_API_KEY

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except ImportError:  # pragma: no cover
    from tests.common import MockConfigEntry

from custom_components.trimet.api import TriMetAuthenticationError
from custom_components.trimet.config_flow import (
    TriMetConfigFlow,
    TriMetOptionsFlowHandler,
    _unique_id_from_api_key,
)
from custom_components.trimet.const import (
    CONF_APPROACH_TIME_MINUTES,
    CONF_ALLOWED_DIRECTIONS,
    CONF_ALLOWED_ROUTES,
    CONF_ALLOWED_VEHICLE_TYPES,
    CONF_DUE_SOON_MINUTES,
    CONF_FRIENDLY_NAME,
    CONF_MAX_ARRIVALS,
    CONF_MONITORS,
    CONF_POLL_INTERVAL_SECONDS,
    CONF_SENSOR_MODE,
    CONF_STOP_ID,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    NAME,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
    SENSOR_MODE_NEXT_ARRIVAL,
)
from custom_components.trimet.models import MonitorConfig


async def test_user_flow_success(hass) -> None:
    """Test successful initial setup."""
    with patch(
        "custom_components.trimet.config_flow._async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_API_KEY: "valid-key", CONF_POLL_INTERVAL_SECONDS: 45},
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_API_KEY: "valid-key",
        CONF_POLL_INTERVAL_SECONDS: 45,
    }


async def test_user_flow_invalid_auth(hass) -> None:
    """Test invalid API key handling."""
    with patch(
        "custom_components.trimet.config_flow._async_validate_api_key",
        new=AsyncMock(side_effect=TriMetAuthenticationError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_KEY: "bad-key",
                CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_duplicate_api_key_aborts(hass) -> None:
    """Test duplicate setup prevention."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        unique_id=_unique_id_from_api_key("dupe-key"),
        data={
            CONF_API_KEY: "dupe-key",
            CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trimet.config_flow._async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_KEY: "dupe-key",
                CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_add_monitor(hass, mock_config_entry) -> None:
    """Test adding a monitor from the options flow."""
    mock_config_entry.options = {
        CONF_POLL_INTERVAL_SECONDS: DEFAULT_POLL_INTERVAL_SECONDS,
        CONF_MONITORS: [],
    }
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "monitor_add"},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_FRIENDLY_NAME: "Downtown Bus",
            CONF_STOP_ID: "5678",
            CONF_ALLOWED_ROUTES: "33",
            CONF_ALLOWED_DIRECTIONS: "southbound",
            CONF_ALLOWED_VEHICLE_TYPES: "bus",
            CONF_DUE_SOON_MINUTES: 6,
            CONF_APPROACH_TIME_MINUTES: 4,
            CONF_SENSOR_MODE: SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
            CONF_MAX_ARRIVALS: 2,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(result["data"][CONF_MONITORS]) == 1
    monitor = result["data"][CONF_MONITORS][0]
    assert monitor[CONF_FRIENDLY_NAME] == "Downtown Bus"
    assert monitor[CONF_STOP_ID] == "5678"
    assert monitor[CONF_ALLOWED_VEHICLE_TYPES] == ["bus"]
    assert monitor[CONF_APPROACH_TIME_MINUTES] == 4
    assert monitor[CONF_SENSOR_MODE] == SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL


def test_monitor_config_defaults_new_decision_fields() -> None:
    """Test older monitor payloads pick up new defaults safely."""
    parsed = MonitorConfig.from_dict(
        {
            "monitor_id": "legacy",
            CONF_FRIENDLY_NAME: "Legacy Monitor",
            CONF_STOP_ID: "1234",
            CONF_ALLOWED_ROUTES: ["90"],
            CONF_ALLOWED_DIRECTIONS: ["southbound"],
            CONF_ALLOWED_VEHICLE_TYPES: ["max"],
            CONF_DUE_SOON_MINUTES: 10,
            CONF_MAX_ARRIVALS: 3,
        }
    )

    assert parsed.approach_time_minutes == 0
    assert parsed.sensor_mode == SENSOR_MODE_NEXT_ARRIVAL


def test_async_get_options_flow_uses_modern_constructor(mock_config_entry) -> None:
    """Test options flows are created without config-entry constructor injection."""
    flow = TriMetConfigFlow.async_get_options_flow(mock_config_entry)

    assert isinstance(flow, TriMetOptionsFlowHandler)
