"""One big GPU model at a time: Unlimited-OCR (6.7 GB) and the Ollama LLM never share the 8 GB card.

    with big_slot.hold("ocr"):                       # background OCR
        while work and not big_slot.should_yield("ocr"): ...
    with big_slot.hold("planner", urgent=True, shared=True): ...  # a lesson jumps the queue

Urgent waiters go ahead of normal ones, and a holder sees should_yield() turn True so it can unload
its model and step aside between batches. Shared holders with the same owner name hold the slot together
(two episodes of a course both use the LLM, which Ollama queues); everyone else waits until the last one leaves.
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
        self._shared = False
        self._count = 0
        self._queue: deque[tuple[str, bool, object]] = deque()

    @contextmanager
    def hold(self, owner: str, urgent: bool = False, shared: bool = False) -> Iterator[None]:
        ticket = (owner, urgent, object())                             # unique: equal tickets of two threads are never mixed up
        with self._cond:
            if shared and self._shared and self._owner == owner:        # the same kind of work already holds it: join in
                self._count += 1
                ticket = None
            elif urgent:
                # After other urgent waiters, before every normal one.
                i = sum(1 for t in self._queue if t[1])
                self._queue.insert(i, ticket)
            else:
                self._queue.append(ticket)
            while ticket is not None:
                if self._owner is None and self._queue[0] is ticket:
                    self._queue.popleft()
                    self._owner, self._shared, self._count = owner, shared, 1
                    break
                if shared and self._shared and self._owner == owner:
                    self._queue = deque(t for t in self._queue if t is not ticket)
                    self._count += 1
                    break
                self._cond.wait()
        try:
            yield
        finally:
            with self._cond:
                self._count -= 1
                if self._count == 0:
                    self._owner, self._shared = None, False
                self._cond.notify_all()

    def should_yield(self, owner: str) -> bool:
        """True while `owner` holds the slot and someone urgent is waiting for it."""
        with self._cond:
            return self._owner == owner and any(t[1] for t in self._queue)

    @property
    def owner(self) -> str | None:
        return self._owner


big_slot = BigSlot()
