from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.engine import qualify_workflow
from app.models import TestCase, Workflow


@dataclass
class ExecutionCase:
    """Defines one qualification scenario."""

    case_id: str
    input_data: Any
    expected_output: Any

    critical: bool = False
    human_review_required: bool = False

    maximum_latency_ms: Optional[float] = None
    maximum_cost_usd: Optional[float] = None


@dataclass
class ExecutionResult:
    """Raw result from one agent execution."""

    case_id: str
    input_data: Any
    expected_output: Any
    actual_output: Any

    success: bool
    latency_ms: float

    tool_error: bool
    critical: bool
    human_review_required: bool

    estimated_cost_usd: float = 0.0

    maximum_latency_ms: Optional[float] = None
    maximum_cost_usd: Optional[float] = None

    error: Optional[str] = None
    failure_category: Optional[str] = None


class AgentRunner:
    """
    Executes an agent against qualification cases.

    Supports both synchronous and asynchronous Python agents
    while keeping runner.run() synchronous for the V1 API.
    """

    def __init__(
        self,
        agent: Callable[[Any], Any],
        *,
        cost_estimator: Optional[
            Callable[[Any, Any], float]
        ] = None,
    ):
        if not callable(agent):
            raise TypeError("agent must be callable")

        self.agent = agent
        self.cost_estimator = cost_estimator

    async def _execute_agent_async(
        self,
        input_data: Any,
    ) -> Any:
        """Execute the agent and await it when necessary."""

        result = self.agent(input_data)

        if inspect.isawaitable(result):
            return await result

        return result

    def _execute_agent(
        self,
        input_data: Any,
    ) -> Any:
        """
        Execute a synchronous or asynchronous agent.

        The public runner remains synchronous so existing CLI,
        tests, and integrations continue to work.
        """

        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self._execute_agent_async(input_data)
            )

        # If run() is called from an already-running event loop,
        # execute the coroutine in a separate thread.
        import threading

        result_container: list[Any] = []
        error_container: list[BaseException] = []

        def execute() -> None:
            try:
                result_container.append(
                    asyncio.run(
                        self._execute_agent_async(input_data)
                    )
                )
            except BaseException as exc:
                error_container.append(exc)

        thread = threading.Thread(target=execute)
        thread.start()
        thread.join()

        if error_container:
            raise error_container[0]

        return result_container[0]

    def _estimate_cost(
        self,
        input_data: Any,
        actual_output: Any,
    ) -> float:
        """Calculate optional execution cost."""

        if self.cost_estimator is None:
            return 0.0

        try:
            cost = self.cost_estimator(
                input_data,
                actual_output,
            )

            return max(float(cost), 0.0)

        except Exception:
            # Cost estimation must never break qualification.
            return 0.0

    @staticmethod
    def _classify_failure(
        *,
        tool_error: bool,
        error: Optional[str],
        success: bool,
    ) -> Optional[str]:

        if tool_error:
            return "TOOL_ERROR"

        if error:
            return "EXECUTION_ERROR"

        if not success:
            return "OUTPUT_MISMATCH"

        return None

    def run_case(
        self,
        case: ExecutionCase,
    ) -> ExecutionResult:
        """Execute one qualification case."""

        start = time.perf_counter()

        try:
            actual_output = self._execute_agent(
                case.input_data
            )

            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            success = (
                actual_output == case.expected_output
            )

            estimated_cost_usd = self._estimate_cost(
                case.input_data,
                actual_output,
            )

            return ExecutionResult(
                case_id=case.case_id,
                input_data=case.input_data,
                expected_output=case.expected_output,
                actual_output=actual_output,
                success=success,
                latency_ms=latency_ms,
                tool_error=False,
                critical=case.critical,
                human_review_required=case.human_review_required,
                estimated_cost_usd=estimated_cost_usd,
                maximum_latency_ms=case.maximum_latency_ms,
                maximum_cost_usd=case.maximum_cost_usd,
                error=None,
                failure_category=self._classify_failure(
                    tool_error=False,
                    error=None,
                    success=success,
                ),
            )

        except Exception as exc:
            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            error_message = str(exc)

            return ExecutionResult(
                case_id=case.case_id,
                input_data=case.input_data,
                expected_output=case.expected_output,
                actual_output=None,
                success=False,
                latency_ms=latency_ms,
                tool_error=True,
                critical=case.critical,
                human_review_required=case.human_review_required,
                estimated_cost_usd=0.0,
                maximum_latency_ms=case.maximum_latency_ms,
                maximum_cost_usd=case.maximum_cost_usd,
                error=error_message,
                failure_category=self._classify_failure(
                    tool_error=True,
                    error=error_message,
                    success=False,
                ),
            )

    def run_cases(
        self,
        cases: list[ExecutionCase],
    ) -> list[ExecutionResult]:
        """Execute all qualification cases sequentially."""

        if not cases:
            raise ValueError(
                "At least one execution case is required"
            )

        return [
            self.run_case(case)
            for case in cases
        ]

    def run(
        self,
        workflow_name: str,
        cases: list[ExecutionCase],
        *,
        description: str = "Executed agent qualification",
        target_reliability: float = 95.0,
        maximum_critical_failures: int = 0,
        maximum_human_review_rate: float = 20.0,
        maximum_average_latency_ms: Optional[float] = None,
        maximum_average_cost_usd: Optional[float] = None,
    ):
        """
        Execute the agent and return a QualificationResult.

        This method intentionally remains synchronous for V1
        compatibility.
        """

        results = self.run_cases(cases)

        test_cases: list[TestCase] = []

        for result in results:
            test_cases.append(
                TestCase(
                    case_id=result.case_id,
                    input_data=result.input_data,
                    expected_output=result.expected_output,
                    actual_output=result.actual_output,
                    success=result.success,
                    latency_ms=result.latency_ms,
                    maximum_latency_ms=result.maximum_latency_ms,
                    tool_error=result.tool_error,
                    critical=result.critical,
                    human_review_required=result.human_review_required,
                    estimated_cost_usd=result.estimated_cost_usd,
                    maximum_cost_usd=result.maximum_cost_usd,
                    failure_category=result.failure_category,
                    error_message=result.error,
                )
            )

        workflow = Workflow(
            name=workflow_name,
            description=description,
            target_reliability=target_reliability,
            maximum_critical_failures=maximum_critical_failures,
            maximum_human_review_rate=maximum_human_review_rate,
            maximum_average_latency_ms=maximum_average_latency_ms,
            maximum_average_cost_usd=maximum_average_cost_usd,
            test_cases=test_cases,
        )

        return qualify_workflow(workflow)


def run_agent_sync(
    agent: Callable[[Any], Any],
    workflow_name: str,
    cases: list[ExecutionCase],
    *,
    description: str = "Executed agent qualification",
    target_reliability: float = 95.0,
    maximum_critical_failures: int = 0,
    maximum_human_review_rate: float = 20.0,
    maximum_average_latency_ms: Optional[float] = None,
    maximum_average_cost_usd: Optional[float] = None,
    cost_estimator: Optional[
        Callable[[Any, Any], float]
    ] = None,
):
    """
    Convenience wrapper for external integrations.
    """

    runner = AgentRunner(
        agent,
        cost_estimator=cost_estimator,
    )

    return runner.run(
        workflow_name,
        cases,
        description=description,
        target_reliability=target_reliability,
        maximum_critical_failures=maximum_critical_failures,
        maximum_human_review_rate=maximum_human_review_rate,
        maximum_average_latency_ms=maximum_average_latency_ms,
        maximum_average_cost_usd=maximum_average_cost_usd,
    )