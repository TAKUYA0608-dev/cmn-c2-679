# CMN-C2-679 — Template Design Specification

> **AI Agent Disaster Recovery & Stateful Session Recovery Q&A Agent** — Cat 2 (design-workflow
> deliverable). Advisory-only, read-only: never executes backup / restore / replay, never triggers a
> live failover, never mutates a production system. Output = a cited **Recovery Design Guidance Package**
> for human review. Scaffolded from the latest scaffold mirror (central-CI include, rtl stubs, PB-7
> conditional stub, setuptools exact pin). This document is the Stage ② design artifact; node bodies land
> in the Stage ③ implementation MR (see **Open Items** below).

## Position in AgentCore Architecture

- **Agent Class**: `DisasterRecoveryStatefulSessionRecoveryAgent` (module-level alias of `Graph`)
- **L1 Base**: `AgentBaseGraph` (L1-direct). `DocGenerationAgent` is a **pattern reference only** (§5/§10
  of the proposal); the implementation inherits `AgentBaseGraph` directly and places a `GraphNode` in the
  `main` slot (Cat 2 GraphNode-in-main; Level 2 base classes are retired — 2026-05-18 PM directive).
- **Category**: Cat 2 — a multi-step DR & session-recovery **design workflow** (job-to-be-done), not a
  single generic capability.
- **Three-Layer Separation**:
  - State: flat `TypedDict` composition (no Pydantic — msgpack incompatible); complex fields are JSON
    strings (ADR-005).
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only — **no
    `config` parameter**, per a review-criteria change).
  - Graph: composition (`register_nodes()` for node substitution); domain complexity is encapsulated in
    the inner workflow graph reached via `main` slot `get_subgraph()`.

## Architecture Overview

### Cat 2 GraphNode-in-main

The outer graph is the fixed 5-slot AgentBaseGraph backbone. Domain complexity lives in the `main` slot,
a `RecoveryDesignWorkflowGraphNode(GraphNode)` that wraps the inner `RecoveryDesignWorkflow(BaseGraph)`
(cached in `self._subgraph`, built once). The inner graph is a **linear pipeline with per-node skip
guards** (conditional edges do not propagate across the subgraph boundary, so branching is done by a
guard at the top of each inner node).

### Node Configuration

| Node | Slot | Responsibility | Input State | Output State | Inherits/Overrides |
|------|------|---------------|-------------|--------------|-------------------|
| initialize | outer | schema_version, session_id, trust_level | user_input | (defaults) | InitializeNode (default) |
| pre_process | outer | **InputValidate** — S-1 NFKC; size cap + prompt-injection handled in `execute()` as degraded `SUCCESS + error_code` (`_extra_security_gate_input` is a no-op, never `status=ERROR`); redact endpoint/token/customer payload; extract `{query, workload_hint, recovery_dimensions}` | user_input | validated_input, input_format, enriched_context, error_code | PreProcessNode (FunctionNode) |
| main | outer | **RecoveryDesignWorkflowGraphNode** — wraps inner workflow; `extract_input`/`merge_output` surface `result` + `retrieval_hit_count` + `error_code` + `status` | validated_input | result, retrieval_hit_count, error_code, status | GraphNode (subgraph) |
| ↳ recovery_intent_classify | inner | classify which recovery dimensions the query concerns (RTO/RPO / checkpoint / idempotency / replay-boundary / session-restoration) | validated_input | recovery_intent | FunctionNode |
| ↳ versioned_kb_retrieve | inner | deterministic retrieval over the versioned recovery/idempotency/checkpoint-pattern KB; sets `retrieval_hit_count`; 0-hit → out-of-scope safe answer | recovery_intent, validated_input | retrieved_patterns, retrieval_hit_count, error_code | FunctionNode |
| ↳ recovery_guidance_synthesize | inner | compose the multi-dimensional Recovery Design Guidance Package + verification checklist, grounded + cited (or the safe answer on 0-hit) | retrieved_patterns, recovery_intent | guidance, result | FunctionNode |
| post_process | outer | **SafetyAndCitationGate** — S-3 sanitize + citation completeness + advisory/DRAFT disclaimer (`_extra_security_gate_output`) + S-4 audit | result | formatted_output, disclaimer, audit_logged | PostProcessNode (FunctionNode) |
| finalize | outer | response_metadata, total_time_ms | formatted_output | (defaults) | FinalizeNode (default) |

### Data Flow

```
START → initialize → pre_process → main(GraphNode) → {route} → post_process → finalize → END
                                          ↓ (retry, max 3)
                                       pre_process

  main(GraphNode) inner workflow (linear + per-node skip guards):
    START → recovery_intent_classify → versioned_kb_retrieve → recovery_guidance_synthesize → END
```

On rejected/empty input `pre_process` sets `error_code` (degraded, `status=SUCCESS`); `versioned_kb_retrieve`
sets `retrieval_hit_count=0`; `recovery_guidance_synthesize` emits the out-of-scope safe answer
(`citations=[]`). No fabricated recovery guidance is ever produced without a grounded KB citation.

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| validated_input | `str` (JSON) | `{query, workload_hint, recovery_dimensions[]}` after S-1/S-2 + redaction | No |
| input_format | `str` | `json` \| `text` \| `empty` | No |
| enriched_context | `str` (JSON) | `{source, channel}` read-only caller context | No |
| recovery_intent | `str` (JSON) | `{dimensions[], workload}` classified intent | No |
| retrieved_patterns | `str` (JSON) | retrieved versioned KB pattern records | No |
| retrieval_hit_count | `int` | KB patterns retrieved (0 → safe answer) | No |
| guidance | `str` (JSON) | per-dimension design blocks (approach + checklist + citation) | No |
| result | `str` (JSON) | assembled Recovery Design Guidance Package | No |
| formatted_output | `str` (JSON) | final envelope (package + disclaimer) | No |
| disclaimer | `str` | mandatory advisory/DRAFT disclaimer | No |
| audit_logged | `bool` | terminal audit event emitted | No |
| error_code | `str` | `INJECTION_REJECTED` \| `INPUT_REJECTED` \| `INPUT_TOO_LONG` \| `NO_PATTERN` | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types); complex fields are JSON strings (ADR-005).
- No JWT, API keys, credentials in State (checkpoint DB leakage) — endpoints/tokens/customer payload are
  redacted at `pre_process` before write.
- InvocationContext via `config["configurable"]` only (not in State).
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible).

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id) — read-only via `input_context`
- [x] S-2: `_extra_security_gate_input()` — **no-op** on `pre_process` (**MUST NOT raise**; returns state
      unchanged). Size cap + prompt-injection markers are enforced in `execute()` as a **degraded
      `status=SUCCESS + error_code`** (`INJECTION_REJECTED` / `INPUT_TOO_LONG`) path: the untrusted body is
      discarded (`validated_input="{}"`) and the request flows to the out-of-scope safe answer, so
      main / post_process (S-3 disclaimer / redaction / S-4 audit) always run. A `status=ERROR` here would
      short-circuit `__call__`, routing straight to `finalize` and skipping main / post_process.
- [x] S-3: `_extra_security_gate_output()` — advisory disclaimer preservation check on `post_process`
      (receives the `execute()` delta; MAY raise to block an output missing the mandatory disclaimer).
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside **every** `execute()`
      (aggregate counts / dimensions only — no PII, no raw query, no secrets).

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (pre/post + 3 inner nodes) → framework `@final` gate always runs; extend via
>   `_extra_security_gate_input()` / `_extra_security_gate_output()` only.
> - `GraphNode` (`main` slot) → deliberate no-op (the inner FunctionNodes' gates already applied).

### Composition Pattern

- **Pattern**: `GraphNode` (subgraph) in the `main` slot wrapping an inner `BaseGraph`.
- **Composition target**: `RecoveryDesignWorkflow` (`src/graph/domain_workflow_graph.py`), cached in
  `self._subgraph`.
- **Error propagation strategy**: `propagate` (`error_strategy="propagate"`, `propagate_hitl=False`).

## Import Isolation Confirmation
- [x] Template does not import agenticstar SDK (Level 0) directly — PB-4.
- [x] Import targets: `framework/` and `src/` only (no `agents/base/` required).

## Security & Advisory-Only Guarantees

- **Read-only / advisory**: no backup / restore / replay execution, no live failover, no production
  connection, no config mutation. Output is a cited recommendation requiring human approval.
- **S-1** input sanitisation (NFKC + control-char strip). **S-2** non-confidential workload description
  only; endpoints / tokens / customer payload are redacted or rejected. **S-3** output sanitize + citation
  completeness + advisory/DRAFT disclaimer. **S-4** audit (dimensions / counts only). **S-5** rate limit
  (framework).
- **Degraded path**: rejected/empty/0-hit paths return `status=SUCCESS` + `error_code` (never
  `status=ERROR` from `execute()`, which would skip post_process/S-3/S-4 on the real SDK).

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step design workflow, no autonomous reasoning loop. |
| Composition pattern | Standalone FunctionNode in main | GraphNode-in-main (subgraph) | **GraphNode-in-main** | Cat 2 requires domain complexity encapsulated in an inner workflow graph. |
| Inner topology | conditional edges | linear + per-node skip guards | **linear + skip guards** | Conditional edges do not propagate across the subgraph boundary. |
| Intent classify / synthesize | free-form LLM | deterministic core + LLM reserved for phrasing | **deterministic core** | Auditable, reproducible; LLM reserved for step phrasing only. |

## Open Items (Stage ③ implementation plan)

The following land in the Stage ③ implementation MR (this design MR ships `docs/02_design.md` +
`src/schemas/state.py` only):

1. `src/nodes/pre_process_node.py` — InputValidate (S-1/S-2 + endpoint/token/payload redaction).
2. `src/graph/graph.py` — outer graph + `RecoveryDesignWorkflowGraphNode` (subgraph cache) + alias.
3. `src/graph/domain_workflow_graph.py` — inner `RecoveryDesignWorkflow` (linear + guards).
4. `src/nodes/recovery_intent_classify_node.py`, `versioned_kb_retrieve_node.py`,
   `recovery_guidance_synthesize_node.py` — inner steps.
5. `src/services/service.py` — `RecoveryPatternKB` (versioned, deterministic retrieve + intent classify).
6. `src/nodes/post_process_node.py` — SafetyAndCitationGate (S-3 + S-4).
7. `src/utils/audit.py` — S-4 audit shim (platform logger + stderr fallback).
8. `config/agent.yaml`, `README.md` — Cat 2 / CMN / L1-direct alignment.
9. `docs/03_test_spec.md`, `docs/07_operation_guide.md`, and unit/integration tests (cov ≥ 89%).
