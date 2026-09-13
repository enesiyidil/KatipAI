"""Split long meeting audio into STT-sized segments using Silero VAD."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import torch

from core.audio.quality import is_loud_enough
from core.config import settings

logger = logging.getLogger(__name__)

MIN_SAMPLES = 512  # Silero window at 16kHz
PAD_MS = 400
MIN_SEG_MS = 1500
MAX_SEG_MS = 20000
MERGE_GAP_MS = 400


@dataclass
class AudioSegment:
    channel: str
    speaker_label: str
    audio: np.ndarray
    started_at: datetime
    duration_ms: int


_vad_model = None


def _get_vad_model():
    global _vad_model
    if _vad_model is None:
        from silero_vad import load_silero_vad

        _vad_model = load_silero_vad(onnx=True)
        logger.info("Meeting VAD model loaded")
    return _vad_model


def _speech_ranges(audio: np.ndarray, sample_rate: int, threshold: float) -> list[tuple[int, int]]:
    """Return (start_sample, end_sample) speech ranges via Silero offline API."""
    from silero_vad import get_speech_timestamps

    model = _get_vad_model()
    audio = audio.astype(np.float32).reshape(-1)
    if len(audio) < MIN_SAMPLES:
        return []
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 1.0:
        audio = audio / peak

    tensor = torch.from_numpy(audio)
    timestamps = get_speech_timestamps(
        tensor,
        model,
        threshold=threshold,
        sampling_rate=sample_rate,
        min_speech_duration_ms=MIN_SEG_MS,
        max_speech_duration_s=MAX_SEG_MS / 1000.0,
        min_silence_duration_ms=MERGE_GAP_MS,
        speech_pad_ms=PAD_MS,
        return_seconds=False,
    )
    ranges: list[tuple[int, int]] = []
    max_samples = int(sample_rate * MAX_SEG_MS / 1000)
    for ts in timestamps:
        start = int(ts["start"])
        end = int(ts["end"])
        if end - start <= max_samples:
            ranges.append((start, end))
            continue
        offset = start
        while offset < end:
            piece_end = min(offset + max_samples, end)
            ranges.append((offset, piece_end))
            offset = piece_end
    return ranges


def split_channel_segments(
    audio: np.ndarray,
    *,
    channel: str,
    speaker_label: str,
    session_start: datetime,
    segment_ms: int | None = None,
    min_ms: int = 800,
) -> list[AudioSegment]:
    """VAD-based speech segments; falls back to fixed windows if VAD fails."""
    sample_rate = settings.sample_rate
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if len(audio) == 0:
        return []

    try:
        ranges = _speech_ranges(audio, sample_rate, settings.vad_threshold)
    except Exception:
        logger.exception("Meeting VAD failed — falling back to fixed windows")
        ranges = []

    if not ranges:
        return _fixed_window_segments(
            audio,
            channel=channel,
            speaker_label=speaker_label,
            session_start=session_start,
            segment_ms=segment_ms or settings.system_max_chunk_ms,
            min_ms=min_ms,
        )

    segments: list[AudioSegment] = []
    for start, end in ranges:
        chunk = audio[start:end]
        rms = float(np.sqrt(np.mean(chunk**2)))
        if not is_loud_enough(rms):
            continue
        start_ms = int(start / sample_rate * 1000)
        segments.append(
            AudioSegment(
                channel=channel,
                speaker_label=speaker_label,
                audio=chunk,
                started_at=session_start + timedelta(milliseconds=start_ms),
                duration_ms=int(len(chunk) / sample_rate * 1000),
            )
        )
    return segments


def _fixed_window_segments(
    audio: np.ndarray,
    *,
    channel: str,
    speaker_label: str,
    session_start: datetime,
    segment_ms: int,
    min_ms: int,
) -> list[AudioSegment]:
    sample_rate = settings.sample_rate
    segment_samples = int(sample_rate * segment_ms / 1000)
    min_samples = int(sample_rate * min_ms / 1000)
    segments: list[AudioSegment] = []
    offset = 0
    while offset < len(audio):
        end = min(offset + segment_samples, len(audio))
        chunk = audio[offset:end]
        if len(chunk) >= min_samples:
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if is_loud_enough(rms):
                start_ms = int(offset / sample_rate * 1000)
                segments.append(
                    AudioSegment(
                        channel=channel,
                        speaker_label=speaker_label,
                        audio=chunk,
                        started_at=session_start + timedelta(milliseconds=start_ms),
                        duration_ms=int(len(chunk) / sample_rate * 1000),
                    )
                )
        offset = end
    return segments


def channel_rms(audio: np.ndarray) -> float:
    if audio is None or len(audio) == 0:
        return 0.0
    a = audio.astype(np.float32)
    return float(np.sqrt(np.mean(a**2)))


def assign_meeting_speakers(
    mic_segs: list[AudioSegment],
    sys_segs: list[AudioSegment],
    mic_audio: np.ndarray,
    system_audio: np.ndarray,
    voice_matcher=None,
) -> tuple[list[AudioSegment], list[AudioSegment], str | None]:
    """
    Relabel speakers based on energy + optional voice enrollment.
    Returns (mic_segs, sys_segs, warning_message).
    """
    mic_r = channel_rms(mic_audio)
    sys_r = channel_rms(system_audio)
    warning = None

    # Headset routing: user voice mostly on system channel
    headset_like = mic_r < settings.min_audio_rms * 0.5 and sys_r >= settings.min_audio_rms
    if headset_like:
        warning = (
            "Kulaklık: mikrofon sessiz, sesiniz sistem kanalından geliyor olabilir — "
            "konuşmacı etiketleri ses profiline göre ayarlandı."
        )
        matcher = voice_matcher
        enrolled = False
        if matcher is not None:
            try:
                enrolled = matcher.is_enrolled()
            except Exception:
                enrolled = False

        for seg in sys_segs:
            if enrolled and matcher is not None:
                try:
                    score, label, _ = matcher.evaluate(seg.audio)
                    seg.speaker_label = label if label in ("Ben", "Diğer") else (
                        "Ben" if score and score >= settings.voice_match_threshold else "Diğer"
                    )
                except Exception:
                    seg.speaker_label = "Diğer"
            else:
                # Without enrollment: keep as Diğer but mark mic segs empty-ish as skip
                seg.speaker_label = "Diğer"
        for seg in mic_segs:
            seg.speaker_label = "Ben"
        return mic_segs, sys_segs, warning

    # Normal: mic = Ben, system = Diğer; refine system with voice match if enrolled
    for seg in mic_segs:
        seg.speaker_label = "Ben"
    for seg in sys_segs:
        seg.speaker_label = "Diğer"
        if voice_matcher is not None:
            try:
                if voice_matcher.is_enrolled():
                    score, label, _ = voice_matcher.evaluate(seg.audio)
                    # High match on system = own voice echo through speakers
                    if score is not None and score >= settings.voice_match_threshold:
                        seg.speaker_label = "Ben"
                    elif label == "Ben":
                        seg.speaker_label = "Ben"
            except Exception:
                pass

    if mic_r < settings.min_audio_rms and sys_r >= settings.min_audio_rms * 2:
        warning = (
            "Mikrofon seviyesi düşük — Teams kulaklık kullanıyorsanız sesiniz "
            "sistem kanalından gelebilir."
        )
    return mic_segs, sys_segs, warning
