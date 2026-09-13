from .models import AuditEvent


class AuditLog:
    def __init__(self):
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)

    def all(self) -> list[AuditEvent]:
        return self.events
