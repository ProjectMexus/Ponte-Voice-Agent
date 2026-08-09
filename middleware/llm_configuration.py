"""Server-owned configuration for the non-streaming execution agent."""
from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from .llm_transport import OpenAICompatibleChatClient


def agent_chat_client_from_environment(environment: Mapping[str, str] | None = None) -> OpenAICompatibleChatClient:
    environment = os.environ if environment is None else environment
    url = environment.get("PONTE_LLM_API_URL", "").strip()
    thinking_flag = environment.get("PONTE_LLM_ENABLE_THINKING", "").strip().casefold()
    if thinking_flag not in {"", "false", "0"}:
        raise ValueError("The non-streaming execution agent requires PONTE_LLM_ENABLE_THINKING=false")
    # QwenCloud enables reasoning by default. The execution protocol stores
    # server-constructed decisions, not provider reasoning, so disable it.
    qwen_cloud = urlsplit(url).hostname == "maas.qwencloudapi.com"
    thinking = False if thinking_flag or qwen_cloud else None
    return OpenAICompatibleChatClient(
        url,
        api_key=environment.get("PONTE_LLM_API_KEY", ""),
        model=environment.get("PONTE_LLM_MODEL", "gpt-4o-mini"),
        timeout=float(environment.get("PONTE_LLM_TIMEOUT_SECONDS", "30")),
        enable_thinking=thinking,
        normalize_final_response=qwen_cloud,
    )
