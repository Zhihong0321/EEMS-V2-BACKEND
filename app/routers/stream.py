from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..logic.sse import sse_manager

router = APIRouter(prefix="/api/v1", tags=["stream"])


@router.get("/stream/{simulator_id}")
async def stream(simulator_id: UUID) -> StreamingResponse:
    settings = get_settings()
    heartbeat_interval = settings.sse_heartbeat_seconds

    async def event_generator():
        async with sse_manager.subscribe(str(simulator_id)) as queue:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                    yield message
                except asyncio.TimeoutError:
                    yield await sse_manager.heartbeat()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
