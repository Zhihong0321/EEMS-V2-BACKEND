from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List


class SSEManager:
    def __init__(self) -> None:
        self._queues: Dict[str, List[asyncio.Queue[str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, simulator_id: str, event_type: str, payload: dict) -> None:
        message = self._format_event(event_type, payload)
        async with self._lock:
            queues = list(self._queues.get(simulator_id, []))
        for queue in queues:
            await queue.put(message)

    async def heartbeat(self) -> str:
        return self._format_event("ping", {})

    @asynccontextmanager
    async def subscribe(self, simulator_id: str) -> AsyncGenerator[asyncio.Queue[str], None]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._queues[simulator_id].append(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                subscribers = self._queues.get(simulator_id)
                if subscribers and queue in subscribers:
                    subscribers.remove(queue)
                if subscribers == []:
                    self._queues.pop(simulator_id, None)

    def _format_event(self, event_type: str, payload: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


sse_manager = SSEManager()
