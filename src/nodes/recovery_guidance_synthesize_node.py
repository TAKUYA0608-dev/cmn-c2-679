"""CMN-C2-679 — inner workflow step 3: recovery_guidance_synthesize.

Composes the multi-dimensional **Recovery Design Guidance Package** — per retrieved recovery dimension:
recommended design approach, a verification checklist, and a versioned source citation — plus an
aggregate verification checklist across dimensions. Grounded in the versioned KB; on the 0-hit / rejected
branch it emits the out-of-scope safe answer with no fabricated guidance (`citations=[]`).

Advisory-only: the package is a *design deliverable* for human review; it never executes backup /
restore / replay and never triggers a live failover.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.utils.audit import emit_trace_event

_OUT_OF_SCOPE = (
    "ご質問に該当する災害復旧 / session 復元の設計パターンが、バージョン管理された recovery / idempotency / "
    "checkpoint-pattern KB(recovery objective(RTO/RPO)/ checkpoint / idempotency / replay 境界 / "
    "session 復元)に見つかりませんでした。関心のある recovery 次元(例: RTO/RPO・checkpoint・冪等性・replay 境界・"
    "session 復元)を具体化してご質問ください。"
)


class RecoveryGuidanceSynthesizeNode(FunctionNode):
    """Compose the cited multi-dimensional Recovery Design Guidance Package (or safe answer on 0-hit)."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        patterns = json.loads(state.get("retrieved_patterns") or "[]")
        if state.get("error_code") or not patterns:
            emit_trace_event(
                "recovery_guidance_synthesize.safe", {"reason": state.get("error_code") or "no_pattern"}, state
            )
            report: dict[str, Any] = {
                "status_kind": "out_of_scope",
                "message": _OUT_OF_SCOPE,
                "guidance": [],
                "checklist": [],
                "citations": [],
            }
            return {"result": json.dumps(report, ensure_ascii=False), "status": AgentStatus.SUCCESS.value}

        intent = json.loads(state.get("recovery_intent") or "{}")
        workload = intent.get("workload")
        guidance: list[dict[str, Any]] = []
        citations: list[dict[str, str]] = []
        checklist: list[str] = []
        for p in patterns:
            steps = list(p["approach"])
            if workload:
                steps = [f"対象 workload: {workload}"] + steps
            block = {
                "dimension": p["dimension"],
                "pattern_id": p["pattern_id"],
                "name": p["name"],
                "approach": steps,
                "checklist": p["checklist"],
                "note": p["note"],
                "citation": {"source": p["source"], "version": p["version"], "pattern_id": p["pattern_id"]},
            }
            guidance.append(block)
            citations.append({"pattern_id": p["pattern_id"], "source": p["source"], "version": p["version"]})
            checklist.extend(p["checklist"])

        report = {
            "status_kind": "guidance",
            "workload": workload,
            "dimensions": [g["dimension"] for g in guidance],
            "guidance": guidance,
            "checklist": list(dict.fromkeys(checklist)),  # aggregate verification checklist (dedup)
            "citations": citations,
        }
        emit_trace_event(
            "recovery_guidance_synthesize.complete",
            {"dimension_count": len(guidance), "citation_count": len(citations)},
            state,
        )
        return {
            "result": json.dumps(report, ensure_ascii=False),
            "guidance": json.dumps(guidance, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
