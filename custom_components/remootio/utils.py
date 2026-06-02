"""Utility methods for the Remootio integration."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional
from aioremootio import ConnectionOptions, LoggerConfiguration, RemootioClient
from aioremootio.enums import State
from aiohttp import ClientError, ClientTimeout
from homeassistant import core
from homeassistant.helpers import aiohttp_client
from homeassistant.exceptions import ConfigEntryNotReady
from .const import EXPECTED_MINIMUM_API_VERSION, REMOOTIO_DELAY, REMOOTIO_TIMEOUT
from .exceptions import (
    UnsupportedRemootioApiVersionError,
    UnsupportedRemootioDeviceError,
)

_LOGGER = logging.getLogger(__name__)

async def _wait_for_connected(remootio_client: RemootioClient) -> bool:
    """Wait for the client to connect."""
    try:
        async with asyncio.timeout(REMOOTIO_TIMEOUT):
            while not remootio_client.connected:
                await asyncio.sleep(REMOOTIO_DELAY)
                _LOGGER.debug("Waiting for connection... Current state: %s", remootio_client.state)
            return remootio_client.connected
    except asyncio.TimeoutError:
        _LOGGER.debug("Connection timeout reached")
        return False

async def _check_api_version(remootio_client: RemootioClient) -> None:
    """Check whether the device uses a supported API version."""
    api_version: int = remootio_client.api_version
    _LOGGER.debug("Device API version: %s", api_version)
    if api_version < EXPECTED_MINIMUM_API_VERSION:
        raise UnsupportedRemootioApiVersionError(
            f"API version {api_version} is not supported. Minimum required version is {EXPECTED_MINIMUM_API_VERSION}"
        )

async def _check_sensor_installed(
    remootio_client: RemootioClient, raise_error: bool = True
) -> None:
    """Check whether the device has a sensor installed."""
    if remootio_client.state == State.NO_SENSOR_INSTALLED:
        if raise_error:
            raise UnsupportedRemootioDeviceError(
                "Device has no sensor installed"
            )
        _LOGGER.error(
            "Your Remootio device isn't supported - no sensor installed. Host: %s",
            remootio_client.host,
        )

async def get_serial_number(
    hass: core.HomeAssistant,
    connection_options: ConnectionOptions,
    logger: logging.Logger
) -> str:
    """Connect to a Remootio device and retrieve its serial number."""
    try:
        async with asyncio.timeout(REMOOTIO_TIMEOUT):
            session = aiohttp_client.async_get_clientsession(hass)
            session.timeout = ClientTimeout(total=REMOOTIO_TIMEOUT)
            async with RemootioClient(
                connection_options,
                session,
                LoggerConfiguration(logger=logger),
            ) as remootio_client:
                _LOGGER.debug("Attempting to connect to device")
                if await _wait_for_connected(remootio_client):
                    await _check_sensor_installed(remootio_client)
                    await _check_api_version(remootio_client)
                    serial = remootio_client.serial_number
                    _LOGGER.debug("Successfully connected. Serial number: %s", serial)
                    return serial
                raise ConfigEntryNotReady("Failed to connect to device")
    except (UnsupportedRemootioDeviceError, UnsupportedRemootioApiVersionError):
        raise
    except (asyncio.TimeoutError, ClientError) as err:
        _LOGGER.error("Connection failed: %s", str(err))
        raise ConfigEntryNotReady(f"Connection failed: {str(err)}") from err

async def create_client(
    hass: core.HomeAssistant,
    connection_options: ConnectionOptions,
    logger: logging.Logger,
    expected_serial_number: Optional[str] = None,
) -> RemootioClient:
    """Create a Remootio client."""
    try:
        async with asyncio.timeout(REMOOTIO_TIMEOUT):
            session = aiohttp_client.async_get_clientsession(hass)
            session.timeout = ClientTimeout(total=REMOOTIO_TIMEOUT)
            client = RemootioClient(
                connection_options,
                session,
                LoggerConfiguration(logger=logger),
            )
            _LOGGER.debug("Creating new client connection")
            await client.connect()
            if await _wait_for_connected(client):
                await _check_sensor_installed(client, False)
                await _check_api_version(client)
                if expected_serial_number is not None:
                    serial_number: str = client.serial_number
                    assert expected_serial_number == serial_number, (
                        f"Serial number mismatch. Expected: {expected_serial_number}, "
                        f"Got: {serial_number}"
                    )
                return client
            raise ConfigEntryNotReady("Failed to connect to device")
    except (asyncio.TimeoutError, ClientError) as err:
        _LOGGER.error("Client creation failed: %s", str(err))
        raise ConfigEntryNotReady(f"Connection failed: {str(err)}") from err
