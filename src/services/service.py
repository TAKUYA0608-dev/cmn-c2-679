"""CMN-C2-679 — deterministic domain services (no framework imports).

``RecoveryPatternKB``: a **versioned** knowledge base of AI-agent disaster-recovery / idempotency /
checkpoint patterns (recovery objectives, checkpoint cadence, idempotency keys, replay boundaries,
stateful session restoration) — each record sourced from published resilience-engineering guidance and
carrying a ``version`` for provenance. Retrieval and intent classification are **deterministic**
(keyword/tag scoring + dimension matching) and auditable; the production LLM is reserved for step
phrasing only.

Advisory-only: the KB carries *design guidance* (how to design recovery), never live-failover or
replay-execution instructions. No PII, no credentials, no customer payloads.
"""

from __future__ import annotations

from typing import Any

# ── recovery-design dimensions this template reasons over ─────────────────────
DIMENSIONS = (
    "recovery_objective",  # RTO / RPO
    "checkpoint",  # state snapshot cadence
    "idempotency",  # exactly-once side effects
    "replay_boundary",  # safe re-execution
    "session_restoration",  # stateful session resume
)

# ── versioned recovery-pattern KB (published resilience-engineering guidance) ─
# Each record: {pattern_id, name, dimension, version, source, tags, approach[], checklist[], note}
KB: list[dict[str, Any]] = [
    {
        "pattern_id": "REC-OBJ-001",
        "name": "Recovery Objective Definition (RTO/RPO)",
        "dimension": "recovery_objective",
        "version": "2026.1",
        "source": "Resilience Design Handbook §RTO/RPO (versioned recovery-pattern KB)",
        "tags": [
            "rto",
            "rpo",
            "recovery objective",
            "recovery time",
            "recovery point",
            "downtime",
            "sla",
            "目標復旧時間",
            "復旧目標",
            "許容停止",
            "データ損失",
        ],
        "approach": [
            "対象 agent サービスごとに RTO(復旧までの許容時間)と RPO(許容データ損失)を業務影響から定義する",
            "checkpoint 頻度を RPO から逆算し、RTO を満たす restore 手順の所要時間を見積もる",
            "downstream 依存(LLM/DB/tool)の可用性目標と整合させ、objective を workload 単位で文書化する",
        ],
        "checklist": [
            "RTO/RPO を workload 単位で定義した",
            "checkpoint 頻度が RPO を満たす",
            "restore 所要時間の見積もりが RTO 以内",
        ],
        "note": "objective は設計値であり、本番の failover 実行や監視の設定は行わない(助言のみ)。",
    },
    {
        "pattern_id": "REC-CKP-002",
        "name": "Agent State Checkpointing & Snapshot Cadence",
        "dimension": "checkpoint",
        "version": "2026.1",
        "source": "Resilience Design Handbook §Checkpointing (versioned recovery-pattern KB)",
        "tags": [
            "checkpoint",
            "snapshot",
            "state persistence",
            "checkpoint frequency",
            "graph state",
            "チェックポイント",
            "スナップショット",
            "状態保存",
            "永続化",
            "セーブポイント",
        ],
        "approach": [
            "graph state を冪等に復元できる粒度(node 境界 / メッセージ境界)で checkpoint を取得する",
            "RPO から checkpoint 頻度を決め、部分完了 tool 呼び出しは checkpoint 対象から除外または再実行安全にする",
            "checkpoint schema をバージョン管理し、後方互換な restore 経路を用意する",
        ],
        "checklist": [
            "checkpoint 境界が node/message 単位で定義済",
            "checkpoint 頻度が RPO と整合",
            "checkpoint schema がバージョン管理されている",
        ],
        "note": "checkpoint は state 復元の設計対象。実データの backup/restore 実行は本テンプレの範囲外。",
    },
    {
        "pattern_id": "REC-IDMP-003",
        "name": "Idempotency Keys & Exactly-Once Side Effects",
        "dimension": "idempotency",
        "version": "2026.2",
        "source": "Resilience Design Handbook §Idempotency (versioned recovery-pattern KB)",
        "tags": [
            "idempotency",
            "idempotent",
            "exactly-once",
            "dedup",
            "duplicate",
            "side effect",
            "冪等",
            "冪等性",
            "二重実行",
            "重複実行",
            "副作用",
            "idempotency key",
        ],
        "approach": [
            "外部副作用を伴う tool 呼び出しに idempotency key(request-id/deterministic hash)を付与する",
            "受信側で dedup ストアを設け、同一 key の再実行を exactly-once に収束させる",
            "非冪等な操作は compensating action(取消手順)とセットで設計し、replay 時の二重発火を防ぐ",
        ],
        "checklist": [
            "副作用 tool に idempotency key を付与",
            "dedup ストアで重複を吸収",
            "非冪等操作に compensating action を定義",
        ],
        "note": "idempotency 方針の設計助言であり、実際の tool 実行や取消は行わない。",
    },
    {
        "pattern_id": "REC-RPLY-004",
        "name": "Replay Boundary & Safe Re-execution",
        "dimension": "replay_boundary",
        "version": "2026.1",
        "source": "Resilience Design Handbook §Replay Boundary (versioned recovery-pattern KB)",
        "tags": [
            "replay",
            "re-execution",
            "re-run",
            "replay boundary",
            "safe replay",
            "resume",
            "リプレイ",
            "再実行",
            "再開",
            "二重発火",
            "巻き戻し",
            "in-flight",
        ],
        "approach": [
            "replay 起点を最後の安全な checkpoint に固定し、境界より前の副作用を再実行しない設計にする",
            "境界をまたぐ非同期処理は idempotency key で保護し、部分完了は再実行安全な単位に分割する",
            "replay 範囲(どの node から再開するか)を明示し、外部呼び出しの再送可否を分類する",
        ],
        "checklist": [
            "replay 起点が安全な checkpoint に固定",
            "境界越えの副作用が idempotent",
            "再開 node と再送可否を分類済",
        ],
        "note": "安全な replay 境界の設計助言。live replay の実行はしない。",
    },
    {
        "pattern_id": "REC-SESS-005",
        "name": "Stateful Session Restoration",
        "dimension": "session_restoration",
        "version": "2026.2",
        "source": "Resilience Design Handbook §Session Restoration (versioned recovery-pattern KB)",
        "tags": [
            "session",
            "session restore",
            "restoration",
            "resume session",
            "in-flight tool",
            "セッション復元",
            "セッション復旧",
            "進行中",
            "再開",
            "会話状態",
            "state 復元",
        ],
        "approach": [
            "session を (会話 state + 進行中 tool 呼び出し + 外部 checkpoint 参照) に分解して復元設計する",
            "進行中 tool 呼び出しは idempotency key で保護し、未完了分のみ安全に再実行する",
            "復元後の一貫性(重複メッセージ/欠落 state)を検証する手順を restoration plan に含める",
        ],
        "checklist": [
            "session を state/in-flight/参照に分解",
            "未完了 tool 呼び出しのみ再実行",
            "復元後の一貫性検証手順が定義済",
        ],
        "note": "安全な session 復元の設計助言。実 session の復元操作は行わない。",
    },
    {
        "pattern_id": "REC-DR-006",
        "name": "Multi-Region Failover Topology (design-time)",
        "dimension": "recovery_objective",
        "version": "2026.1",
        "source": "Resilience Design Handbook §DR Topology (versioned recovery-pattern KB)",
        "tags": [
            "failover",
            "disaster recovery",
            "multi-region",
            "region",
            "topology",
            "redundancy",
            "災害復旧",
            "フェイルオーバー",
            "冗長化",
            "リージョン",
            "多重化",
            "dr",
        ],
        "approach": [
            "RTO/RPO から DR トポロジ(active-active / active-passive / pilot-light)を design-time に選定する",
            "state 複製の一貫性モデル(同期/非同期)と RPO の整合を確認する",
            "failover 判定基準と切戻し(failback)手順を文書化する(実行はしない)",
        ],
        "checklist": [
            "DR トポロジが RTO/RPO と整合",
            "state 複製の一貫性モデルを選定",
            "failover/failback 手順を文書化",
        ],
        "note": "DR トポロジの設計助言。live failover の起動は本テンプレの範囲外。",
    },
]

# keyword → dimension map for deterministic intent classification
_DIMENSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "recovery_objective": (
        "rto",
        "rpo",
        "recovery objective",
        "recovery time",
        "recovery point",
        "downtime",
        "sla",
        "目標復旧",
        "復旧目標",
        "許容停止",
        "failover",
        "disaster recovery",
        "災害復旧",
        "フェイルオーバー",
        "冗長",
    ),
    "checkpoint": (
        "checkpoint",
        "snapshot",
        "state persistence",
        "checkpoint frequency",
        "永続化",
        "チェックポイント",
        "スナップショット",
        "状態保存",
        "セーブポイント",
    ),
    "idempotency": (
        "idempotency",
        "idempotent",
        "exactly-once",
        "dedup",
        "duplicate",
        "side effect",
        "冪等",
        "二重実行",
        "重複実行",
        "副作用",
    ),
    "replay_boundary": (
        "replay",
        "re-execution",
        "re-run",
        "replay boundary",
        "safe replay",
        "リプレイ",
        "再実行",
        "二重発火",
        "巻き戻し",
    ),
    "session_restoration": (
        "session",
        "restore",
        "restoration",
        "resume",
        "in-flight",
        "セッション復元",
        "セッション復旧",
        "進行中",
        "会話状態",
        "復元",
    ),
}


class RecoveryPatternKB:
    """Deterministic intent classification + retrieval over the versioned recovery-pattern KB."""

    @staticmethod
    def classify_intent(query: str) -> list[str]:
        """Return the recovery dimensions the query concerns (deterministic keyword match).

        [] when no dimension is recognised (out-of-scope for the recovery-design KB).
        """
        low = (query or "").lower()
        dims: list[str] = []
        for dim in DIMENSIONS:
            if any(kw in low for kw in _DIMENSION_KEYWORDS[dim]):
                dims.append(dim)
        return dims

    @staticmethod
    def retrieve(query: str, dimensions: list[str] | None = None, top_k: int = 4) -> list[dict[str, Any]]:
        """Keyword/tag + dimension scored retrieval. [] when nothing matches (out-of-scope)."""
        q = (query or "").lower()
        dims = set(dimensions or [])
        scored: list[tuple[int, dict[str, Any]]] = []
        for rec in KB:
            score = sum(2 for t in rec["tags"] if t.lower() in q)
            if rec["dimension"] in dims:
                score += 3
            if rec["name"].lower() in q:
                score += 4
            if score:
                scored.append((score, rec))
        scored.sort(key=lambda x: (-x[0], x[1]["pattern_id"]))
        out: list[dict[str, Any]] = []
        for score, rec in scored[:top_k]:
            out.append(
                {
                    "pattern_id": rec["pattern_id"],
                    "name": rec["name"],
                    "dimension": rec["dimension"],
                    "version": rec["version"],
                    "source": rec["source"],
                    "approach": rec["approach"],
                    "checklist": rec["checklist"],
                    "note": rec["note"],
                    "score": score,
                }
            )
        return out
