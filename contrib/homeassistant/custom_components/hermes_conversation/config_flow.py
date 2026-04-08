from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .client import HermesApiClient, HermesApiError
from .const import (
    CONF_ALWAYS_SPEAK_FALLBACK,
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_ENABLE_CONTINUED_CONVERSATION,
    CONF_ENABLE_SESSION_REUSE,
    CONF_EXPOSE_DEVICE_CONTEXT,
    CONF_FALLBACK_MEDIA_PLAYER,
    CONF_FALLBACK_TTS_ENGINE,
    CONF_INSTRUCTIONS,
    CONF_MODEL,
    CONF_SESSION_TIMEOUT_SECONDS,
    CONF_TIMEOUT,
    DEFAULT_ALWAYS_SPEAK_FALLBACK,
    DEFAULT_API_BASE_URL,
    DEFAULT_ENABLE_CONTINUED_CONVERSATION,
    DEFAULT_ENABLE_SESSION_REUSE,
    DEFAULT_EXPOSE_DEVICE_CONTEXT,
    DEFAULT_FALLBACK_MEDIA_PLAYER,
    DEFAULT_FALLBACK_TTS_ENGINE,
    DEFAULT_INSTRUCTIONS,
    DEFAULT_MODEL,
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT,
    DEFAULT_TITLE,
    DOMAIN,
)


def _step_schema(defaults: dict | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_API_BASE_URL, default=defaults.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL)): str,
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_MODEL, default=defaults.get(CONF_MODEL, DEFAULT_MODEL)): str,
            vol.Required(CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)): vol.Coerce(int),
            vol.Required(
                CONF_ENABLE_CONTINUED_CONVERSATION,
                default=defaults.get(
                    CONF_ENABLE_CONTINUED_CONVERSATION,
                    DEFAULT_ENABLE_CONTINUED_CONVERSATION,
                ),
            ): bool,
            vol.Required(
                CONF_ENABLE_SESSION_REUSE,
                default=defaults.get(
                    CONF_ENABLE_SESSION_REUSE,
                    DEFAULT_ENABLE_SESSION_REUSE,
                ),
            ): bool,
            vol.Required(
                CONF_SESSION_TIMEOUT_SECONDS,
                default=defaults.get(
                    CONF_SESSION_TIMEOUT_SECONDS,
                    DEFAULT_SESSION_TIMEOUT_SECONDS,
                ),
            ): vol.Coerce(int),
            vol.Required(
                CONF_EXPOSE_DEVICE_CONTEXT,
                default=defaults.get(
                    CONF_EXPOSE_DEVICE_CONTEXT,
                    DEFAULT_EXPOSE_DEVICE_CONTEXT,
                ),
            ): bool,
            vol.Required(
                CONF_INSTRUCTIONS,
                default=defaults.get(CONF_INSTRUCTIONS, DEFAULT_INSTRUCTIONS),
            ): str,
            vol.Required(
                CONF_ALWAYS_SPEAK_FALLBACK,
                default=defaults.get(
                    CONF_ALWAYS_SPEAK_FALLBACK,
                    DEFAULT_ALWAYS_SPEAK_FALLBACK,
                ),
            ): bool,
            vol.Required(
                CONF_FALLBACK_MEDIA_PLAYER,
                default=defaults.get(
                    CONF_FALLBACK_MEDIA_PLAYER,
                    DEFAULT_FALLBACK_MEDIA_PLAYER,
                ),
            ): str,
            vol.Required(
                CONF_FALLBACK_TTS_ENGINE,
                default=defaults.get(
                    CONF_FALLBACK_TTS_ENGINE,
                    DEFAULT_FALLBACK_TTS_ENGINE,
                ),
            ): str,
        }
    )


class HermesConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._async_validate(user_input)
            except HermesApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{DOMAIN}:{user_input[CONF_API_BASE_URL].rstrip('/')}:{user_input[CONF_MODEL]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_step_schema(user_input),
            errors=errors,
        )

    async def _async_validate(self, user_input: dict) -> None:
        session = aiohttp_client.async_get_clientsession(self.hass)
        client = HermesApiClient(
            session=session,
            base_url=user_input[CONF_API_BASE_URL],
            api_key=user_input[CONF_API_KEY],
            model=user_input[CONF_MODEL],
            timeout=int(user_input[CONF_TIMEOUT]),
        )
        await client.async_validate()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HermesConversationOptionsFlow(config_entry)


class HermesConversationOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_step_schema(defaults),
            errors={},
        )
