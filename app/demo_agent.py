def refund_agent(request: str) -> str:
    request = request.lower().strip()

    if "duplicate" in request:
        return "REFUND_APPROVED"

    if "damaged" in request:
        return "REFUND_APPROVED"

    if "outside policy" in request:
        return "REFUND_DENIED"

    if "unknown" in request:
        raise RuntimeError("Refund policy service unavailable")

    return "HUMAN_REVIEW"