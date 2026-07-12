from __future__ import annotations

from buili_spatial.eval_metrics import evaluate_plan_elements, evaluate_plan_graph


def test_exact_plan_elements_pass() -> None:
    payload = {
        "objects": [{"id": "o1", "kind": "sink", "bbox": [0, 0, 20, 20]}],
        "openings": [{"id": "d1", "kind": "door", "bbox": [20, 0, 40, 10]}],
        "walls": [{"id": "w1", "segment": [0, 0, 100, 0]}],
    }
    result = evaluate_plan_elements(payload, payload)
    assert result["summary"]["macro_f1"] == 1.0
    assert result["summary"]["quality_gate_passed"] is True


def test_mutually_empty_element_classes_are_perfect_not_failures() -> None:
    result = evaluate_plan_elements({"objects": [], "openings": [], "walls": []}, {})
    assert result["summary"]["macro_f1"] == 1.0
    assert result["walls"]["gt_coverage_at_threshold"] == 1.0


def test_exact_plan_graph_passes_product_target(finalized_plan_graph: dict) -> None:
    result = evaluate_plan_graph(finalized_plan_graph, finalized_plan_graph)
    assert result["rooms"]["f1"] == 1.0
    assert result["traceability"]["coverage"] == 1.0
    assert result["quality_gate"]["passed"] is True
