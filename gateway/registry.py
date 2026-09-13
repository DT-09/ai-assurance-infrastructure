from app.models import QualificationResult


class QualificationRegistry:
    def __init__(self):
        self._records: dict[str, QualificationResult] = {}

    def set(self, agent_id: str, result: QualificationResult) -> None:
        self._records[agent_id] = result

    def get(self, agent_id: str) -> QualificationResult | None:
        return self._records.get(agent_id)

    def remove(self, agent_id: str) -> None:
        self._records.pop(agent_id, None)

    def all(self) -> dict[str, QualificationResult]:
        return self._records.copy()