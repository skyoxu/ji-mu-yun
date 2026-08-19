from scripts.python import skill_input_transport as transport

def test_transport_resume_preserves_content_identity():
    plan = transport.plan_transport(32768, 1048576, content_hash="sha256:" + "a" * 64)
    resumed = transport.resume_transport(plan, content_hash="sha256:" + "a" * 64)
    assert resumed["content_hash"] == plan["content_hash"]
