import logging

import numpy as np
import torch
from silero_vad import load_silero_vad

from core.config import settings

logger = logging.getLogger(__name__)

MIN_SAMPLES = 512  # Silero minimum window at 16kHz


class SileroVAD:
    """Voice activity detection using Silero VAD (ONNX)."""

    def __init__(self, threshold: float | None = None):
        self.threshold = threshold or settings.vad_threshold
        self.model = load_silero_vad(onnx=True)
        self._buffer = np.array([], dtype=np.float32)
        logger.info("Silero VAD loaded (ONNX)")

    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        if audio_chunk.size == 0:
            return False

        self._buffer = np.concatenate([self._buffer, audio_chunk.astype(np.float32)])
        if len(self._buffer) < MIN_SAMPLES:
            return self._last_result if hasattr(self, "_last_result") else False

        window = self._buffer[:MIN_SAMPLES]
        self._buffer = self._buffer[MIN_SAMPLES:]

        tensor = torch.from_numpy(window)
        if tensor.abs().max() > 1.0:
            tensor = tensor / tensor.abs().max()
        speech_prob = self.model(tensor, sample_rate).item()
        self._last_result = speech_prob >= self.threshold
        return self._last_result

    def reset(self) -> None:
        self._buffer = np.array([], dtype=np.float32)
