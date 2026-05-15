extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"

func _spawn_scene():
    var scene := preload("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn").instantiate()
    add_child(auto_free(scene))
    await get_tree().process_frame
    await get_tree().process_frame
    return scene

func test_prototype_scene_instantiates() -> void:
    var scene = await _spawn_scene()
    assert_bool(scene.is_inside_tree()).is_true()

func test_prototype_scene_contains_prototype_loop_node() -> void:
    var scene = await _spawn_scene()
    assert_object(scene.get_node_or_null("PrototypeLoop")).is_not_null()
