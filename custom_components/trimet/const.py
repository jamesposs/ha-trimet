"""Constants for the TriMet integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "trimet"
NAME = "Portland TriMet Arrivals"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_POLL_INTERVAL_SECONDS = "poll_interval_seconds"
CONF_MONITORS = "monitors"
CONF_MONITOR_ID = "monitor_id"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_STOP_ID = "stop_id"
CONF_ALLOWED_ROUTES = "allowed_routes"
CONF_ALLOWED_DIRECTIONS = "allowed_directions"
CONF_ALLOWED_VEHICLE_TYPES = "allowed_vehicle_types"
CONF_DUE_SOON_MINUTES = "due_soon_minutes"
CONF_APPROACH_TIME_MINUTES = "approach_time_minutes"
CONF_SENSOR_MODE = "sensor_mode"
CONF_MAX_ARRIVALS = "max_arrivals"

DEFAULT_POLL_INTERVAL_SECONDS = 30
MIN_POLL_INTERVAL_SECONDS = 15
MAX_POLL_INTERVAL_SECONDS = 300

DEFAULT_DUE_SOON_MINUTES = 10
DEFAULT_APPROACH_TIME_MINUTES = 0
DEFAULT_MAX_ARRIVALS = 3
MIN_MAX_ARRIVALS = 1
MAX_MAX_ARRIVALS = 10

DEFAULT_FETCH_WINDOW_MINUTES = 60
DEFAULT_FETCH_LIMIT = 6
MAX_LOCATIONS_PER_REQUEST = 128
REQUEST_TIMEOUT_SECONDS = 10

VEHICLE_TYPE_BUS = "bus"
VEHICLE_TYPE_MAX = "max"
VEHICLE_TYPE_STREETCAR = "streetcar"
VEHICLE_TYPE_WES = "wes"
VEHICLE_TYPE_OTHER = "other"

SUPPORTED_VEHICLE_TYPES: tuple[str, ...] = (
    VEHICLE_TYPE_BUS,
    VEHICLE_TYPE_MAX,
    VEHICLE_TYPE_STREETCAR,
    VEHICLE_TYPE_WES,
)

VALIDATION_STOP_ID = "6849"

ATTR_MATCHING_ARRIVALS = "matching_arrivals"
ATTR_CATCHABLE_ARRIVALS = "catchable_arrivals"
ATTR_SKIPPED_ARRIVALS = "skipped_arrivals"

SENSOR_MODE_NEXT_ARRIVAL = "next_arrival"
SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL = "next_catchable_arrival"
SUPPORTED_SENSOR_MODES: tuple[str, ...] = (
    SENSOR_MODE_NEXT_ARRIVAL,
    SENSOR_MODE_NEXT_CATCHABLE_ARRIVAL,
)

OPTIONS_MENU_GLOBAL = "global"
OPTIONS_MENU_MONITOR_ADD = "monitor_add"
OPTIONS_MENU_MONITOR_EDIT_SELECT = "monitor_edit_select"
OPTIONS_MENU_MONITOR_DELETE_SELECT = "monitor_delete_select"

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_INVALID_STOP_ID = "invalid_stop_id"
ERROR_INVALID_VEHICLE_TYPE = "invalid_vehicle_type"
ERROR_NO_MONITORS = "no_monitors"
ERROR_UNKNOWN = "unknown"
