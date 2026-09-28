"""CMN-C2-679 — inner domain workflow graph (Cat 2).

Instantiated by RecoveryDesignWorkflowGraphNode.get_subgraph() in graph.py. Linear topology with
per-node skip guards (the portable Cat 2 form; conditional edges don't propagate across the subgraph
boundary):

    START → recovery_intent_classify → versioned_kb_retrieve → recovery_guidance_synthesize → END

On rejected / 0-hit input, recovery_intent_classify propagates error_code; versioned_kb_retrieve sets
retrieval_hit_count=0 (+error_code); recovery_guidance_synthesize emits the out-of-scope safe answer —
no fabricated recovery guidance.
"""

from __future__ import annotations
from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState

from src.nodes.recovery_guidance_synthesize_node import RecoveryGuidanceSynthesizeNode
from src.nodes.recovery_intent_classify_node import RecoveryIntentClassifyNode
from src.nodes.versioned_kb_retrieve_node import VersionedKbRetrieveNode
from src.schemas.state import State


class RecoveryDesignWorkflow(BaseGraph):
    """Inner graph: intent_classify → kb_retrieve → guidance_synthesize."""

    @property
    def name(self) -> str:
        return "RecoveryDesignWorkflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:
        # No super() — BaseGraph.register_nodes() is abstract.
        self._nodes["recovery_intent_classify"] = RecoveryIntentClassifyNode()
        self._nodes["versioned_kb_retrieve"] = VersionedKbRetrieveNode()
        self._nodes["recovery_guidance_synthesize"] = RecoveryGuidanceSynthesizeNode()

    def add_edges(self) -> None:
        # Static linear backbone; the 0-hit / rejected skip is handled by per-node guards.
        self._sg.add_edge(START, "recovery_intent_classify")
        self._sg.add_edge("recovery_intent_classify", "versioned_kb_retrieve")
        self._sg.add_edge("versioned_kb_retrieve", "recovery_guidance_synthesize")
        self._sg.add_edge("recovery_guidance_synthesize", END)

    def route(self, state: AgentState) -> str:
        """Required by the BaseGraph ABC. Linear topology → not wired to a conditional edge."""
        if state.get("error_code") or state.get("retrieval_hit_count", 0) == 0:
            return "recovery_guidance_synthesize"
        return "versioned_kb_retrieve"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "output": state.get("result"),
            "status": state.get("status"),
            "retrieval_hit_count": state.get("retrieval_hit_count", 0),
            "error_code": state.get("error_code"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
