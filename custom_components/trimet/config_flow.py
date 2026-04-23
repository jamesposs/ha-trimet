"""Config flow for TriMet."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TriMetApiClient,
    TriMetAuthenticationError,
    TriMetConnectionError,
    TriMetResponseError,
)
from .const import (
    CONF_ALLOWED_DIRECTIONS,
    CONF_ALLOWED_ROUTES,
    CONF_ALLOWED_VEHICLE_TYPES,
    CONF_DUE_SOON_MINUTES,
    CONF_FRIENDLY_NAME,
    CONF_MAX_ARRIVALS,
    CONF_MONITOR_ID,
    CONF_MONITORS,
    CONF_POLL_INTERVAL_SECONDS,
    CONF_STOP_ID,
    DEFAULT_DUE_SOON_MINUTES,
    DEFAULT_MAX_ARRIVALS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    ERROR_INVALID_RESPONSE,
    ERROR_INVALID_STOP_ID,
    ERROR_INVALID_VEHICLE_TYPE,
    ERROR_NO_MONITORS,
    ERROR_UNKNOWN,
    MAX_MAX_ARRIVALS,
    MAX_POLL_INTERVAL_SECONDS,
    MIN_MAX_ARRIVALS,
    MIN_POLL_INTERVAL_SECONDS,
    OPTIONS_MENU_GLOBAL,
    OPTIONS_MENU_MONITOR_ADD,
    OPTIONS_MENU_MONITOR_DELETE_SELECT,
    OPTIONS_MENU_MONITOR_EDIT_SELECT,
    SUPPORTED_VEHICLE_TYPES,
)
from .models import MonitorConfig, normalize_vehicle_types


class TriMetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TriMet."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            poll_interval = int(user_input[CONF_POLL_INTERVAL_SECONDS])
            unique_id = _unique_id_from_api_key(api_key)

            try:
                await _async_validate_api_key(self.hass, api_key)
            except TriMetAuthenticationError:
                errors["base"] = ERROR_INVALID_AUTH
            except TriMetConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except TriMetResponseError:
                errors["base"] = ERROR_INVALID_RESPONSE
            except Exception:  # pragma: no cover - defensive guard
                errors["base"] = ERROR_UNKNOWN
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="TriMet",
                    data={
                        CONF_API_KEY: api_key,
                        CONF_POLL_INTERVAL_SECONDS: poll_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(
                        CONF_POLL_INTERVAL_SECONDS,
                        default=DEFAULT_POLL_INTERVAL_SECONDS,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_POLL_INTERVAL_SECONDS,
                            max=MAX_POLL_INTERVAL_SECONDS,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        del config_entry
        return TriMetOptionsFlowHandler()


class TriMetOptionsFlowHandler(config_entries.OptionsFlow):
    """Manage TriMet monitors and editable global options."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._selected_monitor_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options menu."""
        del user_input

        menu_options = [OPTIONS_MENU_GLOBAL, OPTIONS_MENU_MONITOR_ADD]
        if self._monitors:
            menu_options.extend(
                [OPTIONS_MENU_MONITOR_EDIT_SELECT, OPTIONS_MENU_MONITOR_DELETE_SELECT]
            )

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_global(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit global polling options."""
        if user_input is not None:
            updated = dict(self.config_entry.options)
            updated[CONF_MONITORS] = [monitor.to_dict() for monitor in self._monitors]
            updated[CONF_POLL_INTERVAL_SECONDS] = int(user_input[CONF_POLL_INTERVAL_SECONDS])
            return self.async_create_entry(title="", data=updated)

        current_poll_interval = int(
            self.config_entry.options.get(
                CONF_POLL_INTERVAL_SECONDS,
                self.config_entry.data.get(
                    CONF_POLL_INTERVAL_SECONDS, DEFAULT_POLL_INTERVAL_SECONDS
                ),
            )
        )
        return self.async_show_form(
            step_id="global",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL_SECONDS, default=current_poll_interval
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_POLL_INTERVAL_SECONDS,
                            max=MAX_POLL_INTERVAL_SECONDS,
                        ),
                    )
                }
            ),
        )

    async def async_step_monitor_add(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a monitor."""
        return await self._async_step_monitor_form(user_input=user_input, monitor=None)

    async def async_step_monitor_edit_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a monitor to edit."""
        if not self._monitors:
            return self.async_abort(reason=ERROR_NO_MONITORS)

        if user_input is not None:
            self._selected_monitor_id = user_input[CONF_MONITOR_ID]
            return await self.async_step_monitor_edit()

        return self.async_show_form(
            step_id="monitor_edit_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_MONITOR_ID): vol.In(self._monitor_labels)}
            ),
        )

    async def async_step_monitor_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit an existing monitor."""
        monitor = self._monitor_by_id(self._selected_monitor_id)
        if monitor is None:
            return self.async_abort(reason=ERROR_NO_MONITORS)

        return await self._async_step_monitor_form(user_input=user_input, monitor=monitor)

    async def async_step_monitor_delete_select(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Delete a monitor."""
        if not self._monitors:
            return self.async_abort(reason=ERROR_NO_MONITORS)

        if user_input is not None:
            selected_id = user_input[CONF_MONITOR_ID]
            updated_monitors = [
                monitor.to_dict()
                for monitor in self._monitors
                if monitor.monitor_id != selected_id
            ]
            updated_options = dict(self.config_entry.options)
            updated_options[CONF_MONITORS] = updated_monitors
            if CONF_POLL_INTERVAL_SECONDS not in updated_options:
                updated_options[CONF_POLL_INTERVAL_SECONDS] = int(
                    self.config_entry.data.get(
                        CONF_POLL_INTERVAL_SECONDS, DEFAULT_POLL_INTERVAL_SECONDS
                    )
                )
            return self.async_create_entry(title="", data=updated_options)

        return self.async_show_form(
            step_id="monitor_delete_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_MONITOR_ID): vol.In(self._monitor_labels)}
            ),
        )

    async def _async_step_monitor_form(
        self,
        *,
        user_input: dict[str, Any] | None,
        monitor: MonitorConfig | None,
    ) -> config_entries.ConfigFlowResult:
        """Shared add/edit monitor form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                parsed_monitor = _monitor_from_form(
                    user_input=user_input,
                    existing_monitor=monitor,
                )
            except InvalidStopIdError:
                errors[CONF_STOP_ID] = ERROR_INVALID_STOP_ID
            except InvalidVehicleTypeError:
                errors[CONF_ALLOWED_VEHICLE_TYPES] = ERROR_INVALID_VEHICLE_TYPE
            else:
                monitors = [entry_monitor for entry_monitor in self._monitors if entry_monitor.monitor_id != parsed_monitor.monitor_id]
                monitors.append(parsed_monitor)
                monitors.sort(key=lambda item: item.friendly_name.lower())

                updated_options = dict(self.config_entry.options)
                updated_options[CONF_MONITORS] = [
                    item.to_dict() for item in monitors
                ]
                if CONF_POLL_INTERVAL_SECONDS not in updated_options:
                    updated_options[CONF_POLL_INTERVAL_SECONDS] = int(
                        self.config_entry.data.get(
                            CONF_POLL_INTERVAL_SECONDS, DEFAULT_POLL_INTERVAL_SECONDS
                        )
                    )
                return self.async_create_entry(title="", data=updated_options)

        monitor = monitor or MonitorConfig(
            monitor_id="",
            friendly_name="",
            stop_id="",
            allowed_routes=(),
            allowed_directions=(),
            allowed_vehicle_types=(),
            due_soon_minutes=DEFAULT_DUE_SOON_MINUTES,
            max_arrivals=DEFAULT_MAX_ARRIVALS,
        )

        return self.async_show_form(
            step_id="monitor_edit" if monitor.monitor_id else "monitor_add",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FRIENDLY_NAME, default=monitor.friendly_name
                    ): str,
                    vol.Required(CONF_STOP_ID, default=monitor.stop_id): str,
                    vol.Optional(
                        CONF_ALLOWED_ROUTES,
                        default=", ".join(monitor.allowed_routes),
                    ): str,
                    vol.Optional(
                        CONF_ALLOWED_DIRECTIONS,
                        default=", ".join(monitor.allowed_directions),
                    ): str,
                    vol.Optional(
                        CONF_ALLOWED_VEHICLE_TYPES,
                        default=", ".join(monitor.allowed_vehicle_types),
                    ): str,
                    vol.Required(
                        CONF_DUE_SOON_MINUTES,
                        default=monitor.due_soon_minutes,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                    vol.Required(
                        CONF_MAX_ARRIVALS,
                        default=monitor.max_arrivals,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_MAX_ARRIVALS, max=MAX_MAX_ARRIVALS),
                    ),
                }
            ),
            errors=errors,
        )

    @property
    def _monitors(self) -> list[MonitorConfig]:
        """Return all monitors from config entry options."""
        return [
            MonitorConfig.from_dict(item)
            for item in self.config_entry.options.get(CONF_MONITORS, [])
            if isinstance(item, Mapping)
        ]

    @property
    def _monitor_labels(self) -> dict[str, str]:
        """Build labels for monitor selection forms."""
        return {
            monitor.monitor_id: f"{monitor.friendly_name} ({monitor.stop_id})"
            for monitor in self._monitors
        }

    def _monitor_by_id(self, monitor_id: str | None) -> MonitorConfig | None:
        """Return the monitor matching an ID."""
        if monitor_id is None:
            return None
        for monitor in self._monitors:
            if monitor.monitor_id == monitor_id:
                return monitor
        return None


async def _async_validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate the TriMet API key."""
    client = TriMetApiClient(
        session=async_get_clientsession(hass),
        api_key=api_key,
    )
    await client.async_validate_api_key()


def _unique_id_from_api_key(api_key: str) -> str:
    """Return a stable, non-secret unique ID from the API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _monitor_from_form(
    *,
    user_input: Mapping[str, Any],
    existing_monitor: MonitorConfig | None,
) -> MonitorConfig:
    """Build and validate a monitor from form data."""
    stop_id = str(user_input[CONF_STOP_ID]).strip()
    if not stop_id.isdigit():
        raise InvalidStopIdError

    vehicle_types = normalize_vehicle_types(user_input.get(CONF_ALLOWED_VEHICLE_TYPES))
    raw_vehicle_types = str(user_input.get(CONF_ALLOWED_VEHICLE_TYPES, "")).strip()
    if raw_vehicle_types and not vehicle_types and raw_vehicle_types:
        raise InvalidVehicleTypeError
    requested_vehicle_types = {
        item.strip().lower() for item in raw_vehicle_types.split(",") if item.strip()
    }
    if requested_vehicle_types - set(SUPPORTED_VEHICLE_TYPES):
        raise InvalidVehicleTypeError

    return MonitorConfig(
        monitor_id=existing_monitor.monitor_id if existing_monitor else uuid4().hex,
        friendly_name=str(user_input[CONF_FRIENDLY_NAME]).strip(),
        stop_id=stop_id,
        allowed_routes=tuple(
            item.strip().upper()
            for item in str(user_input.get(CONF_ALLOWED_ROUTES, "")).split(",")
            if item.strip()
        ),
        allowed_directions=tuple(
            item.strip().lower()
            for item in str(user_input.get(CONF_ALLOWED_DIRECTIONS, "")).split(",")
            if item.strip()
        ),
        allowed_vehicle_types=vehicle_types,
        due_soon_minutes=int(user_input[CONF_DUE_SOON_MINUTES]),
        max_arrivals=int(user_input[CONF_MAX_ARRIVALS]),
    )


class InvalidStopIdError(ValueError):
    """Raised when a stop ID cannot be parsed."""


class InvalidVehicleTypeError(ValueError):
    """Raised when vehicle types are invalid."""
