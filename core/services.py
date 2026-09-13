"""Shared runtime service instances.

Heavy types (RecordingService, NotePipeline) are not imported here so the
API can start in tests without loading capture / ML stacks.
"""

from __future__ import annotations

from typing import Any

recording_service: Any = None
note_pipeline: Any = None
