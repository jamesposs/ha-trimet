"""TriMet API client."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    DEFAULT_FETCH_LIMIT,
    DEFAULT_FETCH_WINDOW_MINUTES,
    LOGGER,
    MAX_LOCATIONS_PER_REQUEST,
    REQUEST_TIMEOUT_SECONDS,
    VALIDATION_STOP_ID,
)
from .models import TriMetFeed, merge_feeds, parse_arrivals_response

ARRIVALS_ENDPOINT = "https://developer.trimet.org/ws/v2/arrivals"


class TriMetApiError(Exception):
    """Base class for TriMet API errors."""


class TriMetAuthenticationError(TriMetApiError):
    """Raised when the API key is rejected."""


class TriMetConnectionError(TriMetApiError):
    """Raised on network failures."""


class TriMetResponseError(TriMetApiError):
    """Raised when the API returns malformed data."""


class TriMetApiClient:
    """Small async client for the TriMet arrivals API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key

    async def async_validate_api_key(self) -> None:
        """Validate the configured API key with a lightweight arrivals request."""
        await self._async_fetch_chunk((VALIDATION_STOP_ID,))

    async def async_fetch_arrivals(self, stop_ids: set[str]) -> TriMetFeed:
        """Fetch arrivals for all monitored stops."""
        if not stop_ids:
            return TriMetFeed.empty(datetime.now(UTC))

        sorted_stop_ids = sorted(stop_ids)
        chunks = [
            tuple(sorted_stop_ids[index : index + MAX_LOCATIONS_PER_REQUEST])
            for index in range(0, len(sorted_stop_ids), MAX_LOCATIONS_PER_REQUEST)
        ]

        LOGGER.debug(
            "Fetching TriMet arrivals for %s stops in %s request chunk(s)",
            len(stop_ids),
            len(chunks),
        )

        feeds = await asyncio.gather(
            *(self._async_fetch_chunk(chunk) for chunk in chunks)
        )
        return merge_feeds(feeds)

    async def _async_fetch_chunk(self, stop_ids: Sequence[str]) -> TriMetFeed:
        """Fetch one arrivals request chunk."""
        params = {
            "appID": self._api_key,
            "locIDs": ",".join(stop_ids),
            "json": "true",
            "minutes": str(DEFAULT_FETCH_WINDOW_MINUTES),
            "arrivals": str(DEFAULT_FETCH_LIMIT),
        }

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._session.get(ARRIVALS_ENDPOINT, params=params)
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise TriMetConnectionError("Timed out contacting the TriMet API") from err
        except ClientResponseError as err:
            if err.status in {401, 403}:
                raise TriMetAuthenticationError("TriMet rejected the API key") from err
            raise TriMetConnectionError(
                f"Unexpected HTTP status from TriMet: {err.status}"
            ) from err
        except ClientError as err:
            raise TriMetConnectionError("Failed to connect to the TriMet API") from err
        except ValueError as err:
            raise TriMetResponseError("TriMet returned invalid JSON") from err

        result = payload.get("resultSet") if isinstance(payload, dict) else None
        error_message = _extract_error_message(result)
        if error_message:
            if _looks_like_auth_error(error_message):
                raise TriMetAuthenticationError(error_message)
            raise TriMetResponseError(error_message)

        try:
            return parse_arrivals_response(payload)
        except ValueError as err:
            raise TriMetResponseError("TriMet returned an unexpected response shape") from err


def _extract_error_message(result: Any) -> str | None:
    """Extract a readable TriMet error message."""
    if not isinstance(result, dict):
        return None

    error = result.get("errorMessage")
    if error is None:
        return None
    if isinstance(error, dict):
        message = error.get("content") or error.get("message")
        return str(message).strip() if message else str(error)
    if isinstance(error, list):
        return "; ".join(str(item) for item in error if item)

    message = str(error).strip()
    return message or None


def _looks_like_auth_error(message: str) -> bool:
    """Return whether an API error message looks auth-related."""
    normalized = message.lower()
    return any(
        marker in normalized
        for marker in ("appid", "api key", "application id", "invalid key", "unauthorized")
    )
