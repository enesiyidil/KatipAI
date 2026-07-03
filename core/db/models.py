from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SessionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    PAUSED = "paused"
    PROCESSING = "processing"


class RecordingMode(str, Enum):
    NORMAL = "normal"
    MEETING = "meeting"
    SILENT = "silent"
    SENSITIVE = "sensitive"
    MANUAL = "manual"


class AppState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    RECORDING = "recording"
    PROCESSING = "processing"
    PAUSED = "paused"
    SENSITIVE = "sensitive"
    ERROR = "error"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mode: Mapped[str] = mapped_column(String(32), default=RecordingMode.NORMAL.value)
    status: Mapped[str] = mapped_column(String(32), default=SessionStatus.ACTIVE.value)
    vault_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    speaker_label: Mapped[str] = mapped_column(String(64), default="Ben")
    audio_path: Mapped[str] = mapped_column(String(1024))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    source_app: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_echo: Mapped[bool] = mapped_column(Boolean, default=False)
    echo_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    voice_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    speaker_id: Mapped[int | None] = mapped_column(ForeignKey("speakers.id"), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="chunks")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="chunk", uselist=False, cascade="all, delete-orphan")
    speaker: Mapped["Speaker | None"] = relationship(back_populates="chunks")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    language: Mapped[str] = mapped_column(String(8), default="tr")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    chunk: Mapped["Chunk"] = relationship(back_populates="transcript")
    corrections: Mapped[list["Correction"]] = relationship(back_populates="transcript", cascade="all, delete-orphan")


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"), index=True)
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transcript: Mapped["Transcript"] = relationship(back_populates="corrections")


class Jargon(Base):
    __tablename__ = "jargon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(256), unique=True)
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auto_added: Mapped[bool] = mapped_column(Boolean, default=False)


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    channel_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="speaker")


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
