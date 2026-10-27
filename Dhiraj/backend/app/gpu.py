"""One big GPU model at a time: Unlimited-OCR (6.7 GB) and the Ollama LLM never share the 8 GB card.

    with big_slot.hold("ocr"):                       # background OCR
        while work and not big_slot.should_yield("ocr"): ...
    with big_slot.hold("planner", urgent=True): ...  # a lesson jumps the queue

Urgent waiters go ahead of normal ones, and a holder sees should_yield() turn True so it can unload
its model and step aside between batches.
"""
from __future__ import annotations

import threading
from collections import deque
from contextlib import contextmanager
from typing import Iterator


class BigSlot:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._owner: str | None = None
        self._queue: deque[tuple[str, bool]] = deque()

    @contextmanager
    def hold(self, owner: str, urgent: bool = False) -> Iterator[None]:
        ticket = (owner, urgent)
        with self._cond:
            if urgent:
                # After other urgent waiters, before every normal one.
                i = sum(1 for _, u in self._queue if u)
                self._queue.insert(i, ticket)
            else:
                self._queue.append(ticket)
            while self._owner is not None or self._queue[0] is not ticket:
                self._cond.wait()
            self._queue.popleft()
            self._owner = owner
        try:
            yield
        finally:
            with self._cond:
                self._owner = None
                self._cond.notify_all()

    def should_yield(self, owner: str) -> bool:
        """True while `owner` holds the slot and someone urgent is waiting for it."""
        with self._cond:
            return self._owner == owner and any(u for _, u in self._queue)

    @property
    def owner(self) -> str | None:
        return self._owner


big_slot = BigSlot()
