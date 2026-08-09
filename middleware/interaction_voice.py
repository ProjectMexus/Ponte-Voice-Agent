"""Voice transport adapter that enters the shared InteractionCore."""

from __future__ import annotations

from typing import Any, Mapping
from dataclasses import replace
import uuid

from .interaction_contracts import EventEnvelope
from .interaction_core import InteractionCore
from .interaction_delivery import DeliveryOrchestrator
from .voice import (
    SpeechToTextAdapter,
    TextToSpeechAdapter,
    VoiceProviderSettings,
    VoiceTurn,
    VoiceTurnProvider,
    VoiceTurnResult,
)


class CoreVoiceTurnProvider(VoiceTurnProvider):
    """Adapt audio or browser STT text into the shared event path."""

    def __init__(
        self,
        core: InteractionCore,
        delivery: DeliveryOrchestrator,
        *,
        stt: SpeechToTextAdapter,
        tts: TextToSpeechAdapter | None = None,
        settings: VoiceProviderSettings | None = None,
    ) -> None:
        self.core = core
        self.delivery = delivery
        self.stt = stt
        self.tts = tts
        self.settings = settings or VoiceProviderSettings.from_env()

    def handle_turn(self, turn: VoiceTurn) -> VoiceTurnResult:
        transcript = self.stt.transcribe(turn.audio, replace(self.settings, locale=turn.locale))
        return self._handle_transcript(turn.session_id, turn.turn_id, transcript, turn.locale)

    def handle_transcript(self, session_id: str, transcript: str, context: Mapping[str, Any] | None = None) -> VoiceTurnResult:
        interaction_id = str((context or {}).get("interaction_id") or f"INT-{uuid.uuid4().hex[:12].upper()}")
        return self._handle_transcript(session_id, interaction_id, transcript, (context or {}).get("locale", "zh-HK"))

    def _handle_transcript(self, session_id: str, interaction_id: str, transcript: str, locale: str = "zh-HK") -> VoiceTurnResult:
        envelope = EventEnvelope.from_json({
            "routing": {"interaction_id": interaction_id, "session_id": session_id},
            "event": {"type": "user_utterance", "task_id": None, "content": transcript},
            "audit": {"locale": "en" if locale == "en-US" else "zh-Hant"},
        })
        canonical = self.core.handle(envelope)
        metadata = self.delivery.deliver(canonical)
        speech = None
        speech_audio = {"status": "unavailable"}
        if self.tts is not None and (locale != "en-US" or self.settings.tts_voice_en):
            try:
                settings = replace(self.settings, locale=locale, tts_voice=self.settings.tts_voice_en) if locale == "en-US" else self.settings
                speech = self.tts.synthesize(metadata["response"]["speech_text"], settings)
                speech_audio = {"status": "ready"}
            except Exception:
                speech = None
        metadata["speech_audio"] = speech_audio
        return VoiceTurnResult(metadata, speech)
