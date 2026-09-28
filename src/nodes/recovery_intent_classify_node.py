"""CMN-C2-679 — inner workflow step 1: recovery_intent_classify.

Deterministic classification of which recovery dimensions the query concerns (recovery objective /
checkpoint / idempotency / replay-boundary / session-restoration). The production LLM is reserved for
phrasing only; the dimension classification itself is auditable keyword matching. Propagates any upstream
rejection (`error_code`) so the pipeline degrades to the out-of-scope safe answer.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import RecoveryPatternKB
from src.utils.audit import emit_trace_event


class RecoveryIntentClassifyNode(FunctionNode):
    """Classify the recovery dimensions the query concerns."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        scope = json.loads(state.get("validated_input") or state.get("user_input") or "{}")
        canonical = json.dumps(scope, ensure_ascii=False)
        if state.get("error_code") or not scope.get("query"):
            emit_trace_event(
                "recovery_intent_classify.skip", {"reason": state.get("error_code") or "empty_query"}, state
            )
            intent = {"dimensions": [], "workload": scope.get("workload_hint")}
            return {
                "validated_input": canonical,
                "recovery_intent": json.dumps(intent, ensure_ascii=False),
                "error_code": state.get("error_code") or "INPUT_REJECTED",
                "status": AgentStatus.SUCCESS.value,
            }

        hinted = [d for d in scope.get("recovery_dimensions", []) if d]
        detected = RecoveryPatternKB.classify_intent(scope["query"])
        # Merge caller-hinted dimensions with detected ones (preserve order, dedup).
        dims = list(dict.fromkeys(hinted + detected))
        intent = {"dimensions": dims, "workload": scope.get("workload_hint")}
        emit_trace_event("recovery_intent_classify.complete", {"dimension_count": len(dims)}, state)
        return {
            "validated_input": canonical,
            "recovery_intent": json.dumps(intent, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
