from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent

from .client import HermesApiClient, HermesApiError
from .const import (
    CONF_ALWAYS_SPEAK_FALLBACK,
    CONF_ENABLE_CONTINUED_CONVERSATION,
    CONF_ENABLE_SESSION_REUSE,
    CONF_EXPOSE_DEVICE_CONTEXT,
    CONF_FALLBACK_MEDIA_PLAYER,
    CONF_FALLBACK_TTS_ENGINE,
    CONF_INSTRUCTIONS,
    CONF_SESSION_TIMEOUT_SECONDS,
    DEFAULT_ALWAYS_SPEAK_FALLBACK,
    DEFAULT_ENABLE_CONTINUED_CONVERSATION,
    DEFAULT_ENABLE_SESSION_REUSE,
    DEFAULT_EXPOSE_DEVICE_CONTEXT,
    DEFAULT_FALLBACK_MEDIA_PLAYER,
    DEFAULT_FALLBACK_TTS_ENGINE,
    DEFAULT_INSTRUCTIONS,
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


HermesConfigEntry = ConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HermesConfigEntry,
    async_add_entities,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HermesConversationEntity(hass, entry, data["client"], data["sessions"])])


class HermesConversationEntity(conversation.ConversationEntity, conversation.AbstractConversationAgent):
    _attr_has_entity_name = True
    _attr_name = "Hermes"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HermesConfigEntry,
        client: HermesApiClient,
        session_map: dict[str, dict[str, Any]],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.session_map = session_map
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title or "Hermes"

    @property
    def supported_languages(self) -> str | list[str]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        del chat_log

        response = intent.IntentResponse(language=user_input.language)
        continue_conversation = self._continued_conversation_enabled()
        reuse_session = self._session_reuse_enabled()
        conversation_id = user_input.conversation_id or str(uuid.uuid4())
        device_id = getattr(user_input, "device_id", None)
        satellite_id = getattr(user_input, "satellite_id", None)
        session_key = self._build_session_key(user_input, conversation_id) if reuse_session else None
        session_id = self._get_active_session_id(session_key) if session_key else None
        _LOGGER.info(
            "Hermes voice turn: continued=%s reuse_session=%s conversation_id=%s device_id=%s satellite_id=%s session_key=%s reused_session_id=%s",
            continue_conversation,
            reuse_session,
            conversation_id,
            device_id,
            satellite_id,
            session_key,
            session_id,
        )
        instructions = await self._build_instructions(user_input)

        try:
            result = await self.client.async_send(
                text=user_input.text,
                instructions=instructions,
                session_id=session_id,
            )
        except HermesApiError as err:
            _LOGGER.warning("Hermes API error: %s", err)
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Hermes API error: {err}",
            )
            return conversation.ConversationResult(
                response=response,
                conversation_id=conversation_id,
                continue_conversation=False,
            )
        except Exception as err:  # pragma: no cover - defensive fallback
            _LOGGER.exception("Unexpected Hermes conversation failure")
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Unexpected Hermes error: {err}",
            )
            return conversation.ConversationResult(
                response=response,
                conversation_id=conversation_id,
                continue_conversation=False,
            )

        if session_key:
            self._remember_session(session_key, result.session_id)

        _LOGGER.info(
            "Hermes voice turn result: session_key=%s prior_session_id=%s returned_session_id=%s text_len=%s",
            session_key,
            session_id,
            result.session_id,
            len(result.text or ""),
        )

        response.async_set_speech(result.text)
        await self._async_speak_fallback(result.text, user_input)

        return conversation.ConversationResult(
            response=response,
            conversation_id=conversation_id,
            continue_conversation=continue_conversation,
        )

    def _continued_conversation_enabled(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_ENABLE_CONTINUED_CONVERSATION,
                self.entry.data.get(
                    CONF_ENABLE_CONTINUED_CONVERSATION,
                    DEFAULT_ENABLE_CONTINUED_CONVERSATION,
                ),
            )
        )

    def _session_reuse_enabled(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_ENABLE_SESSION_REUSE,
                self.entry.data.get(
                    CONF_ENABLE_SESSION_REUSE,
                    DEFAULT_ENABLE_SESSION_REUSE,
                ),
            )
        )

    def _session_timeout_seconds(self) -> int:
        try:
            return max(
                0,
                int(
                    self.entry.options.get(
                        CONF_SESSION_TIMEOUT_SECONDS,
                        self.entry.data.get(
                            CONF_SESSION_TIMEOUT_SECONDS,
                            DEFAULT_SESSION_TIMEOUT_SECONDS,
                        ),
                    )
                ),
            )
        except (TypeError, ValueError):
            return DEFAULT_SESSION_TIMEOUT_SECONDS

    def _build_session_key(
        self,
        user_input: conversation.ConversationInput,
        conversation_id: str,
    ) -> str:
        device_id = getattr(user_input, "device_id", None)
        satellite_id = getattr(user_input, "satellite_id", None)
        if device_id:
            return f"device:{device_id}"
        if satellite_id:
            return f"satellite:{satellite_id}"
        return f"conversation:{conversation_id}"

    def _get_active_session_id(self, session_key: str | None) -> str | None:
        if not session_key:
            return None

        record = self.session_map.get(session_key)
        if not record:
            _LOGGER.info("Hermes voice session miss: session_key=%s", session_key)
            return None

        session_id = record.get("session_id")
        last_used_at = float(record.get("last_used_at", 0) or 0)
        timeout_seconds = self._session_timeout_seconds()
        if timeout_seconds and (time.time() - last_used_at) > timeout_seconds:
            _LOGGER.info(
                "Hermes voice session expired: session_key=%s session_id=%s idle_seconds=%.1f timeout_seconds=%s",
                session_key,
                session_id,
                time.time() - last_used_at,
                timeout_seconds,
            )
            self.session_map.pop(session_key, None)
            return None

        active_session_id = session_id if isinstance(session_id, str) and session_id.strip() else None
        _LOGGER.info(
            "Hermes voice session hit: session_key=%s session_id=%s idle_seconds=%.1f",
            session_key,
            active_session_id,
            time.time() - last_used_at,
        )
        return active_session_id

    def _remember_session(self, session_key: str, session_id: str | None) -> None:
        if not session_id:
            self.session_map.pop(session_key, None)
            return

        self.session_map[session_key] = {
            "session_id": session_id,
            "last_used_at": time.time(),
        }
        _LOGGER.info("Hermes voice session stored: session_key=%s session_id=%s", session_key, session_id)

    async def _build_instructions(
        self, user_input: conversation.ConversationInput
    ) -> str:
        base_instructions = self.entry.options.get(
            CONF_INSTRUCTIONS,
            self.entry.data.get(CONF_INSTRUCTIONS, DEFAULT_INSTRUCTIONS),
        ).strip()

        parts: list[str] = [base_instructions] if base_instructions else []

        if user_input.extra_system_prompt:
            parts.append(f"Home Assistant extra system prompt:\n{user_input.extra_system_prompt}")

        if self._session_reuse_enabled():
            timeout_seconds = self._session_timeout_seconds()
            parts.append(
                "Backend session reuse is enabled. Short follow-ups from the same Home Assistant device may refer to recent context"
                + (f" for up to {timeout_seconds} seconds of idle time." if timeout_seconds else ".")
            )

        if self._continued_conversation_enabled():
            parts.append(
                "Home Assistant continued conversation mode is enabled. Keep replies especially natural for rapid voice follow-ups."
            )

        expose_context = self.entry.options.get(
            CONF_EXPOSE_DEVICE_CONTEXT,
            self.entry.data.get(CONF_EXPOSE_DEVICE_CONTEXT, DEFAULT_EXPOSE_DEVICE_CONTEXT),
        )
        if expose_context:
            context_lines = await self._build_origin_context(user_input)
            if context_lines:
                parts.append("Origin context:\n" + "\n".join(f"- {line}" for line in context_lines))

        return "\n\n".join(part for part in parts if part)

    async def _build_origin_context(
        self, user_input: conversation.ConversationInput
    ) -> list[str]:
        lines: list[str] = []

        language = getattr(user_input, "language", None)
        device_id = getattr(user_input, "device_id", None)
        satellite_id = getattr(user_input, "satellite_id", None)

        if language:
            lines.append(f"Language: {language}")
        if device_id:
            lines.extend(self._describe_device(device_id))
        if satellite_id:
            lines.extend(self._describe_satellite(satellite_id))

        return lines

    def _describe_device(self, device_id: str) -> list[str]:
        device_reg = dr.async_get(self.hass)
        area_reg = ar.async_get(self.hass)
        device = device_reg.async_get(device_id)
        if not device:
            return [f"Home Assistant device_id: {device_id}"]

        lines = [f"Origin device: {device.name_by_user or device.name or device_id}"]
        if device.area_id:
            area = area_reg.async_get_area(device.area_id)
            if area:
                lines.append(f"Origin area: {area.name}")
        return lines

    async def _async_speak_fallback(
        self, text: str, user_input: conversation.ConversationInput
    ) -> None:
        if not text.strip():
            return

        if not (
            getattr(user_input, "device_id", None)
            or getattr(user_input, "satellite_id", None)
        ):
            return

        speak_fallback = self.entry.options.get(
            CONF_ALWAYS_SPEAK_FALLBACK,
            self.entry.data.get(
                CONF_ALWAYS_SPEAK_FALLBACK,
                DEFAULT_ALWAYS_SPEAK_FALLBACK,
            ),
        )
        if not speak_fallback:
            return

        media_player_entity = self.entry.options.get(
            CONF_FALLBACK_MEDIA_PLAYER,
            self.entry.data.get(
                CONF_FALLBACK_MEDIA_PLAYER,
                DEFAULT_FALLBACK_MEDIA_PLAYER,
            ),
        )
        tts_entity = self.entry.options.get(
            CONF_FALLBACK_TTS_ENGINE,
            self.entry.data.get(
                CONF_FALLBACK_TTS_ENGINE,
                DEFAULT_FALLBACK_TTS_ENGINE,
            ),
        )
        if not media_player_entity or not tts_entity:
            return

        service_data = {
            "entity_id": tts_entity,
            "media_player_entity_id": media_player_entity,
            "message": text,
            "cache": True,
        }

        language = getattr(user_input, "language", None)
        if language:
            service_data["language"] = language

        try:
            await self.hass.services.async_call(
                "tts",
                "speak",
                service_data,
                blocking=True,
            )
        except Exception as err:  # pragma: no cover - defensive fallback
            _LOGGER.warning("Fallback TTS failed: %s", err)

    def _describe_satellite(self, satellite_id: str) -> list[str]:
        state = self.hass.states.get(satellite_id) if "." in satellite_id else None
        if not state:
            return [f"Assist satellite: {satellite_id}"]

        friendly_name = state.attributes.get("friendly_name", satellite_id)
        return [f"Assist satellite: {friendly_name} ({satellite_id})"]
