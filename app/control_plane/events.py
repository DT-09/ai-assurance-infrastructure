from __future__ import annotations

from typing import Callable, List

from .models import AuditEvent


class ControlPlaneEventBus:
    """
    In-process event boundary for the Control Plane.

    The interface is intentionally small so the implementation can later
    be replaced by Kafka, NATS, Pub/Sub, or another durable event system.
    """

    def __init__(self):
        self._events: List[AuditEvent] = []
        self._subscribers: List[Callable[[AuditEvent], None]] = []

    def publish(self, event: AuditEvent) -> None:
        self._events.append(event)

        for subscriber in list(self._subscribers):
            subscriber(event)

    def subscribe(
        self,
        subscriber: Callable[[AuditEvent], None],
    ) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(
        self,
        subscriber: Callable[[AuditEvent], None],
    ) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def list_events(self) -> List[AuditEvent]:
        return list(self._events)
