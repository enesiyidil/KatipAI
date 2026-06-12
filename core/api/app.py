import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.api.routes import chunks, corrections, jargon, sessions, settings as settings_routes, status
from core.audio.recorder import RecordingService
from core.config import settings
from core.db.database import init_db
from core.db.models import AppState
from core.pipeline.note_pipeline import NotePipeline
from core import services

logger = logging.getLogger(__name__)

ws_clients: set[WebSocket] = set()
async def broadcast(event: str, data: dict[str, Any]) -> None:
    message = json.dumps({"event": event, **data})
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


async def on_state_change(state: AppState) -> None:
    await broadcast("state", {"state": state.value})


async def on_chunk_saved(chunk_id: int) -> None:
    await broadcast("chunk", {"chunk_id": chunk_id})
    if services.note_pipeline:
        await services.note_pipeline.process_chunk(chunk_id)
        await broadcast("transcript_done", {"chunk_id": chunk_id})


async def on_session_end(session_id: int) -> None:
    await broadcast("session_end", {"session_id": session_id})
    if services.note_pipeline:
        await services.note_pipeline.finalize_session(session_id)
        await broadcast("session_finalized", {"session_id": session_id})


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    services.note_pipeline = NotePipeline()
    services.recording_service = RecordingService(
        on_state_change=on_state_change,
        on_chunk_saved=on_chunk_saved,
        on_session_end=on_session_end,
    )
    services.recording_service.set_event_loop(asyncio.get_running_loop())
    services.recording_service.start()
    logger.info("KatipAI core started on %s:%s", settings.host, settings.port)
    yield
    if services.recording_service:
        services.recording_service.stop()


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
    app.include_router(sessions.router, prefix="/api", tags=["sessions"])
    app.include_router(chunks.router, prefix="/api", tags=["chunks"])
    app.include_router(jargon.router, prefix="/api", tags=["jargon"])
    app.include_router(corrections.router, prefix="/api", tags=["corrections"])
    app.include_router(settings_routes.router, prefix="/api", tags=["settings"])

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.add(ws)
        try:
            if services.recording_service:
                await ws.send_text(json.dumps({
                    "event": "state",
                    "state": services.recording_service.app_state.value,
                }))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_clients.discard(ws)

    return app
