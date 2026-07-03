"""ONNX speaker embedding for personal voice profile."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.config import settings
from core.db.database import get_session
from core.db.models import VoiceProfile

logger = logging.getLogger(__name__)

MODEL_NAME = "speaker_embedding.onnx"
SAMPLE_RATE = 16000


class VoiceProfileService:
    """Extract speaker embeddings and match against enrolled profile."""

    def __init__(self):
        self._session = None
        self._input_name: str | None = None
        self._output_name: str | None = None

    @property
    def model_path(self) -> Path:
        return settings.data_dir / "models" / MODEL_NAME

    def _ensure_model(self) -> bool:
        if not self.model_path.exists():
            logger.warning("Voice model missing: %s — run scripts/download_voice_model.py", self.model_path)
            return False
        if self._session is None:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(self.model_path),
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            self._output_name = self._session.get_outputs()[0].name
        return True

    def _mel_features(self, audio: np.ndarray) -> np.ndarray:
        """Compute log-mel spectrogram features for embedding model."""
        from scipy import signal

        audio = audio.astype(np.float32)
        if len(audio) < SAMPLE_RATE:
            audio = np.pad(audio, (0, SAMPLE_RATE - len(audio)))

        f, t, zxx = signal.stft(
            audio,
            fs=SAMPLE_RATE,
            nperseg=400,
            noverlap=160,
            nfft=512,
        )
        power = np.abs(zxx) ** 2
        n_mels = 80
        mel_basis = self._mel_filterbank(n_mels, SAMPLE_RATE, f.shape[0])
        mel = mel_basis @ power
        log_mel = np.log(mel + 1e-10)
        return log_mel.T.astype(np.float32)

    @staticmethod
    def _mel_filterbank(n_mels: int, sr: int, n_fft_bins: int) -> np.ndarray:
        """Simple mel filterbank."""
        low_freq = 0
        high_freq = sr / 2
        mel_low = 2595 * np.log10(1 + low_freq / 700)
        mel_high = 2595 * np.log10(1 + high_freq / 700)
        mel_points = np.linspace(mel_low, mel_high, n_mels + 2)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)
        bin_points = np.floor((n_fft_bins * 2 + 1) * hz_points / sr).astype(int)
        fbank = np.zeros((n_mels, n_fft_bins))
        for i in range(n_mels):
            left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
            for j in range(left, center):
                if center > left:
                    fbank[i, j] = (j - left) / (center - left)
            for j in range(center, right):
                if right > center:
                    fbank[i, j] = (right - j) / (right - center)
        return fbank

    def extract_embedding(self, audio: np.ndarray) -> np.ndarray | None:
        if not self._ensure_model():
            return self._fallback_embedding(audio)

        features = self._mel_features(audio)
        # Pad/truncate to fixed time steps expected by model
        target_frames = 200
        if features.shape[0] < target_frames:
            pad = np.zeros((target_frames - features.shape[0], features.shape[1]), dtype=np.float32)
            features = np.vstack([features, pad])
        else:
            features = features[:target_frames]

        inp = features[np.newaxis, np.newaxis, :, :]
        try:
            out = self._session.run([self._output_name], {self._input_name: inp})[0]
            emb = out.reshape(-1).astype(np.float32)
            norm = np.linalg.norm(emb)
            if norm > 1e-8:
                emb = emb / norm
            return emb
        except Exception as e:
            logger.warning("ONNX embedding failed, using fallback: %s", e)
            return self._fallback_embedding(audio)

    @staticmethod
    def _fallback_embedding(audio: np.ndarray) -> np.ndarray:
        """Spectral fingerprint fallback when ONNX model unavailable."""
        audio = audio.astype(np.float32)
        if len(audio) < SAMPLE_RATE // 2:
            audio = np.pad(audio, (0, SAMPLE_RATE // 2 - len(audio)))
        fft = np.abs(np.fft.rfft(audio[: SAMPLE_RATE * 2]))
        # Downsample to 128 bins
        step = max(1, len(fft) // 128)
        emb = fft[::step][:128].astype(np.float32)
        norm = np.linalg.norm(emb)
        if norm > 1e-8:
            emb = emb / norm
        return emb

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        dot = float(np.dot(a, b))
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na < 1e-8 or nb < 1e-8:
            return 0.0
        return max(0.0, min(1.0, dot / (na * nb)))

    def is_enrolled(self) -> bool:
        with get_session() as db:
            return db.query(VoiceProfile).first() is not None

    def load_profile(self) -> np.ndarray | None:
        with get_session() as db:
            row = db.query(VoiceProfile).order_by(VoiceProfile.id.desc()).first()
            if not row:
                return None
            return np.frombuffer(row.embedding, dtype=np.float32)

    def enroll(self, samples: list[np.ndarray]) -> float:
        embeddings = []
        for sample in samples:
            emb = self.extract_embedding(sample)
            if emb is not None:
                embeddings.append(emb)
        if not embeddings:
            raise ValueError("No valid audio samples for enrollment")

        centroid = np.mean(embeddings, axis=0).astype(np.float32)
        norm = np.linalg.norm(centroid)
        if norm > 1e-8:
            centroid = centroid / norm

        blob = centroid.tobytes()
        with get_session() as db:
            db.query(VoiceProfile).delete()
            db.add(
                VoiceProfile(
                    embedding=blob,
                    sample_count=len(samples),
                    updated_at=datetime.now(timezone.utc),
                )
            )

        np.savez(settings.data_dir / "voice_profile.npz", embedding=centroid)
        logger.info("Voice profile enrolled with %d samples", len(samples))
        return float(np.mean([self.cosine_similarity(centroid, e) for e in embeddings]))

    def delete_profile(self) -> None:
        with get_session() as db:
            db.query(VoiceProfile).delete()
        backup = settings.data_dir / "voice_profile.npz"
        backup.unlink(missing_ok=True)

    def match(self, audio: np.ndarray) -> float:
        profile = self.load_profile()
        if profile is None:
            return 0.0
        emb = self.extract_embedding(audio)
        if emb is None:
            return 0.0
        return self.cosine_similarity(profile, emb)

    def status(self) -> dict:
        with get_session() as db:
            row = db.query(VoiceProfile).order_by(VoiceProfile.id.desc()).first()
            if not row:
                return {"enrolled": False, "sample_count": 0, "last_updated": None, "model_ready": self.model_path.exists()}
            return {
                "enrolled": True,
                "sample_count": row.sample_count,
                "last_updated": row.updated_at.isoformat() if row.updated_at else None,
                "model_ready": self.model_path.exists(),
            }
