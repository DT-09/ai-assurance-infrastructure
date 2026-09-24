from app.models import QualificationResult


QUALIFIED_VERDICTS = {
    "QUALIFIED",
}


def is_agent_qualified(result: QualificationResult) -> bool:
    return result.verdict in QUALIFIED_VERDICTS
