extends "res://addons/gdUnit4/src/GdUnitTestSuite.gd"

func _spawn_scene():
    var scene := preload("res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn").instantiate()
    add_child(auto_free(scene))
    await get_tree().process_frame
    await get_tree().process_frame
    return scene

func test_he_is_coming_scene_instantiates() -> void:
    var scene = await _spawn_scene()
    assert_bool(scene.is_inside_tree()).is_true()

func test_he_is_coming_scene_contains_prototype_loop_node() -> void:
    var scene = await _spawn_scene()
    assert_object(scene.get_node_or_null("PrototypeLoop")).is_not_null()

func test_he_is_coming_scene_uses_split_map_and_battle_scene_roots() -> void:
    var scene = await _spawn_scene()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/TimerPanel/TimerMargin/TimerLabel")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/RewardPanel")).is_not_null()

func test_he_is_coming_scene_keeps_map_info_header_inside_viewport() -> void:
    var scene = await _spawn_scene()
    var viewport = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport")
    var timer_panel = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/TimerPanel")

    assert_that(timer_panel.get_global_rect().position.y).is_greater_equal(viewport.get_global_rect().position.y)

func test_he_is_coming_scene_keeps_map_frame_tight_to_600_grid_and_clips_background() -> void:
    var scene = await _spawn_scene()
    var track = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track")
    var track_root = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot")
    var map_background = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/MapBackground")

    assert_bool(track.clip_contents).is_true()
    assert_bool(track_root.clip_contents).is_true()
    assert_that(track_root.size.x).is_equal(600.0)
    assert_that(track_root.size.y).is_equal(600.0)
    assert_that(map_background.position.x).is_equal(0.0)
    assert_that(map_background.position.y).is_equal(0.0)

func test_he_is_coming_scene_replaces_placeholder_blocks_with_sprite_overlays() -> void:
    var scene = await _spawn_scene()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken/PlayerTokenSprite")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/RewardChest/RewardChestSprite")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor/PlayerActorSprite")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor/EnemyActorSprite")).is_not_null()

func test_he_is_coming_scene_adds_floor_tiles_and_map_decor_layers_for_visual_polish() -> void:
    var scene = await _spawn_scene()
    await get_tree().process_frame
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Floor_0_0")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Floor_11_11")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Shadow_0_0")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Backdrop_1_0")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/River_5_5")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Castle_8_2")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor/PlayerActorMargin/PlayerActorVBox/PlayerActorHpBar")).is_not_null()
    assert_object(scene.get_node_or_null("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor/EnemyActorMargin/EnemyActorVBox/EnemyActorHpBar")).is_not_null()

func test_he_is_coming_scene_draws_clear_overworld_bounds_for_showcase_map() -> void:
    var scene = await _spawn_scene()
    var right_edge = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/MapEdgeRight")
    var right_shade = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/MapEdgeRightShade")
    var top_edge = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/MapEdgeTop")

    assert_bool(right_edge.visible).is_true()
    assert_bool(right_shade.visible).is_true()
    assert_bool(top_edge.visible).is_true()
    assert_that(right_edge.color.a).is_greater(top_edge.color.a)
    assert_that(right_shade.size.x).is_greater(right_edge.size.x)

func test_he_is_coming_scene_emphasizes_map_player_token_with_outline_shadow_and_pulse() -> void:
    var scene = await _spawn_scene()
    var player_token = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken")
    var player_sprite = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken/PlayerTokenSprite")
    var player_outline = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken/PlayerTokenOutline")
    var player_shadow = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken/PlayerTokenShadow")

    assert_that(player_sprite.custom_minimum_size.x).is_greater(32.0)
    assert_bool(player_outline.visible).is_true()
    assert_bool(player_shadow.visible).is_true()

    var base_scale: Vector2 = player_token.scale
    var base_outline_modulate: Color = player_outline.modulate

    scene.AdvanceUiAnimationForTest(0.30)
    await get_tree().process_frame

    assert_bool(player_token.scale != base_scale).is_true()
    assert_bool(player_outline.modulate != base_outline_modulate).is_true()

func test_he_is_coming_scene_highlights_path_and_animates_hud_values() -> void:
    var scene = await _spawn_scene()
    var floor_tile = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Floor_0_0")
    var player_hp = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor/PlayerActorMargin/PlayerActorVBox/PlayerActorHpBar")
    var enemy_hp = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor/EnemyActorMargin/EnemyActorVBox/EnemyActorHpBar")

    assert_bool(floor_tile.modulate != Color(1, 1, 1, 1)).is_true()

    scene.StartEncounterForTest()
    await get_tree().process_frame

    assert_float(float(player_hp.value)).is_greater(0.0)
    assert_float(float(enemy_hp.value)).is_greater(0.0)

func test_he_is_coming_scene_starts_on_map_without_battle_overlay() -> void:
    var scene = await _spawn_scene()
    var map_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene")
    var battle_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("map")
    assert_bool(map_scene.visible).is_true()
    assert_bool(battle_scene.visible).is_false()

func test_he_is_coming_scene_exposes_grid_map_state() -> void:
    var scene = await _spawn_scene()
    assert_int(scene.GetMapGridSizeForTest()).is_equal(12)
    assert_int(scene.GetMapCellSizeForTest()).is_equal(50)
    assert_int(scene.GetChestCountForTest()).is_greater_equal(1)
    assert_int(scene.GetObstacleCountForTest()).is_equal(0)

func test_he_is_coming_scene_allows_showcase_map_movement_to_right_edge() -> void:
    var scene = await _spawn_scene()
    var start: Vector2i = scene.GetPlayerGridPositionForTest()

    for _i in range(12):
        var move_event := InputEventKey.new()
        move_event.pressed = true
        move_event.keycode = KEY_D
        Input.parse_input_event(move_event)
        await get_tree().process_frame

    var finish: Vector2i = scene.GetPlayerGridPositionForTest()
    assert_that(finish.y).is_equal(start.y)
    assert_that(finish.x).is_equal(11)

func test_he_is_coming_scene_idle_does_not_increase_encounter_progress() -> void:
    var scene = await _spawn_scene()
    var timer_label = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/TimerPanel/TimerMargin/TimerLabel")

    scene.AdvanceMapTime(10.0)
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("map")
    assert_str(str(timer_label.text)).contains("0格")
    assert_str(str(timer_label.text)).contains("0%")

func test_he_is_coming_scene_collects_chest_then_returns_to_map_after_reward_pick() -> void:
    var scene = await _spawn_scene()
    var reward_panel = scene.get_node("CanvasLayer/UIRoot/RewardPanel")
    var chests_before: int = int(scene.GetChestCountForTest())

    scene.MovePlayerToChestForTest()
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("reward")
    assert_bool(reward_panel.visible).is_true()

    scene.ChooseRewardForTest(0)
    await get_tree().process_frame
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("map")
    assert_bool(reward_panel.visible).is_false()
    assert_int(scene.GetChestCountForTest()).is_equal(chests_before - 1)

func test_he_is_coming_scene_battle_switch_hides_map_scene() -> void:
    var scene = await _spawn_scene()
    var map_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene")
    var battle_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")

    scene.StartEncounterForTest()
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")
    assert_bool(map_scene.visible).is_false()
    assert_bool(battle_scene.visible).is_true()

func test_he_is_coming_scene_resets_content_transform_after_encounter_transition() -> void:
    var scene = await _spawn_scene()
    var content = scene.get_node("CanvasLayer/UIRoot/Content")

    scene.StartEncounterForTest()
    await get_tree().create_timer(0.30).timeout
    await get_tree().process_frame

    assert_that(content.scale.x).is_equal(1.0)
    assert_that(content.scale.y).is_equal(1.0)
    assert_that(content.position.x).is_equal(0.0)
    assert_that(content.position.y).is_equal(0.0)

func test_he_is_coming_scene_reveals_one_battle_log_line_per_second_and_only_resolves_after_all_lines() -> void:
    var scene = await _spawn_scene()
    var battle_log = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog")

    scene.StartEncounterForTest()
    await get_tree().process_frame

    assert_int(_non_empty_line_count(str(battle_log.text))).is_equal(1)

    scene.AdvanceBattlePresentationForTest(0.90)
    await get_tree().process_frame
    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")
    assert_int(_non_empty_line_count(str(battle_log.text))).is_equal(1)

    scene.AdvanceBattlePresentationForTest(0.10)
    await get_tree().process_frame
    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")
    assert_int(_non_empty_line_count(str(battle_log.text))).is_equal(2)

    scene.AdvanceBattlePresentationForTest(3.00)
    await get_tree().process_frame
    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")
    assert_int(_non_empty_line_count(str(battle_log.text))).is_equal(5)

    scene.AdvanceBattlePresentationForTest(1.00)
    await get_tree().process_frame
    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")
    assert_int(_non_empty_line_count(str(battle_log.text))).is_equal(6)

    scene.AdvanceBattlePresentationForTest(1.00)
    await get_tree().process_frame
    assert_str(str(scene.GetScenePhaseForTest())).is_equal("reward")

func test_he_is_coming_scene_keeps_battle_view_visible_when_result_panel_shows() -> void:
    var scene = await _spawn_scene()
    var battle_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")
    var player_actor = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor")
    var battle_log = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog")
    var result_panel = scene.get_node("CanvasLayer/UIRoot/ResultPanel")

    scene.ForceVictoryForTest()
    await get_tree().process_frame

    assert_bool(battle_scene.visible).is_true()
    assert_bool(player_actor.visible).is_true()
    assert_bool(battle_log.visible).is_true()
    assert_bool(result_panel.get_global_rect().intersects(battle_log.get_global_rect())).is_false()

    scene.ForceGameOverForTest()
    await get_tree().process_frame

    assert_bool(battle_scene.visible).is_true()
    assert_bool(player_actor.visible).is_true()
    assert_bool(battle_log.visible).is_true()
    assert_bool(result_panel.get_global_rect().intersects(battle_log.get_global_rect())).is_false()

func test_he_is_coming_scene_keeps_battle_backdrop_out_of_status_and_log_regions() -> void:
    var scene = await _spawn_scene()
    var encounter_type = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/EncounterTypePanel")
    var battle_log = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame")
    var battle_actors_frame = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame")
    var battle_backdrop = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleBackdropBand/BattleBackdrop")

    scene.StartEncounterForTest()
    await get_tree().process_frame

    assert_bool(battle_backdrop.visible).is_true()
    assert_bool(battle_backdrop.get_global_rect().intersects(encounter_type.get_global_rect())).is_false()
    assert_bool(battle_backdrop.get_global_rect().intersects(battle_log.get_global_rect())).is_false()
    assert_that(battle_backdrop.get_global_rect().size.y).is_less(battle_actors_frame.get_global_rect().size.y)

func test_he_is_coming_scene_enters_reward_phase_after_battle_resolution() -> void:
    var scene = await _spawn_scene()
    var reward_panel = scene.get_node("CanvasLayer/UIRoot/RewardPanel")
    var battle_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")
    var battle_log = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog")

    scene.StartEncounterForTest()
    await get_tree().process_frame
    scene.AdvanceBattleFlowForTest()
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("reward")
    assert_bool(reward_panel.visible).is_true()
    assert_bool(battle_scene.visible).is_true()
    assert_bool(battle_log.visible).is_true()

func test_he_is_coming_scene_returns_to_map_and_refreshes_chest_after_battle_reward() -> void:
    var scene = await _spawn_scene()
    var chests_before: int = int(scene.GetChestCountForTest())
    var map_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene")
    var battle_scene = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene")

    scene.StartEncounterForTest()
    await get_tree().process_frame
    scene.AdvanceBattleFlowForTest()
    await get_tree().process_frame
    scene.ChooseRewardForTest(1)
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("map")
    assert_bool(map_scene.visible).is_true()
    assert_bool(battle_scene.visible).is_false()
    assert_int(scene.GetChestCountForTest()).is_less_equal(5)
    assert_int(scene.GetChestCountForTest()).is_greater_equal(_min_int(chests_before + 1, 5))

func test_he_is_coming_scene_marks_elite_and_boss_encounters_visually() -> void:
    var scene = await _spawn_scene()
    var encounter_type_label = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/EncounterTypePanel/EncounterTypeMargin/EncounterTypeLabel")

    scene.SetStepIndexForTest(5)
    scene.StartEncounterForTest()
    await get_tree().process_frame
    assert_str(str(encounter_type_label.text)).contains("精英")

    scene.SetStepIndexForTest(15)
    scene.StartEncounterForTest()
    await get_tree().process_frame
    assert_str(str(encounter_type_label.text)).contains("首领")

func test_he_is_coming_scene_reveals_battle_log_progressively_during_battle_phase() -> void:
    var scene = await _spawn_scene()
    var battle_log = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog")

    scene.StartEncounterForTest()
    await get_tree().process_frame

    var log_at_start := str(battle_log.text)
    scene.AdvanceBattlePresentationForTest(1.00)
    await get_tree().process_frame
    var log_after_one_second := str(battle_log.text)

    assert_int(_non_empty_line_count(log_at_start)).is_equal(1)
    assert_int(_non_empty_line_count(log_after_one_second)).is_equal(2)
    assert_bool(log_after_one_second.length() > log_at_start.length()).is_true()

func test_he_is_coming_scene_flashes_player_then_enemy_actor_during_battle_presentation() -> void:
    var scene = await _spawn_scene()
    var player_actor = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor")
    var enemy_actor = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor")

    scene.StartEncounterForTest()
    await get_tree().process_frame

    var player_base: Color = player_actor.color
    var enemy_base: Color = enemy_actor.color

    scene.AdvanceBattlePresentationForTest(1.15)
    await get_tree().process_frame
    var player_flash: Color = player_actor.color
    var enemy_before_counter: Color = enemy_actor.color

    scene.AdvanceBattlePresentationForTest(3.40)
    await get_tree().process_frame
    var enemy_flash: Color = enemy_actor.color

    assert_bool(player_flash != player_base).is_true()
    assert_bool(enemy_before_counter == enemy_base).is_true()
    assert_bool(enemy_flash != enemy_base).is_true()

func test_he_is_coming_scene_updates_sidebar_with_current_build_direction_after_reward_pick() -> void:
    var scene = await _spawn_scene()
    var build_label = scene.get_node("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/BuildDirectionPanel/BuildDirectionMargin/BuildDirection")

    scene.StartEncounterForTest()
    await get_tree().process_frame
    scene.AdvanceBattleFlowForTest()
    await get_tree().process_frame
    scene.ChooseRewardForTest(2)
    await get_tree().process_frame

    assert_str(str(build_label.text)).contains("猎手")
    assert_str(str(build_label.text)).contains("暴击")

func test_he_is_coming_scene_tracks_build_history_icons_in_sidebar() -> void:
    var scene = await _spawn_scene()
    var build_history = scene.get_node("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/BuildHistoryPanel/BuildHistoryMargin/BuildHistory")

    scene.StartEncounterForTest()
    await get_tree().process_frame
    scene.AdvanceBattleFlowForTest()
    await get_tree().process_frame
    scene.ChooseRewardForTest(0)
    await get_tree().process_frame

    scene.StartEncounterForTest()
    await get_tree().process_frame
    scene.AdvanceBattleFlowForTest()
    await get_tree().process_frame
    scene.ChooseRewardForTest(2)
    await get_tree().process_frame

    assert_str(str(build_history.text)).contains("锋")
    assert_str(str(build_history.text)).contains("猎")

func test_he_is_coming_scene_enters_battle_after_ten_successful_moves() -> void:
    var scene = await _spawn_scene()
    var timer_label = scene.get_node("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/TimerPanel/TimerMargin/TimerLabel")

    scene.MoveEncounterStepsForTest(9)
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("map")
    assert_str(str(timer_label.text)).contains("9格")
    assert_str(str(timer_label.text)).contains("90%")

    scene.MoveEncounterStepsForTest(1)
    await get_tree().process_frame

    assert_str(str(scene.GetScenePhaseForTest())).is_equal("battle")

func test_he_is_coming_scene_shows_result_panel_on_forced_victory_and_game_over() -> void:
    var scene = await _spawn_scene()
    var result_panel = scene.get_node("CanvasLayer/UIRoot/ResultPanel")
    var result_title = scene.get_node("CanvasLayer/UIRoot/ResultPanel/VBox/ResultTitle")

    scene.ForceVictoryForTest()
    await get_tree().process_frame
    assert_bool(result_panel.visible).is_true()
    assert_str(str(result_title.text)).contains("原型通关")

    scene.ForceGameOverForTest()
    await get_tree().process_frame
    assert_bool(result_panel.visible).is_true()
    assert_str(str(result_title.text)).contains("游戏结束")

func _min_int(a: int, b: int) -> int:
    return a if a < b else b

func _non_empty_line_count(text: String) -> int:
    var count := 0
    for line in text.split("\n"):
        if not line.strip_edges().is_empty():
            count += 1
    return count
