from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .client import HermesApiClient
from .const import (
    CONF_API_BASE_URL,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_TIMEOUT,
    DEFAULT_API_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)


HermesConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: HermesConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)
    client = HermesApiClient(
        session=session,
        base_url=entry.options.get(CONF_API_BASE_URL, entry.data.get(CONF_API_BASE_URL, DEFAULT_API_BASE_URL)),
        api_key=entry.options.get(CONF_API_KEY, entry.data[CONF_API_KEY]),
        model=entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL)),
        timeout=int(entry.options.get(CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "sessions": {},
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HermesConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
