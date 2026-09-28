"""CMN-C2-679 — inner workflow step 2: versioned_kb_retrieve.

Deterministic retrieval over the **versioned** recovery/idempotency/checkpoint-pattern KB. Sets
`retrieval_hit_count`; **0 hits (rejected input or no match) routes to the out-of-scope safe answer** —
the agent never fabricates recovery guidance that is not grounded in a versioned KB pattern with a
citation. No-ops (guard) on the rejected / empty branch.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import RecoveryPatternKB
from src.utils.audit import emit_trace_event


class VersionedKbRetrieveNode(FunctionNode):
    """Retrieve grounded, versioned recovery-pattern records for the query + intent."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        scope = json.loads(state.get("validated_input") or "{}")
        intent = json.loads(state.get("recovery_intent") or "{}")
        query = scope.get("query")
        if state.get("error_code") or not query:
            emit_trace_event("versioned_kb_retrieve.skip", {"reason": state.get("error_code") or "empty_query"}, state)
            return {
                "retrieved_patterns": "[]",
                "retrieval_hit_count": 0,
                "error_code": state.get("error_code") or "NO_PATTERN",
                "status": AgentStatus.SUCCESS.value,
            }

        patterns = RecoveryPatternKB.retrieve(query, dimensions=intent.get("dimensions"))
        emit_trace_event("versioned_kb_retrieve.complete", {"hit_count": len(patterns)}, state)
        out = {
            "retrieved_patterns": json.dumps(patterns, ensure_ascii=False),
            "retrieval_hit_count": len(patterns),
            "status": AgentStatus.SUCCESS.value,
        }
        if not patterns:
            out["error_code"] = "NO_PATTERN"
        return out
