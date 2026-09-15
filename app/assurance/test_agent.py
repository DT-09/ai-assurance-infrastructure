from fastapi import APIRouter

router = APIRouter(
    prefix="/v1",
    tags=["Test Agent"],
)


@router.post("/test-agent")
def test_agent(payload: dict):
    input_data = payload.get("input")

    responses = {
        "Customer received a damaged product": "REFUND_APPROVED",
        "Customer requests a refund outside policy": "REFUND_DENIED",
        "Customer has an unclear request": "ESCALATE",
    }

    output = responses.get(
        input_data,
        "UNKNOWN",
    )

    return {
        "output": output,
        "cost_usd": 0.01,
    }
