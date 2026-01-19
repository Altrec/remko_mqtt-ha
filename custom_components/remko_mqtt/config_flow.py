"""Config flow"""

import logging

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components.mqtt import valid_subscribe_topic
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_ID,
    CONF_MQTT_NODE,
    CONF_LANGUAGE,
    CONF_FREQ,
    AVAILABLE_LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


class InvalidPostalCode(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidDomainName(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Component config flow."""

    VERSION = 1

    async def validate_input(self, data):
        """Validate input in step user"""
        return data

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ID, default="remko"): cv.string,
                vol.Required(CONF_MQTT_NODE, default="V04P28"): cv.string,
                vol.Required(CONF_LANGUAGE, default="en"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["en", "de"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(CONF_FREQ, default=100): cv.positive_int,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        # Helper to normalise mqtt prefix
        def _normalize_prefix(prefix: str) -> str:
            if prefix.endswith("/#"):
                prefix = prefix[:-2]
            elif prefix.endswith("/"):
                prefix = prefix[:-1]
            return prefix

        # Build error schema preserving supplied defaults
        error_schema = vol.Schema(
            {
                vol.Required(CONF_ID, default=user_input.get(CONF_ID, "")): cv.string,
                vol.Required(
                    CONF_MQTT_NODE, default=user_input.get(CONF_MQTT_NODE, "")
                ): cv.string,
                vol.Required(
                    CONF_LANGUAGE, default=user_input.get(CONF_LANGUAGE, "en")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["en", "de"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(
                    CONF_FREQ, default=user_input.get(CONF_FREQ, 100)
                ): cv.positive_int,
            }
        )

        # Validate id / unique id
        id_name = user_input.get(CONF_ID, "")
        if not id_name or " " in id_name:
            _LOGGER.debug("Invalid id provided: %s", id_name)
            return self.async_show_form(
                step_id="user", data_schema=error_schema, errors={"base": "invalid_id"}
            )
        # Use the provided id_name as the unique ID for this config entry
        await self.async_set_unique_id(id_name)
        # Abort if an entry with this unique ID already exists
        self._abort_if_unique_id_configured()

        # Validate mqtt prefix
        prefix = user_input.get(CONF_MQTT_NODE, "")
        try:
            prefix = _normalize_prefix(prefix)
            valid_subscribe_topic(f"{prefix}/#")
        except (ValueError, TypeError) as ex:
            _LOGGER.debug("Invalid mqtt node '%s': %s", prefix, ex)
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "invalid_nodename"},
            )

        # Validate language
        try:
            lang = AVAILABLE_LANGUAGES.index(user_input.get(CONF_LANGUAGE, "en"))
        except ValueError:
            _LOGGER.debug(
                "Invalid language provided: %s", user_input.get(CONF_LANGUAGE)
            )
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "invalid_language"},
            )

        # All validations passed; create the entry
        try:
            return self.async_create_entry(
                title=id_name,
                data={
                    CONF_ID: id_name,
                    CONF_MQTT_NODE: prefix,
                    CONF_LANGUAGE: user_input.get(CONF_LANGUAGE),
                    CONF_FREQ: user_input.get(CONF_FREQ, 100),
                },
                options={},
            )
        except Exception as exc:  # defensive: surface creation failure
            _LOGGER.exception("Failed to create config entry: %s", exc)
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "creation_error"},
            )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler for the provided config entry."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Remko MQTT config flow options handler."""

    def __init__(self, config_entry):
        """Initialize Remko MQTT options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def validate_input(self, data):
        """Validate input in step user"""
        return data

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MQTT_NODE,
                    default=self._config_entry.data.get(CONF_MQTT_NODE),
                ): cv.string,
                vol.Required(
                    CONF_LANGUAGE,
                    default=self._config_entry.data.get(CONF_LANGUAGE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["en", "de"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(
                    CONF_FREQ, default=self._config_entry.data.get(CONF_FREQ)
                ): cv.positive_int,
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema)

        error_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MQTT_NODE, default=user_input[CONF_MQTT_NODE]
                ): cv.string,
                vol.Required(
                    CONF_LANGUAGE, default=user_input[CONF_LANGUAGE]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["en", "de"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(CONF_FREQ, default=user_input[CONF_FREQ]): cv.positive_int,
            }
        )

        try:
            entryTitle = self._config_entry.title
            id_name = self._config_entry.data[CONF_ID]
        except (KeyError, AttributeError) as ex:
            _LOGGER.error("Failed to get config entry data: %s", ex)
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "invalid_id"},
            )

        try:
            prefix = user_input[CONF_MQTT_NODE]
            if prefix.endswith("/#"):
                prefix = prefix[:-2]
            elif prefix.endswith("/"):
                prefix = prefix[:-1]
            valid_subscribe_topic(f"{prefix}/#")
        except (ValueError, TypeError) as ex:
            _LOGGER.debug("Invalid mqtt node '%s': %s", prefix, ex)
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "invalid_nodename"},
            )

        try:
            lang = AVAILABLE_LANGUAGES.index(user_input[CONF_LANGUAGE])
        except (ValueError, IndexError) as ex:
            _LOGGER.debug(
                "Invalid language provided: %s, error: %s",
                user_input[CONF_LANGUAGE],
                ex,
            )
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "invalid_language"},
            )

        try:
            data = {
                CONF_ID: id_name,
                CONF_MQTT_NODE: prefix,
                CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                CONF_FREQ: user_input[CONF_FREQ],
            }

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data=data,
                options={},
            )

            # This is the options entry, keep it empty
            return self.async_create_entry(title="", data={})

        except Exception as ex:
            _LOGGER.exception("Failed to update config entry: %s", ex)
            return self.async_show_form(
                step_id="user",
                data_schema=error_schema,
                errors={"base": "update_error"},
            )
