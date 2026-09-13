import numpy as np
from core.audio.dedup import EchoDedupEngine
from core.config import settings


def _tone(n: int = 8000) -> np.ndarray:
    return np.sin(np.linspace(0, 40 * np.pi, n)).astype(np.float32)


def test_identical_wave_scores_high():
    engine = EchoDedupEngine()
    tone = _tone()
    engine.push_system(tone)
    assert engine.echo_score(tone) > 0.9
    is_echo, score = engine.is_echo(tone)
    assert is_echo
    assert score > 0.9


def test_noise_scores_low():
    engine = EchoDedupEngine()
    engine.push_system(_tone())
    noise = np.random.default_rng(0).standard_normal(8000).astype(np.float32)
    assert engine.echo_score(noise) < 0.5


def test_suppression_off_returns_zero(monkeypatch):
    monkeypatch.setattr(settings, "echo_suppression_enabled", False)
    engine = EchoDedupEngine()
    tone = _tone()
    engine.push_system(tone)
    assert engine.echo_score(tone) == 0.0
