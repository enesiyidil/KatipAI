import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.api.routes import audio, chunks, corrections, jargon, permissions, sessions, settings as settings_routes, status, timeline, vault_read, voice
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
_pipeline_queue: asyncio.Queue[PipelineJob] | None = None
_pipeline_task: asyncio.Task | None = None
_pipeline_active = 0


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

    job_type: Literal["chunk", "finalize"] = job["type"]
    if job_type == "chunk":
        chunk_id = job["chunk_id"]
        await services.note_pipeline.process_chunk(chunk_id)
        await broadcast("transcript_done", {"chunk_id": chunk_id})
    elif job_type == "finalize":
        session_id = job["session_id"]
        await services.note_pipeline.try_finalize_session(session_id)
        await broadcast("session_finalized", {"session_id": session_id})


async def _pipeline_worker_loop() -> None:
    global _pipeline_active
    assert _pipeline_queue is not None
    while True:
        job = await _pipeline_queue.get()
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
    assert _pipeline_queue is not None
    await _pipeline_queue.put(job)


async def on_state_change(state: AppState) -> None:
    await broadcast("state", {"state": state.value})


async def on_mode_change(mode) -> None:
    await broadcast("mode", {"mode": mode.value})


async def on_chunk_saved(chunk_id: int) -> None:
    await broadcast("chunk", {"chunk_id": chunk_id})
    await _enqueue({"type": "chunk", "chunk_id": chunk_id})


async def on_session_end(session_id: int) -> None:
    await broadcast("session_end", {"session_id": session_id})
    await _enqueue({"type": "finalize", "session_id": session_id})


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline_queue, _pipeline_task, _api_loop

    init_db()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    services.note_pipeline = NotePipeline()
    _pipeline_queue = asyncio.Queue()
    _pipeline_task = asyncio.create_task(_pipeline_worker_loop())

    services.recording_service = RecordingService(
        on_state_change=on_state_change,
        on_mode_change=on_mode_change,
        on_chunk_saved=on_chunk_saved,
        on_session_end=on_session_end,
    )
    services.recording_service.set_event_loop(asyncio.get_running_loop())
    _api_loop = asyncio.get_running_loop()
    services.recording_service.start()
    logger.info("KatipAI core started on %s:%s", settings.host, settings.port)
    yield

    _api_loop = None
    if _pipeline_task:
        _pipeline_task.cancel()
        try:
            await _pipeline_task
        except asyncio.CancelledError:
            pass
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
