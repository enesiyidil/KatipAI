import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.api.routes import audio, chunks, corrections, jargon, meetings, permissions, sessions, settings as settings_routes, status, timeline, vault_read, voice
from core.audio.recorder import RecordingService
from core.config import settings
from core.db.database import init_db
from core.db.models import AppState
from core.pipeline.note_pipeline import NotePipeline
from core.pipeline.worker import shutdown_worker
from core import services

logger = logging.getLogger(__name__)

ws_clients: set[WebSocket] = set()
_api_loop: asyncio.AbstractEventLoop | None = None

PipelineJob = dict[str, Any]
_pipeline_queue: asyncio.PriorityQueue[tuple[int, int, PipelineJob]] | None = None
_pipeline_task: asyncio.Task | None = None
_pipeline_tasks: list[asyncio.Task] = []
_pipeline_active = 0
_pipeline_seq = 0
_live_transcription = True  # normal mod: canlı chunk STT
_PIPELINE_WORKERS = 2


def set_live_transcription(enabled: bool) -> None:
    global _live_transcription
    _live_transcription = enabled


def get_pipeline_info() -> dict[str, int | bool]:
    pending = _pipeline_queue.qsize() if _pipeline_queue else 0
    return {
        "pending": pending,
        "active": _pipeline_active,
        "busy": pending > 0 or _pipeline_active > 0,
    }


async def broadcast(event: str, data: dict[str, Any]) -> None:
    message = json.dumps({"event": event, **data})
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


def notify_clients(event: str, **data: Any) -> None:
    """Schedule a WS broadcast from sync code (HTTP handlers, audio threads)."""
    if _api_loop is None:
        return
    asyncio.run_coroutine_threadsafe(broadcast(event, data), _api_loop)


def _maybe_finish_processing() -> None:
    if _pipeline_queue and not _pipeline_queue.empty():
        return
    if services.recording_service:
        services.recording_service.on_processing_complete()


async def _run_pipeline_job(job: PipelineJob) -> None:
    if not services.note_pipeline:
        return

    job_type: Literal["chunk", "finalize", "meeting"] = job["type"]
    if job_type == "chunk":
        chunk_id = job["chunk_id"]
        try:
            await services.note_pipeline.process_chunk(chunk_id)
        except Exception as e:
            services.note_pipeline.mark_chunk_failed(chunk_id, str(e))
            await broadcast("transcript_done", {"chunk_id": chunk_id, "failed": True})
            raise
        await broadcast("transcript_done", {"chunk_id": chunk_id})
    elif job_type == "meeting":
        session_id = job["session_id"]
        try:
            await services.note_pipeline.process_meeting_session(session_id)
        except Exception:
            logger.exception("Meeting job failed for session %s", session_id)
        await broadcast("meeting_processed", {"session_id": session_id})
    elif job_type == "finalize":
        session_id = job["session_id"]
        await services.note_pipeline.try_finalize_session(session_id)
        await broadcast("session_finalized", {"session_id": session_id})


async def _reprocess_pending_chunks() -> None:
    """Requeue a capped backlog of untranscribed chunks on startup."""
    from core.pipeline.note_pipeline import find_pending_chunk_ids

    ids = find_pending_chunk_ids(limit=50)
    if not ids:
        return
    logger.info("Requeueing %d pending chunks on startup", len(ids))
    for chunk_id in ids:
        await _enqueue({"type": "chunk", "chunk_id": chunk_id})


async def on_chunk_saved(chunk_id: int) -> None:
    await broadcast("chunk", {"chunk_id": chunk_id})
    if not _live_transcription:
        return
    # Sessiz mod: kayıt olabilir ama STT kuyruğa alınmaz
    if services.recording_service and services.recording_service.mode.value == "silent":
        return
    await _enqueue({"type": "chunk", "chunk_id": chunk_id})


async def on_session_end(session_id: int) -> None:
    from core.db.database import get_session
    from core.db.models import RecordingMode, Session

    await broadcast("session_end", {"session_id": session_id})
    with get_session() as db:
        session = db.get(Session, session_id)
        if session and session.mode == RecordingMode.MEETING.value:
            return
    await _enqueue({"type": "finalize", "session_id": session_id})


async def on_meeting_end(session_id: int) -> None:
    await broadcast("meeting_end", {"session_id": session_id})
    await _enqueue({"type": "meeting", "session_id": session_id})


async def _pipeline_worker_loop() -> None:
    global _pipeline_active
    assert _pipeline_queue is not None
    while True:
        _, _, job = await _pipeline_queue.get()
        _pipeline_active += 1
        try:
            await _run_pipeline_job(job)
        except Exception:
            logger.exception("Pipeline job failed: %s", job)
        finally:
            _pipeline_active -= 1
            _pipeline_queue.task_done()
            _maybe_finish_processing()


async def _enqueue(job: PipelineJob) -> None:
    global _pipeline_seq
    assert _pipeline_queue is not None
    _pipeline_seq += 1
    # Lower priority number = processed first.
    # Live chunks always beat meeting batch so normal mode stays responsive.
    if job.get("type") == "chunk":
        priority = -2_000_000 - int(job["chunk_id"])
    elif job.get("type") == "meeting":
        priority = 100_000  # lower than live chunks
    else:
        priority = 1_000_000
    await _pipeline_queue.put((priority, _pipeline_seq, job))


def schedule_reprocess_chunk(chunk_id: int) -> bool:
    """Schedule chunk transcription from sync HTTP handlers."""
    if _api_loop is None or _pipeline_queue is None:
        return False
    asyncio.run_coroutine_threadsafe(
        _enqueue({"type": "chunk", "chunk_id": chunk_id}),
        _api_loop,
    )
    return True


def schedule_meeting_reprocess(session_id: int) -> bool:
    """Schedule meeting batch STT from sync HTTP handlers."""
    if _api_loop is None or _pipeline_queue is None:
        return False
    asyncio.run_coroutine_threadsafe(
        _enqueue({"type": "meeting", "session_id": session_id}),
        _api_loop,
    )
    return True


async def on_state_change(state: AppState) -> None:
    await broadcast("state", {"state": state.value})


async def on_mode_change(mode) -> None:
    await broadcast("mode", {"mode": mode.value})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline_queue, _pipeline_task, _pipeline_tasks, _api_loop

    init_db()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    services.note_pipeline = NotePipeline()
    _pipeline_queue = asyncio.PriorityQueue()
    _pipeline_tasks = [
        asyncio.create_task(_pipeline_worker_loop()) for _ in range(_PIPELINE_WORKERS)
    ]
    _pipeline_task = _pipeline_tasks[0]

    services.recording_service = RecordingService(
        on_state_change=on_state_change,
        on_mode_change=on_mode_change,
        on_chunk_saved=on_chunk_saved,
        on_session_end=on_session_end,
        on_meeting_end=on_meeting_end,
    )
    services.recording_service.set_event_loop(asyncio.get_running_loop())
    _api_loop = asyncio.get_running_loop()
    services.recording_service.start()
    await _reprocess_pending_chunks()
    logger.info(
        "KatipAI core started on %s:%s (%d pipeline workers)",
        settings.host,
        settings.port,
        _PIPELINE_WORKERS,
    )
    yield

    _api_loop = None
    for task in _pipeline_tasks:
        task.cancel()
    for task in _pipeline_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    _pipeline_tasks = []
    _pipeline_task = None
    _pipeline_queue = None

    if services.recording_service:
        services.recording_service.stop()
    shutdown_worker()


def create_app() -> FastAPI:
    app = FastAPI(title="KatipAI", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(status.router, prefix="/api", tags=["status"])
    app.include_router(audio.router, prefix="/api", tags=["audio"])
    app.include_router(voice.router, prefix="/api", tags=["voice"])
    app.include_router(permissions.router, prefix="/api", tags=["permissions"])
    app.include_router(sessions.router, prefix="/api", tags=["sessions"])
    app.include_router(meetings.router, prefix="/api", tags=["meetings"])
    app.include_router(chunks.router, prefix="/api", tags=["chunks"])
    app.include_router(jargon.router, prefix="/api", tags=["jargon"])
    app.include_router(corrections.router, prefix="/api", tags=["corrections"])
    app.include_router(settings_routes.router, prefix="/api", tags=["settings"])
    app.include_router(timeline.router, prefix="/api", tags=["timeline"])
    app.include_router(vault_read.router, prefix="/api", tags=["vault"])

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.add(ws)
        try:
            if services.recording_service:
                svc = services.recording_service
                await ws.send_text(json.dumps({
                    "event": "state",
                    "state": svc.app_state.value,
                }))
                await ws.send_text(json.dumps({
                    "event": "mode",
                    "mode": svc.mode.value,
                }))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(ws)

    return app
