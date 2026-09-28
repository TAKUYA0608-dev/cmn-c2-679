"""CMN-C2-679 — pre_process node: InputValidate (S-1 input validation + S-2 redaction + slot extraction).

Accepts a structured JSON request (`{query, workload, recovery_dimensions?}`) or NL text, normalizes it
(NFKC), applies S-1/S-2 domain checks (size cap + prompt-injection markers), and extracts
`{query, workload_hint, recovery_dimensions}`. **Advisory / read-only**: endpoints, bearer tokens, API
keys and long secret-like runs are **redacted** before the query is persisted to State
(`validated_input`) so no confidential payload ever enters the checkpoint DB.

All rejects (prompt-injection / empty / oversize) return `status=SUCCESS + error_code` (degraded, NOT
`status=ERROR`) — the untrusted body is discarded and the request flows to the out-of-scope safe answer,
so main / post_process (disclaimer / redaction / S-4 audit) always run. `_extra_security_gate_input` is a
no-op that returns state unchanged (a `status=ERROR` there would short-circuit `__call__` and skip
main / post_process).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.utils.audit import emit_trace_event

_MAX_INPUT = 20_000
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard the above",
    "system prompt",
    "you are now",
    "###system",
    "<|im_start|>",
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# S-2 defense-in-depth: redact endpoint/token/customer-payload secrets a caller may inadvertently
# include in a workload description, before the query is written to State (`validated_input`).
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"https?://[^\s\"'<>]+"), "[ENDPOINT-REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[JWT-REDACTED]"),  # JWT
    (re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9]{16,}"), "[TOKEN-REDACTED]"),  # API key
    (re.compile(r"\bAKIA[0-9A-Z]{12,}"), "[AWS-KEY-REDACTED]"),  # AWS
    (re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password|bearer)\b\s*[:=]\s*\S+"), "[SECRET-REDACTED]"),
)


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _sanitize(text: str) -> str:
    """Strip control chars (S-1) and redact endpoint/token/customer-payload secrets (S-2)."""
    clean = _CONTROL.sub("", text or "")
    for pattern, mask in _REDACTIONS:
        clean = pattern.sub(mask, clean)
    return clean


class PreProcessNode(FunctionNode):
    """Validate the recovery-design request, redact secrets, and extract the analysis slots."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain hook — no hard reject.

        SDK 1.0.0 contract: MUST NOT raise. Prompt-injection and oversize are handled as a degraded
        `status=SUCCESS + error_code` path in `execute()` (the untrusted content is never processed) so
        main / post_process S-3/S-4 always run. A `status=ERROR` here would short-circuit `__call__` and
        skip main / post_process — the disclaimer / redaction / audit would never run.
        The framework default S-2 masking still applies. Returns state unchanged.
        """
        return dict(state)

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "") or ""
        input_context = state.get("input_context", {})  # read-only [C1]
        enriched = json.dumps(
            {
                "source": "DisasterRecoveryStatefulSessionRecoveryAgent",
                "channel": input_context.get("channel", "unknown"),
            },
            ensure_ascii=False,
        )
        normalized = _nfkc(raw).strip()

        # Prompt-injection -> degraded SUCCESS + error_code (never processed). NOT status=ERROR: ERROR
        # short-circuits __call__ so main / post_process (disclaimer / redaction / audit) would be
        # skipped. The untrusted body is discarded; the safe-answer path runs.
        if any(marker in normalized.lower() for marker in _INJECTION_MARKERS):
            emit_trace_event("input_validate.rejected", {"reason": "prompt_injection"}, state)
            return {
                "validated_input": "{}",
                "input_format": "rejected",
                "enriched_context": enriched,
                "error_code": "INJECTION_REJECTED",
                "error_message": "prompt-injection marker detected; input not processed",
                "status": AgentStatus.SUCCESS.value,
            }

        if not raw.strip():
            emit_trace_event("input_validate.rejected", {"reason": "empty_input"}, state)
            return {
                "validated_input": "{}",
                "input_format": "empty",
                "enriched_context": enriched,
                "error_code": "INPUT_REJECTED",
                "error_message": "no recovery-design question submitted",
                "status": AgentStatus.SUCCESS.value,
            }

        # Oversize -> degraded SUCCESS + error_code (body discarded, not ERROR — post_process must run).
        if len(normalized) > _MAX_INPUT:
            emit_trace_event("input_validate.rejected", {"reason": "oversize"}, state)
            return {
                "validated_input": "{}",
                "input_format": "oversize",
                "enriched_context": enriched,
                "error_code": "INPUT_TOO_LONG",
                "error_message": f"input exceeds {_MAX_INPUT} chars",
                "status": AgentStatus.SUCCESS.value,
            }

        scope, fmt = self._parse(normalized)
        emit_trace_event(
            "input_validate.validated",
            {"input_format": fmt, "dimension_hint_count": len(scope["recovery_dimensions"])},
            state,
        )
        return {
            "validated_input": json.dumps(scope, ensure_ascii=False),
            "input_format": fmt,
            "enriched_context": enriched,
            "status": AgentStatus.SUCCESS.value,
        }

    def _parse(self, text: str) -> tuple[dict[str, Any], str]:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                query = str(obj.get("query") or obj.get("question") or "")
                workload = obj.get("workload") or obj.get("workload_hint")
                dims = obj.get("recovery_dimensions")
                dims = [str(d) for d in dims] if isinstance(dims, list) else []
                return {
                    "query": _sanitize(query),
                    "workload_hint": _sanitize(str(workload)) if workload else None,
                    "recovery_dimensions": dims,
                }, "json"
        except (ValueError, TypeError):
            pass
        clean = _sanitize(text)
        return {"query": clean, "workload_hint": None, "recovery_dimensions": []}, "text"
