"""Utility methods for the Remootio integration."""
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING, Optional
from aiohttp import ClientError
from homeassistant import core
from homeassistant.helpers import aiohttp_client
from homeassistant.exceptions import ConfigEntryNotReady
from .const import EXPECTED_MINIMUM_API_VERSION
from .exceptions import (
    UnsupportedRemootioApiVersionError,
    UnsupportedRemootioDeviceError,
)

if TYPE_CHECKING:
    from aioremootio import ConnectionOptions, RemootioClient

_LOGGER = logging.getLogger(__name__)


def _check_api_version(remootio_client: RemootioClient) -> None:
    """Raise if the device API version is below the minimum required."""
    api_version: int = remootio_client.api_version
    _LOGGER.debug("Device API version: %s", api_version)
    if api_version < EXPECTED_MINIMUM_API_VERSION:
        raise UnsupportedRemootioApiVersionError(
            f"API version {api_version} is not supported. "
            f"Minimum required: {EXPECTED_MINIMUM_API_VERSION}"
        )


def _check_sensor_installed(
    remootio_client: RemootioClient, raise_error: bool = True
) -> None:
    """Raise (or log) if no sensor is installed on the device."""
    from aioremootio.enums import State  # noqa: PLC0415

    if remootio_client.state == State.NO_SENSOR_INSTALLED:
        if raise_error:
            raise UnsupportedRemootioDeviceError("Device has no sensor installed")
        _LOGGER.error(
            "Remootio device has no sensor installed. Host: %s",
            remootio_client.host,
        )


async def get_serial_number(
    hass: core.HomeAssistant,
    connection_options: ConnectionOptions,
    logger: logging.Logger,
) -> str:
    """Connect to a Remootio device and return its serial number.

    aioremootio manages its own internal 30 s connection timeout, so no outer
    timeout wrapper is needed here — it would create nested asyncio.timeout()
    conflicts on Python 3.11+/3.14 that surface as CancelledError.
    """
    from aioremootio import LoggerConfiguration, RemootioClient  # noqa: PLC0415
    from aioremootio.errors import RemootioClientError  # noqa: PLC0415

    remootio_client: Optional[RemootioClient] = None
    try:
        session = aiohttp_client.async_get_clientsession(hass)
        remootio_client = await RemootioClient(
            connection_options,
            session,
            LoggerConfiguration(logger=logger),
        )
        _LOGGER.debug("Connected. State: %s", remootio_client.state)
        _check_sensor_installed(remootio_client)
        _check_api_version(remootio_client)
        serial = remootio_client.serial_number
        _LOGGER.debug("Serial number: %s", serial)
        return serial
    except (UnsupportedRemootioDeviceError, UnsupportedRemootioApiVersionError):
        raise
    except RemootioClientError as err:
        _LOGGER.error("Remootio client error during setup: %s", str(err))
        raise ConfigEntryNotReady(str(err)) from err
    except asyncio.CancelledError as err:
        _LOGGER.error("Connection attempt was cancelled: %s", str(err))
        raise ConfigEntryNotReady("Connection timed out or was cancelled") from err
    except ClientError as err:
        _LOGGER.error("HTTP client error during setup: %s", str(err))
        raise ConfigEntryNotReady(str(err)) from err
    finally:
        if remootio_client is not None:
            await remootio_client.terminate()


async def create_client(
    hass: core.HomeAssistant,
    connection_options: ConnectionOptions,
    logger: logging.Logger,
    expected_serial_number: Optional[str] = None,
) -> RemootioClient:
    """Create and return a connected Remootio client."""
    from aioremootio import LoggerConfiguration, RemootioClient  # noqa: PLC0415
    from aioremootio.errors import RemootioClientError  # noqa: PLC0415

    try:
        session = aiohttp_client.async_get_clientsession(hass)
        client = await RemootioClient(
            connection_options,
            session,
            LoggerConfiguration(logger=logger),
        )
        _LOGGER.debug("Client connected. State: %s", client.state)
        _check_sensor_installed(client, raise_error=False)
        _check_api_version(client)
        if expected_serial_number is not None:
            serial_number: str = client.serial_number
            if expected_serial_number != serial_number:
                raise ConfigEntryNotReady(
                    f"Serial number mismatch. Expected: {expected_serial_number}, "
                    f"Got: {serial_number}"
                )
        return client
    except (UnsupportedRemootioDeviceError, UnsupportedRemootioApiVersionError):
        raise
    except RemootioClientError as err:
        _LOGGER.error("Remootio client error: %s", str(err))
        raise ConfigEntryNotReady(str(err)) from err
    except asyncio.CancelledError as err:
        _LOGGER.error("Connection attempt was cancelled: %s", str(err))
        raise ConfigEntryNotReady("Connection timed out or was cancelled") from err
    except ClientError as err:
        _LOGGER.error("HTTP client error: %s", str(err))
        raise ConfigEntryNotReady(str(err)) from err
