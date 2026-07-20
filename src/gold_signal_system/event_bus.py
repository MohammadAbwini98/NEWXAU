from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class EventBus:
    """In-process publish/subscribe bus for realtime websocket updates."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: dict) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)

    async def stream(self, queue: asyncio.Queue, heartbeat_seconds: int) -> AsyncIterator[dict]:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=max(heartbeat_seconds, 1))
                yield event
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": {}}
