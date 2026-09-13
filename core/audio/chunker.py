import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from core.audio.quality import is_loud_enough
from core.config import settings

logger = logging.getLogger(__name__)


class Channel(str, Enum):
    MIC = "mic"
    SYSTEM = "system"


DEFAULT_SPEAKER = {
    Channel.MIC: "Ben",
    Channel.SYSTEM: "Diğer",
}


@dataclass
class ChannelState:
    channel: Channel
    is_recording: bool = False
    buffer: list[np.ndarray] = field(default_factory=list)
    silence_ms: int = 0
    last_speech_at: datetime | None = None
    speaker_counter: int = 0
    current_speaker: str = ""

    def __post_init__(self):
        if not self.current_speaker:
            self.current_speaker = DEFAULT_SPEAKER[self.channel]


@dataclass
class ChunkResult:
    channel: Channel
    audio_path: Path
    duration_ms: int
    speaker_label: str
    started_at: datetime
    audio: np.ndarray | None = None
    is_echo: bool = False
    echo_score: float | None = None
    voice_match_score: float | None = None
    skip_reason: str | None = None
    source_app: str | None = None


class AudioChunker:
    """Per-channel VAD chunking: 2s silence splits, 60s global idle stops session."""

    def __init__(
        self,
        session_id: int,
        on_chunk: Callable[[ChunkResult], None],
        on_session_idle: Callable[[], None],
        sample_rate: int = 16000,
        echo_dedup=None,
        voice_matcher=None,
        source_app: str | None = None,
    ):
        from core.audio.vad_processor import SileroVAD

        self.session_id = session_id
        self.on_chunk = on_chunk
        self.on_session_idle = on_session_idle
        self._echo_dedup = echo_dedup
        self._voice_matcher = voice_matcher
        self._source_app = source_app
        self._vads = {ch: SileroVAD() for ch in Channel}
        self.sample_rate = sample_rate
        self.chunk_silence_ms = settings.silence_chunk_ms
        self.mic_silence_ms = settings.mic_silence_chunk_ms
        self.max_chunk_ms = settings.max_chunk_ms
        self.system_max_chunk_ms = settings.system_max_chunk_ms
        self.session_silence_ms = settings.silence_session_ms
        self.frame_ms = 30
        self.output_dir = settings.audio_dir / str(session_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_index = 0
        self._states = {ch: ChannelState(channel=ch) for ch in Channel}
        if Channel.SYSTEM in self._states and source_app:
            from core.audio.app_sources import system_speaker_label

            self._states[Channel.SYSTEM].current_speaker = system_speaker_label()
        self._session_active = True
        self._global_silence_ms = 0

    def _silence_limit_ms(self, channel: Channel) -> int:
        if channel == Channel.MIC:
            return self.mic_silence_ms
        return self.chunk_silence_ms

    def _max_chunk_ms(self, channel: Channel) -> int:
        if channel == Channel.SYSTEM:
            return self.system_max_chunk_ms
        return self.max_chunk_ms

    def _buffer_duration_ms(self, state: ChannelState) -> int:
        if not state.buffer:
            return 0
        samples = sum(len(f) for f in state.buffer)
        return int(samples / self.sample_rate * 1000)

    def _maybe_force_split(self, state: ChannelState) -> None:
        if state.is_recording and self._buffer_duration_ms(state) >= self._max_chunk_ms(state.channel):
            logger.debug(
                "Max chunk length reached on %s (%dms)",
                state.channel.value,
                self._buffer_duration_ms(state),
            )
            self._finalize_chunk(state)

    def process_frame(self, channel: Channel, frame: np.ndarray) -> None:
        if not self._session_active:
            return

        state = self._states[channel]
        is_speech = self._vads[channel].is_speech(frame, self.sample_rate)

        if is_speech:
            self._global_silence_ms = 0
            state.silence_ms = 0
            state.last_speech_at = datetime.now(timezone.utc)
            if not state.is_recording:
                state.is_recording = True
                state.buffer = []
                logger.debug("Recording started on %s", channel.value)
            state.buffer.append(frame)
            self._maybe_force_split(state)
        elif state.is_recording:
            state.silence_ms += self.frame_ms
            state.buffer.append(frame)
            if state.silence_ms >= self._silence_limit_ms(channel):
                self._finalize_chunk(state)
            else:
                self._maybe_force_split(state)
        else:
            self._global_silence_ms += self.frame_ms
            if self._global_silence_ms >= self.session_silence_ms:
                self._end_session()

    def _finalize_chunk(self, state: ChannelState) -> None:
        if not state.buffer:
            state.is_recording = False
            state.silence_ms = 0
            return

        audio = np.concatenate(state.buffer)
        duration_ms = int(len(audio) / self.sample_rate * 1000)
        if duration_ms < 300:
            state.buffer = []
            state.is_recording = False
            state.silence_ms = 0
            return

        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        if not is_loud_enough(rms):
            logger.debug("Chunk atlandı (düşük ses rms=%.4f) kanal=%s", rms, state.channel.value)
            state.buffer = []
            state.is_recording = False
            state.silence_ms = 0
            return

        started_at = state.last_speech_at or datetime.now(timezone.utc)
        filename = f"{state.channel.value}_{self._chunk_index:04d}.wav"
        path = self.output_dir / filename
        wavfile.write(path, self.sample_rate, (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16))

        is_echo = False
        echo_score = None
        skip_reason = None
        voice_match_score = None
        speaker_label = state.current_speaker

        if state.channel == Channel.MIC and self._echo_dedup is not None:
            is_echo, echo_score = self._echo_dedup.is_echo(audio)

        if state.channel == Channel.MIC and not is_echo and self._voice_matcher is not None:
            try:
                voice_match_score, speaker_label, voice_skip = self._voice_matcher.evaluate(audio)
            except Exception:
                logger.exception("Voice match failed — chunk yine de kaydedilecek")
                voice_match_score, speaker_label, voice_skip = None, state.current_speaker, False
            if voice_skip:
                skip_reason = "voice_mismatch"

        # Kendi sesin hoparlör yankısı olsa bile yüksek voice skoru varsa echo sayma
        if (
            state.channel == Channel.MIC
            and is_echo
            and voice_match_score is not None
            and voice_match_score >= settings.voice_match_threshold
        ):
            is_echo = False
            echo_score = None
            skip_reason = None
            speaker_label = "Ben"
            logger.info(
                "Mic echo ignored — voice match %.2f >= threshold",
                voice_match_score,
            )
        elif state.channel == Channel.MIC and is_echo:
            skip_reason = "echo"
            logger.info("Mic chunk echo detected (score=%.2f)", echo_score)

        result = ChunkResult(
            channel=state.channel,
            audio_path=path,
            duration_ms=duration_ms,
            speaker_label=speaker_label,
            started_at=started_at,
            audio=audio,
            is_echo=is_echo,
            echo_score=echo_score,
            voice_match_score=voice_match_score,
            skip_reason=skip_reason,
            source_app=self._source_app if state.channel == Channel.SYSTEM else None,
        )
        if state.channel == Channel.SYSTEM and self._source_app:
            from core.audio.app_sources import system_speaker_label

            result.speaker_label = system_speaker_label()
        self._chunk_index += 1
        state.buffer = []
        state.is_recording = False
        state.silence_ms = 0
        self.on_chunk(result)

    def force_chunk(self, channel: Channel) -> None:
        state = self._states[channel]
        if state.buffer:
            self._finalize_chunk(state)

    def _end_session(self) -> None:
        if not self._session_active:
            return
        self._session_active = False
        for state in self._states.values():
            if state.is_recording and state.buffer:
                self._finalize_chunk(state)
        logger.info("Session %s idle timeout", self.session_id)
        self.on_session_idle()

    def stop(self) -> None:
        self._session_active = False
        for state in self._states.values():
            if state.buffer:
                self._finalize_chunk(state)
