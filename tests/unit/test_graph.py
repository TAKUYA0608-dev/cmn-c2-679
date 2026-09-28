# CMN-C2-679 — Unit Tests: Cat 2 graph wiring (outer GraphNode + inner workflow)

import pytest

from src.graph.domain_workflow_graph import RecoveryDesignWorkflow
from src.graph.graph import (
    DisasterRecoveryStatefulSessionRecoveryAgent,
    Graph,
    RecoveryDesignWorkflowGraphNode,
)
from src.schemas.state import State


class TestOuterGraph:
    def test_registry_alias(self):
        assert DisasterRecoveryStatefulSessionRecoveryAgent is Graph

    def test_name_and_state_schema(self):
        g = Graph()
        assert g.name == "DisasterRecoveryStatefulSessionRecoveryAgent"
        assert g.state_schema is State

    def test_main_slot_is_graphnode(self):
        g = Graph()
        g.register_nodes()
        assert isinstance(g._nodes["main"], RecoveryDesignWorkflowGraphNode)
        for slot in ("pre_process", "main", "post_process"):
            assert slot in g._nodes

    def test_error_strategy_propagate(self):
        assert RecoveryDesignWorkflowGraphNode.error_strategy == "propagate"
        assert RecoveryDesignWorkflowGraphNode.propagate_hitl is False

    def test_get_subgraph_is_cached(self):
        node = RecoveryDesignWorkflowGraphNode()
        assert node.get_subgraph() is node.get_subgraph()

    def test_extract_input_prefers_validated(self):
        node = RecoveryDesignWorkflowGraphNode()
        assert node.extract_input({"validated_input": "{}", "user_input": "raw"}) == "{}"

    def test_merge_output_maps_fields(self):
        node = RecoveryDesignWorkflowGraphNode()
        merged = node.merge_output({}, {"output": '{"x":1}', "retrieval_hit_count": 3,
                                        "status": "success", "error_code": None})
        assert merged["result"] == '{"x":1}' and merged["retrieval_hit_count"] == 3
        assert merged["status"] == "success"


class TestInnerWorkflow:
    def test_inner_registers_three_nodes(self):
        wf = RecoveryDesignWorkflow(config={})
        wf.register_nodes()
        for slot in ("recovery_intent_classify", "versioned_kb_retrieve", "recovery_guidance_synthesize"):
            assert slot in wf._nodes

    def test_route_zero_hit_to_synthesize(self):
        wf = RecoveryDesignWorkflow(config={})
        assert wf.route({"retrieval_hit_count": 0}) == "recovery_guidance_synthesize"

    def test_route_error_to_synthesize(self):
        wf = RecoveryDesignWorkflow(config={})
        assert wf.route({"error_code": "NO_PATTERN", "retrieval_hit_count": 2}) == "recovery_guidance_synthesize"

    def test_route_normal_to_retrieve(self):
        wf = RecoveryDesignWorkflow(config={})
        assert wf.route({"retrieval_hit_count": 2}) == "versioned_kb_retrieve"

    def test_get_output_shape(self):
        wf = RecoveryDesignWorkflow(config={})
        out = wf.get_output({"result": "{}", "status": "success", "retrieval_hit_count": 1})
        assert out["output"] == "{}" and out["retrieval_hit_count"] == 1


class TestServerModule:
    def test_server_imports(self):
        try:
            import src.api.server as server
        except ModuleNotFoundError as exc:
            pytest.skip(f"platform module unavailable in the local stub env: {exc}")
        assert server.app is not None and server.agent is not None
