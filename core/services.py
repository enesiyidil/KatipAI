"""Shared runtime service instances."""

from core.audio.recorder import RecordingService
from core.pipeline.note_pipeline import NotePipeline

recording_service: RecordingService | None = None
note_pipeline: NotePipeline | None = None
