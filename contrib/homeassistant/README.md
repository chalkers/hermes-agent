# Hermes Conversation for Home Assistant

This directory contains a custom Home Assistant conversation agent that proxies Assist text requests to Hermes Agent through Hermes's local OpenAI-compatible API server.

## What it does

- Registers a selectable conversation agent in Home Assistant Assist
- Sends transcribed user text to Hermes via `POST /v1/chat/completions`
- Reuses Hermes `X-Hermes-Session-Id` sessions so follow-up turns can keep context on the server side
- Keeps voice continuity sticky per HA device/satellite for a configurable idle timeout
- Passes device/satellite context into Hermes instructions for room-aware behavior

## Directory layout

- `custom_components/hermes_conversation/` — installable custom integration

## Install into Home Assistant

Copy `custom_components/hermes_conversation` into your Home Assistant config directory:

```text
<HA config>/custom_components/hermes_conversation
```

Then restart Home Assistant.

## Configure Hermes first

On the Hermes host, enable the API server in `~/.hermes/.env`:

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=choose-a-long-random-token
# optional if not localhost
# API_SERVER_HOST=0.0.0.0
# API_SERVER_PORT=8642
```

Restart the Hermes gateway after changing `.env`.

## Add the integration

In Home Assistant:

1. Settings → Devices & Services → Add Integration
2. Search for `Hermes Conversation`
3. Enter:
   - API base URL, usually `http://<hermes-host>:8642/v1`
   - API key
   - model, usually `hermes-agent`
4. Save

Recommended options for voice:
- leave `enable_session_reuse` on so Hermes keeps short-term memory across turns
- enable continued conversation if you want Home Assistant itself to stay in conversational follow-up mode
- set `session_timeout_seconds` to something forgiving like `900` or `1800`

## Use it with Assist

After adding the integration, pick Hermes as the conversation agent in your Assist pipeline.

The exact UI wording changes a bit across HA versions, but the path is usually:

- Settings → Voice assistants / Assist
- Open the pipeline used by your HA Voice device
- Set the conversation agent/engine to Hermes

## Notes

- This integration intentionally keeps voice replies short by default.
- Hermes still has access to its tools, including Home Assistant device control, through its own runtime.
- If you enable continued conversation, your voice device may keep listening after Hermes replies.
- Continued conversation now reuses a sticky Hermes session per device or satellite, so short voice follow-ups can still make sense even if Home Assistant rotates its own conversation ID.
