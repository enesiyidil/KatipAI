from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KATIPAI_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8742
    data_dir: Path = Path.home() / ".katipai"
    vault_path: Path | None = None

    sample_rate: int = 16000
    silence_chunk_ms: int = 2000
    mic_silence_chunk_ms: int = 800
    max_chunk_ms: int = 12000
    system_max_chunk_ms: int = 25000
    silence_session_ms: int = 60000
    vad_threshold: float = 0.6
    min_audio_rms: float = 0.012

    stt_model: str = "mlx-community/whisper-large-v3-turbo"
    stt_fallback_model: str = "mlx-community/whisper-medium-mlx"
    stt_language: str = "tr"

    llm_model: str = "mlx-community/Qwen3.5-4B-OptiQ-4bit"
    llm_fallback_model: str = "mlx-community/Qwen2.5-3B-Instruct-4bit"

    mic_enabled: bool = True
    system_enabled: bool = True
    audio_retention_days: int = 7

    echo_suppression_enabled: bool = True
    echo_correlation_threshold: float = 0.65
    voice_filter_mode: str = "off"
    voice_match_threshold: float = 0.75
    capture_all_system_audio: bool = False

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "katipai.db"


settings = Settings()
