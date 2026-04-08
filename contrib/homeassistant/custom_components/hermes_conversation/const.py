DOMAIN = "hermes_conversation"

CONF_API_BASE_URL = "api_base_url"
CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_TIMEOUT = "timeout"
CONF_INSTRUCTIONS = "instructions"
CONF_ENABLE_CONTINUED_CONVERSATION = "enable_continued_conversation"
CONF_ENABLE_SESSION_REUSE = "enable_session_reuse"
CONF_SESSION_TIMEOUT_SECONDS = "session_timeout_seconds"
CONF_EXPOSE_DEVICE_CONTEXT = "expose_device_context"
CONF_ALWAYS_SPEAK_FALLBACK = "always_speak_fallback"
CONF_FALLBACK_MEDIA_PLAYER = "fallback_media_player"
CONF_FALLBACK_TTS_ENGINE = "fallback_tts_engine"

DEFAULT_TITLE = "Hermes"
DEFAULT_MODEL = "hermes-agent"
DEFAULT_TIMEOUT = 90
DEFAULT_API_BASE_URL = "http://127.0.0.1:8642/v1"
DEFAULT_ENABLE_CONTINUED_CONVERSATION = False
DEFAULT_ENABLE_SESSION_REUSE = True
DEFAULT_SESSION_TIMEOUT_SECONDS = 900
DEFAULT_EXPOSE_DEVICE_CONTEXT = True
DEFAULT_ALWAYS_SPEAK_FALLBACK = True
DEFAULT_FALLBACK_MEDIA_PLAYER = "media_player.living_room"
DEFAULT_FALLBACK_TTS_ENGINE = "tts.piper"
DEFAULT_INSTRUCTIONS = (
    "You are Hermes, a concise voice assistant running through Home Assistant Assist. "
    "Keep spoken replies brief, direct, and natural. Prefer acting over explaining. "
    "If you control Home Assistant devices, confirm the action plainly. "
    "Avoid markdown, bullet points, or long lists unless explicitly asked."
)

PLATFORMS = ["conversation"]
