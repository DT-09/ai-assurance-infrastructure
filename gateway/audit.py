from .models import AuditEvent
from .storage import SQLiteStorage


class AuditLog:
    def __init__(self, database_path: str = "gateway.db"):
        self.storage = SQLiteStorage(database_path)

    def record(self, event: AuditEvent) -> None:
        self.storage.save_audit_event(
            event.model_dump(mode="json")
        )

    def all(self) -> list[AuditEvent]:
        return [
            AuditEvent.model_validate(data)
            for data in self.storage.get_all_audit_events()
        ]