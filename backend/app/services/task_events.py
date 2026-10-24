"""Process-local live output channels for approved task steps."""

import asyncio
import logging
import threading
from typing import Any, Dict, Set, Tuple
import uuid

logger = logging.getLogger(__name__)

StepKey = Tuple[uuid.UUID, uuid.UUID]
Subscriber = Tuple[asyncio.AbstractEventLoop, asyncio.Queue[Dict[str, Any]]]
_subscribers: Dict[StepKey, Set[Subscriber]] = {}
_subscribers_lock = threading.RLock()


async def subscribe_to_step(task_id: uuid.UUID, step_id: uuid.UUID) -> asyncio.Queue:
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    key = (task_id, step_id)
    with _subscribers_lock:
        _subscribers.setdefault(key, set()).add((asyncio.get_running_loop(), queue))
    return queue


def unsubscribe_from_step(
    task_id: uuid.UUID,
    step_id: uuid.UUID,
    event_queue: asyncio.Queue,
) -> None:
    key = (task_id, step_id)
    with _subscribers_lock:
        subscribers = _subscribers.get(key)
        if subscribers is None:
            return
        matches = {
            (loop, queue)
            for loop, queue in subscribers
            if queue is event_queue
        }
        subscribers.difference_update(matches)
        if not subscribers:
            _subscribers.pop(key, None)


def publish_step_event(
    task_id: uuid.UUID,
    step_id: uuid.UUID,
    event: Dict[str, Any],
) -> None:
    with _subscribers_lock:
        subscribers = tuple(_subscribers.get((task_id, step_id), ()))
    for loop, event_queue in subscribers:
        if loop.is_closed():
            continue
        try:
            loop.call_soon_threadsafe(event_queue.put_nowait, event)
        except RuntimeError:
            logger.debug("Step output subscriber disconnected.")
