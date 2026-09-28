"""CMN-C2-679 — Agent state (AI Agent DR & Stateful Session Recovery Design, Cat 2).

ADR-005: State is a flat TypedDict — never a validation/BaseModel instance. Complex fields are stored
as JSON strings (``NotRequired[str]`` + ``# JSON:``); nodes ``json.dumps`` on write / ``json.loads`` on
read. LangGraph checkpoints use msgpack serialisation, so only plain serialisable fields are allowed and
no credentials/secrets are persisted.

Security / advisory-only design: this template is **read-only and advisory**. It never executes backup /
restore / replay, never triggers a live failover, and never mutates a production system. Inputs are a
question + a **non-confidential** workload description; endpoints / tokens / customer payloads are
redacted at pre_process (S-1/S-2) before anything is written to ``validated_input``.

All agent-specific fields are NotRequired (populated progressively; absent at empty-start invoke).
"""

from __future__ import annotations


from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for the DR & session-recovery design workflow."""

    # ── pre_process (InputValidate: S-1/S-2 validated + redacted request) ─────
    validated_input: str  # JSON: {query, workload_hint, recovery_dimensions[]}
    input_format: str  # "json" | "text" | "empty"
    enriched_context: str  # JSON: {source, channel} (read-only caller context)

    # ── inner workflow (intent_classify → kb_retrieve → guidance_synthesize) ──
    recovery_intent: str  # JSON: {dimensions[], workload}
    retrieved_patterns: str  # JSON: [{pattern_id, dimension, name, version, source, ...}]
    retrieval_hit_count: int  # versioned KB patterns retrieved (0 → out-of-scope safe answer)
    guidance: str  # JSON: [{dimension, approach[], checklist[], citation}]
    result: str  # JSON: assembled Recovery Design Guidance Package

    # ── post_process (S-3 gate + S-4 audit) ──────────────────────────────────
    formatted_output: str  # JSON: final response envelope (package + disclaimer)
    disclaimer: str  # mandatory advisory / DRAFT disclaimer
    audit_logged: bool  # True once the terminal audit event is emitted

    # ── degraded-path signalling (SUCCESS + error_code, never status=ERROR) ──
    error_code: str  # INJECTION_REJECTED | INPUT_REJECTED | INPUT_TOO_LONG | NO_PATTERN
    error_message: str  # operator-facing detail
