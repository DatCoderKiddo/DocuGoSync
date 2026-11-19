"""
Server-Sent Events (SSE) endpoint.

The frontend subscribes to /api/events and receives real-time notifications
when new drift issues are detected — no polling needed from the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])

# Global broadcast queue — any service can push events here
_subscribers: list[asyncio.Queue] = []


def broadcast(event_type: str, data: dict) -> None:
    """
    Push an event to all connected SSE clients.
    Call this from any service after detecting drift or finishing analysis.
    """
    payload = json.dumps({"type": event_type, "data": data})
    dead = []
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


async def _event_generator(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    try:
        # Send a connected event immediately
        yield "event: connected\ndata: {}\n\n"
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive comment so the connection doesn't time out
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        try:
            _subscribers.remove(queue)
        except ValueError:
            pass


@router.get("")
async def sse_stream():
    """
    Subscribe to real-time drift detection events.

    Frontend usage:
      const es = new EventSource('/api/events')
      es.onmessage = e => { const event = JSON.parse(e.data); ... }
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.append(queue)

    return StreamingResponse(
        _event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
