"""Utility methods for the Remootio integration."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional
import aiohttp

from aioremootio import ConnectionOptions, LoggerConfiguration, RemootioClient
from aioremootio.enums import State
import async_timeout
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

async def check_device_availability(hass: core.HomeAssistant, host: str, port: int = 8080) -> bool:
    """Check if the device is available on the network."""
    try:
        # First try WebSocket connection
        url = f"ws://{host}:{port}"
        timeout = ClientTimeout(total=5)
        session = aiohttp_client.async_get_clientsession(hass)
        
        try:
            async with session.ws_connect(url, timeout=timeout) as ws:
                await ws.close()
                return True
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.debug("WebSocket connection failed, trying TCP connection")
            
            # Fallback to TCP connection check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                _LOGGER.debug("TCP connection successful")
                return True
            
            _LOGGER.debug("TCP connection failed with error code: %s", result)
            return False
            
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug("Device availability check failed: %s", str(ex))
        return False

async def _wait_for_connected(remootio_client: RemootioClient) -> bool:
    """Wait for the client to connect."""
    try:
        async with async_timeout.timeout(REMOOTIO_TIMEOUT):
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
    host, port = connection_options.host.split(':') if ':' in connection_options.host else (connection_options.host, 8080)
    
    _LOGGER.debug("Checking device availability at %s:%s", host, port)
    if not await check_device_availability(hass, host, int(port)):
        raise ConfigEntryNotReady(
            f"Device not available at {host}:{port}. Please check if:\n"
            "1. The device is powered on\n"
            "2. Connected to your network\n"
            "3. The IP address and port are correct (default port is 8080)\n"
            "4. API access is enabled in the Remootio app\n"
            "5. No firewall is blocking the connection"
        )

    try:
        async with async_timeout.timeout(REMOOTIO_TIMEOUT):
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
        async with async_timeout.timeout(REMOOTIO_TIMEOUT):
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