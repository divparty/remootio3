"""Config flow for Remootio integration."""
from __future__ import annotations

import logging
from typing import Any

from aioremootio import (
    ConnectionOptions,
    RemootioClientAuthenticationError,
    RemootioClientConnectionEstablishmentError,
)
from aioremootio.constants import (
    CONNECTION_OPTION_REGEX_API_AUTH_KEY,
    CONNECTION_OPTION_REGEX_API_SECRET_KEY,
    CONNECTION_OPTION_REGEX_HOST,
)
import voluptuous as vol

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_DATA,
    CONF_SERIAL_NUMBER,
    CONF_TITLE,
    DOMAIN,
)
from .exceptions import UnsupportedRemootioDeviceError
from .utils import get_serial_number

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_SECRET_KEY): str,
        vol.Required(CONF_API_AUTH_KEY): str,
        vol.Required(CONF_DEVICE_CLASS, default=CoverDeviceClass.GARAGE): vol.In(
            [CoverDeviceClass.GARAGE, CoverDeviceClass.GATE]
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        # Validate host format
        if not CONNECTION_OPTION_REGEX_HOST.match(data[CONF_HOST]):
            raise InvalidHost

        # Validate API keys format
        if not CONNECTION_OPTION_REGEX_API_SECRET_KEY.match(data[CONF_API_SECRET_KEY].upper()):
            raise InvalidApiSecretKey

        if not CONNECTION_OPTION_REGEX_API_AUTH_KEY.match(data[CONF_API_AUTH_KEY].upper()):
            raise InvalidApiAuthKey

        connection_options: ConnectionOptions = ConnectionOptions(
            data[CONF_HOST],
            data[CONF_API_SECRET_KEY].upper(),
            data[CONF_API_AUTH_KEY].upper(),
        )

        device_serial_number: str = await get_serial_number(hass, connection_options, _LOGGER)
        
        return {
            CONF_TITLE: f"Remootio Device (Host: {data[CONF_HOST]}, S/N: {device_serial_number})",
            CONF_DATA: {
                CONF_HOST: data[CONF_HOST],
                CONF_API_SECRET_KEY: data[CONF_API_SECRET_KEY].upper(),
                CONF_API_AUTH_KEY: data[CONF_API_AUTH_KEY].upper(),
                CONF_DEVICE_CLASS: data[CONF_DEVICE_CLASS],
                CONF_SERIAL_NUMBER: device_serial_number,
            },
        }

    except RemootioClientConnectionEstablishmentError as err:
        raise CannotConnect from err
    except RemootioClientAuthenticationError as err:
        raise InvalidAuth from err
    except UnsupportedRemootioDeviceError as err:
        raise DeviceNotSupported from err


class RemootioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                validation_result = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidHost:
                errors[CONF_HOST] = "host_invalid"
            except InvalidApiSecretKey:
                errors[CONF_API_SECRET_KEY] = "secret__api_secret_key_invalid"
            except InvalidApiAuthKey:
                errors[CONF_API_AUTH_KEY] = "secret__api_auth_key_invalid"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except DeviceNotSupported:
                return self.async_abort(reason="unsupported_device")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    validation_result[CONF_DATA][CONF_SERIAL_NUMBER]
                )
                self._abort_if_unique_id_configured(validation_result[CONF_DATA])

                return self.async_create_entry(
                    title=validation_result[CONF_TITLE],
                    data=validation_result[CONF_DATA],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(HomeAssistantError):
    """Error to indicate invalid host."""


class InvalidApiSecretKey(HomeAssistantError):
    """Error to indicate invalid API secret key."""


class InvalidApiAuthKey(HomeAssistantError):
    """Error to indicate invalid API auth key."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid authentication."""


class DeviceNotSupported(HomeAssistantError):
    """Error to indicate device not supported."""