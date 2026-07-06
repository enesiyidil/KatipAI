"""Voice profile matching for mic chunks."""

from __future__ import annotations

import logging

import numpy as np

from core.config import settings

logger = logging.getLogger(__name__)


class VoiceMatcher:
    """Evaluate mic chunks against enrolled voice profile."""

    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service is None:
            from core.audio.voice_profile import VoiceProfileService

            self._service = VoiceProfileService()
        return self._service

    def is_enrolled(self) -> bool:
        return self._get_service().is_enrolled()

    def evaluate(self, audio: np.ndarray) -> tuple[float | None, str, bool]:
        """
        Returns (match_score, speaker_label, should_skip_stt).
        """
        mode = settings.voice_filter_mode
        if mode == "off":
            return None, "Ben", False

        svc = self._get_service()
        if not svc.is_enrolled():
            if mode == "strict":
                logger.debug("Voice strict mode but no profile — skipping mic chunk")
                return None, "Bilinmeyen", True
            return None, "Ben", False

        score = svc.match(audio)
        threshold = settings.voice_match_threshold

        if score >= threshold:
            return score, "Ben", False

        if mode == "strict":
            return score, "Bilinmeyen", True

        # prefer: düşük skorda yine transcribe et, mic kanalında "Ben" etiketi koru
        return score, "Ben", False
