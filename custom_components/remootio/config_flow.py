"""Config flow for Remootio integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from aioremootio import (
    ConnectionOptions,
    RemootioClientAuthenticationError,
    RemootioClientConnectionEstablishmentError,
)
import voluptuous as vol

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import ConfigFlow
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

# Validation patterns
HOST_PATTERN = r"^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*(:\d{1,5})?$"
API_KEY_PATTERN = r"^[A-F0-9]{64}$"

class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate host format
                if not re.match(HOST_PATTERN, user_input[CONF_HOST]):
                    errors[CONF_HOST] = "host_invalid"
                    raise InvalidHost

                # Validate API keys format
                api_secret_key = user_input[CONF_API_SECRET_KEY].upper()
                api_auth_key = user_input[CONF_API_AUTH_KEY].upper()

                if not re.match(API_KEY_PATTERN, api_secret_key):
                    errors[CONF_API_SECRET_KEY] = "secret__api_secret_key_invalid"
                    raise InvalidApiSecretKey

                if not re.match(API_KEY_PATTERN, api_auth_key):
                    errors[CONF_API_AUTH_KEY] = "secret__api_auth_key_invalid"
                    raise InvalidApiAuthKey

                connection_options = ConnectionOptions(
                    user_input[CONF_HOST],
                    api_secret_key,
                    api_auth_key,
                )

                device_serial_number = await get_serial_number(
                    self.hass, connection_options, _LOGGER
                )

                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_API_SECRET_KEY: api_secret_key,
                    CONF_API_AUTH_KEY: api_auth_key,
                    CONF_DEVICE_CLASS: user_input[CONF_DEVICE_CLASS],
                    CONF_SERIAL_NUMBER: device_serial_number,
                }

                await self.async_set_unique_id(device_serial_number)
                self._abort_if_unique_id_configured(data)

                return self.async_create_entry(
                    title=f"Remootio Device ({user_input[CONF_HOST]})",
                    data=data,
                )

            except RemootioClientConnectionEstablishmentError:
                errors["base"] = "cannot_connect"
            except RemootioClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except UnsupportedRemootioDeviceError:
                return self.async_abort(reason="unsupported_device")
            except (InvalidHost, InvalidApiSecretKey, InvalidApiAuthKey):
                pass  # Errors already set
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_SECRET_KEY): str,
                    vol.Required(CONF_API_AUTH_KEY): str,
                    vol.Required(
                        CONF_DEVICE_CLASS,
                        default=CoverDeviceClass.GARAGE
                    ): vol.In([CoverDeviceClass.GARAGE, CoverDeviceClass.GATE]),
                }
            ),
            errors=errors,
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate invalid host."""


class InvalidApiSecretKey(HomeAssistantError):
    """Error to indicate invalid API secret key."""


class InvalidApiAuthKey(HomeAssistantError):
    """Error to indicate invalid API auth key."""