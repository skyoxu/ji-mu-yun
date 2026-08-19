from scripts.python import knowledge_gate_projection as gates

def test_knowledge_gates_keep_stale_catalog_degraded():
    result = gates.project_knowledge_gates(catalog_stale=True, read_set_same=True, source_bytes_same=True)
    assert result["route"] == "degraded-continuation"
    assert result["publication_allowed"] is False

def test_knowledge_gates_refresh_same_selection_source_drift():
    result = gates.project_knowledge_gates(catalog_stale=False, read_set_same=True, source_bytes_same=False)
    assert result["route"] == "successor-refresh"
    assert result["publication_allowed"] is False
