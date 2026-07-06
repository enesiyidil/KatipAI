"""Background thread pool for MLX STT/LLM — keeps the asyncio API loop responsive."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="katipai-ml")
        logger.info("ML worker thread pool started (1 worker)")
    return _executor


async def run_ml(fn: Callable[..., T], /, *args, **kwargs) -> T:
    """Run CPU/GPU-heavy model work off the asyncio event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_executor(), partial(fn, *args, **kwargs))


def shutdown_worker() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
        logger.info("ML worker thread pool shut down")
