"""Config flow for Remootio integration."""
from __future__ import annotations
import logging
import re
from typing import Any
import voluptuous as vol
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from .const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from .exceptions import UnsupportedRemootioDeviceError, UnsupportedRemootioApiVersionError
from .utils import get_serial_number

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult  # type: ignore[assignment]

_LOGGER = logging.getLogger(__name__)

HOST_PATTERN = r"^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*(\:\d{1,5})?$"
API_KEY_PATTERN = r"^[A-F0-9]{64}$"


class RemootioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                if not re.match(HOST_PATTERN, user_input[CONF_HOST]):
                    errors[CONF_HOST] = "host_invalid"
                    raise InvalidHost
                api_secret_key = user_input[CONF_API_SECRET_KEY].upper()
                api_auth_key = user_input[CONF_API_AUTH_KEY].upper()
                if not re.match(API_KEY_PATTERN, api_secret_key):
                    errors[CONF_API_SECRET_KEY] = "secret__api_secret_key_invalid"
                    raise InvalidApiSecretKey
                if not re.match(API_KEY_PATTERN, api_auth_key):
                    errors[CONF_API_AUTH_KEY] = "secret__api_auth_key_invalid"
                    raise InvalidApiAuthKey

                # aioremootio imported here so this module loads before HA installs requirements
                from aioremootio import ConnectionOptions  # noqa: PLC0415

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
            except UnsupportedRemootioDeviceError:
                return self.async_abort(reason="unsupported_device")
            except (UnsupportedRemootioApiVersionError, ConfigEntryNotReady):
                errors["base"] = "cannot_connect"
            except (InvalidHost, InvalidApiSecretKey, InvalidApiAuthKey):
                pass
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    def _build_schema(
        self, user_input: dict[str, Any] | None = None
    ) -> vol.Schema:
        """Build the data schema, pre-filling with previous user input."""
        ui = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=ui.get(CONF_HOST, "")): str,
                vol.Required(CONF_API_SECRET_KEY, default=ui.get(CONF_API_SECRET_KEY, "")): str,
                vol.Required(CONF_API_AUTH_KEY, default=ui.get(CONF_API_AUTH_KEY, "")): str,
                vol.Required(
                    CONF_DEVICE_CLASS,
                    default=ui.get(CONF_DEVICE_CLASS, CoverDeviceClass.GARAGE),
                ): vol.In([CoverDeviceClass.GARAGE, CoverDeviceClass.GATE]),
            }
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate invalid host."""


class InvalidApiSecretKey(HomeAssistantError):
    """Error to indicate invalid API secret key."""


class InvalidApiAuthKey(HomeAssistantError):
    """Error to indicate invalid API auth key."""
