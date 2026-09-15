from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """
    A single workflow qualification test case.

    input_data is optional for backward compatibility with the
    existing manual qualification API. Real agent execution in V1
    will populate it.
    """

    case_id: str

    # Test definition
    input_data: Any = None
    expected_output: Any

    # Execution result
    actual_output: Optional[Any] = None
    success: bool = False

    # Reliability signals
    latency_ms: float = Field(default=0, ge=0)
    maximum_latency_ms: Optional[float] = Field(default=None, ge=0)

    tool_error: bool = False

    # Risk classification
    critical: bool = False
    human_review_required: bool = False

    # Cost
    estimated_cost_usd: float = Field(default=0, ge=0)
    maximum_cost_usd: Optional[float] = Field(default=None, ge=0)

    # Failure information
    failure_category: Optional[str] = None
    error_message: Optional[str] = None


class Workflow(BaseModel):
    """
    Qualification policy for one AI-agent workflow.
    """

    name: str
    description: str = ""

    # Required reliability
    target_reliability: float = Field(
        default=95,
        ge=0,
        le=100,
    )

    # Maximum number of critical failures allowed
    maximum_critical_failures: int = Field(
        default=0,
        ge=0,
    )

    # Maximum percentage of cases requiring human review
    maximum_human_review_rate: float = Field(
        default=20,
        ge=0,
        le=100,
    )

    # Optional operational limits
    maximum_average_latency_ms: Optional[float] = Field(
        default=None,
        ge=0,
    )

    maximum_average_cost_usd: Optional[float] = Field(
        default=None,
        ge=0,
    )

    # Qualification cases
    test_cases: List[TestCase]


class Failure(BaseModel):
    """
    A failure discovered during qualification.
    """

    case_id: str
    category: str
    severity: str
    message: str


class QualificationResult(BaseModel):
    """
    Final qualification result and deployment decision.
    """

    workflow_name: str

    # Execution summary
    total_cases: int
    successful_cases: int
    failed_cases: int

    # Reliability
    reliability_score: float

    # Failure metrics
    critical_failures: int
    tool_failures: int

    # Human oversight
    human_review_cases: int
    human_review_rate: float

    # Performance
    average_latency_ms: float

    # Cost
    total_estimated_cost_usd: float
    average_cost_per_case_usd: float

    # Applied qualification policy
    target_reliability: float
    maximum_critical_failures: int
    maximum_human_review_rate: float

    maximum_average_latency_ms: Optional[float] = None
    maximum_average_cost_usd: Optional[float] = None

    # Final decision
    verdict: str
    reasons: List[str]

    # Detailed failures
    failures: List[Failure]