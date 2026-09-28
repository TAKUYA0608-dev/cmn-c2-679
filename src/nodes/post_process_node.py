"""CMN-C2-679 — post_process node: SafetyAndCitationGate (S-3 output gate + S-4 audit).

S-3: verify citation completeness (grounded recovery guidance must cite its versioned KB source) and
append the mandatory **advisory / DRAFT disclaimer** ("consult a human owner; do not apply to production
directly"). S-4: emit an audit event (recovery dimensions / counts only — no PII, no raw query, no
secrets). Runs on both the full guidance package and the out-of-scope safe branch.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.utils.audit import emit_trace_event

_DISCLAIMER = (
    "【DRAFT・助言のみ】本パッケージはバージョン管理された recovery / idempotency / checkpoint-pattern KB に基づく"
    "災害復旧・session 復元の設計助言であり、参考ドラフトです。本エージェントは backup / restore / replay を一切実行せず、"
    "live failover も起動せず、本番設定を一切変更しません。最終的な recovery objective・checkpoint・idempotency 方針・"
    "session 復元計画は、権限を持つ担当者(プラットフォームアーキテクト / SRE)が内容を確認・承認のうえ適用してください。"
)


class PostProcessNode(FunctionNode):
    """Verify citations, append advisory/DRAFT disclaimer, emit audit."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 preservation check: advisory/DRAFT disclaimer present in the output envelope.

        SDK 1.0.0 contract: receives the **result dict from `execute()`**; returns the (possibly
        filtered) result. MAY raise to block an output missing the mandatory disclaimer.
        """
        out = result.get("formatted_output", "")
        if out and "DRAFT" not in out and "助言" not in out:
            raise ValueError("S-3: advisory/DRAFT disclaimer missing from output")
        return dict(result)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        report: dict[str, Any] = json.loads(state.get("result", "{}") or "{}")

        citations = report.get("citations", [])
        grounded = report.get("status_kind") == "guidance"
        citation_complete = (not grounded) or bool(citations)

        formatted = {
            "status_kind": report.get("status_kind"),
            "workload": report.get("workload"),
            "dimensions": report.get("dimensions", []),
            "guidance": report.get("guidance", []),
            "checklist": report.get("checklist", []),
            "citations": citations,
            "citation_complete": citation_complete,
            "message": report.get("message"),
            "disclaimer": _DISCLAIMER,
        }
        emit_trace_event(
            "post_process.complete",
            {
                "status_kind": report.get("status_kind"),
                "dimension_count": len(report.get("guidance", [])),
                "citation_complete": citation_complete,
                "error_code": state.get("error_code"),
            },
            state,
        )
        return {
            "formatted_output": json.dumps(formatted, ensure_ascii=False),
            "disclaimer": _DISCLAIMER,
            "audit_logged": True,
            "status": AgentStatus.SUCCESS.value,
        }
