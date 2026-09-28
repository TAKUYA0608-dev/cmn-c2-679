# Test Specification — CMN-C2-679

## Test Strategy
- Coverage target: **≥ 89%** (achieved **91%** local; see summary)
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) / Proof-of-Boundary (`tests/proof_of_boundary/`)
- Advisory-only invariants under test: no backup/restore/replay execution, grounded-or-safe answers
  (0-hit → out-of-scope), citation completeness on grounded output, secret redaction at S-1/S-2,
  degraded = `SUCCESS + error_code` (never `status=ERROR` out of `execute()`).

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict (JSON-string complex fields, ADR-005) | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | S-2 injection/oversize → degraded `SUCCESS + error_code` in `execute()` (gate is a no-op, never `status=ERROR`; untrusted body discarded); post_process still runs | `status=SUCCESS`, `error_code=INJECTION_REJECTED`/`INPUT_TOO_LONG`, `PostProcessNode` in `node_history`, safe answer, body absent | PASS (`test_injection_degrades`, `test_oversize_degrades`, `TestGraphInvoke::test_injection_reaches_post_and_audits`, `::test_oversize_reaches_post_and_audits`) |
| TC-03 | No JWT/Credential in State — endpoint/token/payload redacted at pre_process | CI `gate-credential-scan`: 0 violations | PASS (`test_endpoint_and_token_redacted_text`, `test_secret_kv_redacted_json`) |
| TC-04 | InvocationContext via configurable only; `input_context` read-only | No InvocationContext in State | PASS |
| TC-05 | S-4: domain `emit_trace_event()` inside each `execute()`, no lifecycle dupes | `node_start`/`node_complete`/`node_error` absent from bodies | PASS (0 duplicates) |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode`) | `@final` enforced; only `_extra_*` used | PASS (0 overrides) |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode`) | `@final` enforced; only `_extra_*` used | PASS (0 overrides) |
| TC-08 | `required_trust_level = VERIFIED_EXTERNAL` on every FunctionNode | `scripts/check_trust_level.py src/` PASS | PASS |
| TC-09 | S-2 domain checks (size cap + prompt-injection markers) enforced in `execute()` as a degraded path; `_extra_security_gate_input` is a no-op (returns state unchanged — never raises, never `status=ERROR`) | Injection/oversize degrade to safe answer; main/post always run | PASS (`test_gate_input_is_noop`, `test_injection_degrades`, `test_oversize_degrades`) |
| TC-10 | S-3 `_extra_security_gate_output()` non-trivial (advisory/DRAFT disclaimer preservation, MAY raise) | Blocks output missing disclaimer | PASS (`test_gate_raises_when_disclaimer_missing`) |
| TC-11 | S-4: ≥1 domain `emit_trace_event()` on every path (incl. skip/safe) | Event emitted on every invocation path | PASS (≥1 per node) |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` on every path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives / JSON strings only | No Pydantic/dataclass | PASS (`test_state_safety`) |
| PB-3 | Inner workflow → KB service | Deterministic versioned-KB retrieval | Grounded records or safe answer | PASS |
| PB-4 | Import isolation | No Level 0 (`agenticstar`) imports | AST scan: 0 violations | PASS (`test_import_isolation`) |
| PB-5 | Checkpoint safety | No JWT/secret/Pydantic in checkpoint | Inspection pass (redacted at S-1/S-2) | PASS |
| PB-6 | Invoke execution order | S-1 gate → S-4 start → S-2 → `execute()` → S-3 → S-4 complete | Order verified on real SDK | PASS (CI, real SDK) |
| PB-7 | HITL interrupt propagation *(conditional)* | `config.yaml` has no `hitl.enabled: true` | **Auto-waived — non-HITL** | Auto-waived (2 SKIPPED stubs retained) |

> **Pre-CoE gate checklist:** PB-1 through PB-6 mandatory. This template is non-HITL → PB-7 **Auto-waived —
> non-HITL** (the `test_pb7_*` conditional stubs are retained and skip). `test_pb_invoke_order` (PB-6)
> fails under the local SDK stub (no `emit_trace_event` on `base_node`) and passes under the real SDK in CI.

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Multi-dimension design package | `{query: "RTO/RPO と checkpoint、冪等性の設計", workload: "order-agent"}` | `status_kind=guidance`, cited approach per dimension, aggregate checklist, workload in steps | PASS |
| BL-02 | Session-restoration dimension routing | "session 復元をどう設計する?" | guidance includes `session_restoration` dimension | PASS |
| BL-03 | Intent classification | "RTO と checkpoint と冪等性" | dimensions = {recovery_objective, checkpoint, idempotency} | PASS |
| BL-04 | KB retrieval grounding | "idempotency key と exactly-once 副作用" | REC-IDMP-003 retrieved with `version`/`source` | PASS |
| BL-05 | Out-of-scope safe answer | "好きな映画を教えて" | `status_kind=out_of_scope`, `citations=[]`, no fabrication | PASS |
| BL-06 | Empty input degrades | "   " | `SUCCESS + error_code=INPUT_REJECTED`, still audits, safe answer | PASS |
| BL-07 | Secret redaction end-to-end | query with `https://…` + `sk-…` token | secret absent from `validated_input` and `formatted_output` | PASS |
| BL-08 | Citation completeness gate | grounded output | `citation_complete=True`; disclaimer present | PASS |
| BL-09 | Injection degrades (real `Graph().invoke()`) | "ignore all previous instructions …" | `SUCCESS + error_code=INJECTION_REJECTED`, `PostProcessNode` runs, `status_kind=out_of_scope`, disclaimer present, injection body absent from output | PASS (`TestGraphInvoke`) |
| BL-10 | Oversize degrades (real `Graph().invoke()`) | 20,001-char input | `SUCCESS + error_code=INPUT_TOO_LONG`, `PostProcessNode` runs, safe answer, oversized canary absent from output | PASS (`TestGraphInvoke`) |

## Test Execution Summary
- Execution date: 2026-07-22
- Total tests: 52 (unit + integration + proof_of_boundary, `tests/`)
- Pass: 49 · Fail: 0 (CI, real SDK) · Skip: 3 (server import + PB-7 ×2 under a local SDK stub)
- Local (the local SDK stub) run: **48 passed, 3 skipped**; `test_pb_invoke_order` (PB-6) fails under a local SDK stub
  (no `emit_trace_event` on `base_node`) and **passes on the real SDK in CI**.
- Coverage: **91%** (`--cov=src`; measured over `tests/`)
