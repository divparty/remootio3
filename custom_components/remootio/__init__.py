"""The Remootio integration."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from .const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    REMOOTIO_CLIENT,
)
from .utils import create_client

if TYPE_CHECKING:
    from aioremootio import ConnectionOptions, RemootioClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remootio from a config entry."""
    from aioremootio import ConnectionOptions  # noqa: PLC0415

    _LOGGER.debug("Doing async_setup_entry. entry [%s]", entry.as_dict())
    connection_options: ConnectionOptions = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_API_SECRET_KEY],
        entry.data[CONF_API_AUTH_KEY],
    )
    serial_number: str = entry.data[CONF_SERIAL_NUMBER]
    remootio_client = await create_client(
        hass, connection_options, _LOGGER, serial_number
    )
    hass_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})
    hass_data[REMOOTIO_CLIENT] = remootio_client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
        "Doing async_unload_entry. entry [%s] hass.data[%s][%s] [%s]",
        entry.as_dict(),
        DOMAIN,
        entry.entry_id,
        hass.data.get(DOMAIN, {}).get(entry.entry_id, {}),
    )
    platforms_unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if platforms_unloaded and DOMAIN in hass.data:
        hass_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        remootio_client = hass_data.pop(REMOOTIO_CLIENT, None)
        if remootio_client is not None:
            terminated: bool = await remootio_client.terminate()
            if terminated:
                _LOGGER.debug(
                    "Remootio client successfully terminated. entry [%s]",
                    entry.as_dict(),
                )
    return platforms_unloaded
