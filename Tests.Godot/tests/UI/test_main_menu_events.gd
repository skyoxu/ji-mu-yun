extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"

var _bus: Node
var _received := false
var _etype := ""
var _data_json := ""

func before() -> void:
    # Install a temporary EventBus under /root to mimic Autoload
    _bus = preload("res://Game.Godot/Adapters/EventBusAdapter.cs").new()
    _bus.name = "EventBus"
    get_tree().get_root().add_child(auto_free(_bus))
    _bus.connect("DomainEventEmitted", Callable(self, "_on_evt"))

func _on_evt(type, _source, data_json, _id, _spec, _ct, _ts) -> void:
    _received = true
    _etype = str(type)
    _data_json = str(data_json)

func test_main_menu_emits_start() -> void:
    _received = false
    _data_json = ""
    var menu = preload("res://Game.Godot/Scenes/UI/MainMenu.tscn").instantiate()
    add_child(auto_free(menu))
    await get_tree().process_frame
    var btn = menu.get_node("VBox/BtnPlay")
    btn.emit_signal("pressed")
    await get_tree().process_frame
    assert_bool(_received).is_true()
    assert_str(_etype).is_equal("ui.menu.start")

func test_main_menu_emits_default_menu_prototype_payload() -> void:
    _received = false
    _data_json = ""
    var menu = preload("res://Game.Godot/Scenes/UI/MainMenu.tscn").instantiate()
    add_child(auto_free(menu))
    await get_tree().process_frame
    var btn = menu.get_node("VBox/BtnPrototype")
    btn.emit_signal("pressed")
    await get_tree().process_frame
    assert_bool(_received).is_true()
    assert_str(_etype).is_equal("ui.menu.prototype")
    if ResourceLoader.exists("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn"):
        assert_str(_data_json).contains("\"slug\":\"dq-rpg\"")
        assert_str(_data_json).contains("\"scene_path\":\"res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn\"")
    else:
        assert_str(_data_json).contains("\"slug\":\"default-rpg-template\"")
        assert_str(_data_json).contains("\"scene_path\":\"res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn\"")
