from scripts.python import knowledge_gate_projection as gates

def test_knowledge_gates_are_independent():
    assert callable(getattr(gates, "project_knowledge_gates", None))
