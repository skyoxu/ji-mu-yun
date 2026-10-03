extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"

func _client() -> Node:
    var sc = load("res://Game.Godot/Scripts/Security/SecurityHttpClient.cs")
    if sc == null or not sc.has_method("new"):
        push_warning("SKIP: CSharpScript.new() unavailable, skip HTTP block signal test")
        return null
    var c = sc.new()
    add_child(auto_free(c))
    return c


func test_emits_request_blocked_signal_on_denied() -> void:
    var c = _client()
    if c == null:
        return

    # ADR-0025: dictionaries share callback observations across the closure.
    var observed := {"reason": "", "url": "", "count": 0}

    c.RequestBlocked.connect(func(reason: String, url: String) -> void:
        observed["reason"] = reason
        observed["url"] = url
        observed["count"] += 1
    )

    var ok = c.Validate("GET", "http://example.com", "", 0)
    assert_bool(ok).is_false()

    await get_tree().process_frame

    assert_int(observed["count"]).is_equal(1)
    assert_str(observed["reason"]).is_equal("not https")
    assert_str(observed["url"]).is_equal("http://example.com")

