using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Game.Core.Prototypes;
using Godot;

namespace Game.Godot.Prototypes;

public partial class DefaultRpgPrototype : Node2D
{
    private static readonly string[] PrototypeAssetRoots =
    [
        "res://Prototypes/DefaultRpgTemplate/Assets/",
        "res://Game.Godot/Prototypes/DefaultRpgTemplate/Assets/"
    ];

    private sealed record BuildArchetype(string Name, string Focus, string PassiveSummary, string TriggerLog, string HistoryShort, Color ActorColor);
    private sealed record GridPoint(int X, int Y);

    private const string ScenePhaseMap = "map";
    private const string ScenePhaseBattle = "battle";
    private const string ScenePhaseReward = "reward";
    private const string ScenePhaseComplete = "complete";
    private const double BattleLogStepDurationSec = 1.0;
    private const double SceneFadeDurationSec = 0.20;
    private const double RewardPanelFadeDurationSec = 0.18;
    private const double MapMoveTweenDurationSec = 0.12;
    private const double EncounterFlashDurationSec = 0.16;
    private const double EncounterPunchDurationSec = 0.08;
    private const double HpBarTweenDurationSec = 0.32;
    private static readonly Vector2 EncounterPunchScale = new(1.03f, 1.03f);
    private static readonly Vector2 EncounterPunchOffset = new(10.0f, -6.0f);
    private const double PlayerStrikeFlashStartSec = 0.10;
    private const double PlayerStrikeFlashEndSec = 0.35;
    private const double EnemyCounterFlashStartSec = 0.55;
    private const double EnemyCounterFlashEndSec = 0.82;
    private const int MapGridSize = 12;
    private const int MapCellSize = 50;
    private const int MaxChestCount = 5;
    private const int ObstacleCount = 22;
    private const float BattleBackdropBandHeight = 112.0f;
    private const float MapPlayerTokenBaseScale = 1.18f;
    private const float MapPlayerTokenPulseScale = 0.12f;
    private const double MapPlayerPulseCycleSec = 1.2;

    private readonly DefaultRpgPrototypeLoop _loop = new();
    private readonly Random _random = new(20260504);

    private DefaultRpgPrototypeState _state = default!;
    private DefaultRpgEncounterResult? _lastEncounter;
    private string _scenePhase = ScenePhaseMap;
    private bool _rewardFromChest;

    private Label _statusLabel = default!;
    private Label _progressLabel = default!;
    private Label _playerStatsLabel = default!;
    private Label _playerSkillsLabel = default!;
    private Label _buildDirectionLabel = default!;
    private Label _buildHistoryLabel = default!;
    private Label _enemyStatsLabel = default!;
    private Label _enemySkillsLabel = default!;
    private Label _encounterTypeLabel = default!;
    private Label _timerLabel = default!;
    private Label _chestLabel = default!;
    private Label _playerActorTitleLabel = default!;
    private Label _enemyActorTitleLabel = default!;
    private RichTextLabel _battleLogLabel = default!;
    private Texture2D _mapPlayerTexture = default!;
    private Texture2D[] _mapChestTextures = default!;
    private Texture2D[] _mapObstacleTextures = default!;
    private Texture2D[] _floorTileTextures = default!;
    private Texture2D[] _mapRiverTextures = default!;
    private Texture2D[] _mapCastleTextures = default!;
    private Texture2D[] _mapMountainBackdropTextures = default!;
    private Texture2D? _showcaseMapTexture;
    private Texture2D? _showcaseBattleTexture;
    private Texture2D _battleHeroVanguardTexture = default!;
    private Texture2D _battleHeroGuardianTexture = default!;
    private Texture2D _battleHeroHunterTexture = default!;
    private Texture2D _battleEnemyNormalTexture = default!;
    private Texture2D _battleEnemyEliteTexture = default!;
    private Texture2D _battleEnemyBossTexture = default!;
    private ColorRect _road = default!;
    private ColorRect _rewardChest = default!;
    private ColorRect _playerToken = default!;
    private TextureRect _mapBackground = default!;
    private Control _battleBackdropBand = default!;
    private Control _battleBackdrop = default!;
    private TextureRect _battleBackdropTexture = default!;
    private PanelContainer _rewardPanel = default!;
    private PanelContainer _resultPanel = default!;
    private ColorRect _transitionFlash = default!;
    private Label _resultTitleLabel = default!;
    private Label _resultSummaryLabel = default!;
    private ProgressBar _encounterProgress = default!;
    private ProgressBar _playerActorHpBar = default!;
    private ProgressBar _enemyActorHpBar = default!;
    private Control _contentRoot = default!;
    private Control _mapSceneRoot = default!;
    private Control _battleSceneRoot = default!;
    private ColorRect _playerActor = default!;
    private ColorRect _enemyActor = default!;
    private Button[] _rewardButtons = [];
    private Control _gridRoot = default!;
    private ColorRect[,] _gridCells = new ColorRect[MapGridSize, MapGridSize];
    private TextureRect[,] _gridFloorSprites = new TextureRect[MapGridSize, MapGridSize];
    private TextureRect[,] _gridBackdropSprites = new TextureRect[MapGridSize, MapGridSize];
    private ColorRect[,] _gridRouteSprites = new ColorRect[MapGridSize, MapGridSize];
    private ColorRect[,] _gridShadowSprites = new ColorRect[MapGridSize, MapGridSize];
    private TextureRect[,] _gridObstacleSprites = new TextureRect[MapGridSize, MapGridSize];
    private TextureRect[,] _gridRiverSprites = new TextureRect[MapGridSize, MapGridSize];
    private TextureRect[,] _gridCastleSprites = new TextureRect[MapGridSize, MapGridSize];
    private int _encounterMoveSteps;
    private double _battlePresentationSec;
    private double _manualBattlePresentationSec;
    private double _playerHpDisplayValue = 100.0;
    private double _enemyHpDisplayValue = 100.0;
    private double _mapPlayerPulseSec;
    private int _layoutDebugFramesRemaining = 3;
    private Vector2 _contentRootBasePosition = Vector2.Zero;
    private Tween? _playerMoveTween;
    private Tween? _sceneFadeTween;
    private Tween? _rewardPanelTween;
    private Tween? _transitionFlashTween;
    private Tween? _encounterPunchTween;
    private Tween? _playerHpTween;
    private Tween? _enemyHpTween;
    private bool _useManualBattlePresentationForTest;
    private string _currentBuildArchetype = "均衡";
    private readonly List<string> _buildHistory = [];
    private readonly HashSet<GridPoint> _obstacles = [];
    private readonly List<GridPoint> _chests = [];
    private GridPoint _playerPosition = new(0, 0);

    public override void _Ready()
    {
        _statusLabel = GetNode<Label>("CanvasLayer/UIRoot/TopPanel/TopMargin/TopVBox/TopInfo/StatusPanel/StatusMargin/StatusLabel");
        _progressLabel = GetNode<Label>("CanvasLayer/UIRoot/TopPanel/TopMargin/TopVBox/TopInfo/ProgressPanel/ProgressMargin/ProgressLabel");
        _contentRoot = GetNode<Control>("CanvasLayer/UIRoot/Content");
        _playerStatsLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/PlayerStatsPanel/PlayerStatsMargin/PlayerStats");
        _playerSkillsLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/PlayerSkillsPanel/PlayerSkillsMargin/PlayerSkills");
        _buildDirectionLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/BuildDirectionPanel/BuildDirectionMargin/BuildDirection");
        _buildHistoryLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/Sidebar/SidebarMargin/SidebarVBox/BuildHistoryPanel/BuildHistoryMargin/BuildHistory");
        _mapSceneRoot = GetNode<Control>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene");
        _battleSceneRoot = GetNode<Control>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene");
        _timerLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/TimerPanel/TimerMargin/TimerLabel");
        _chestLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/MapInfo/ChestPanel/ChestMargin/ChestLabel");
        _gridRoot = GetNode<Control>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot");
        _road = GetNode<ColorRect>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/Road");
        _rewardChest = GetNode<ColorRect>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/RewardChest");
        _playerToken = GetNode<ColorRect>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/PlayerToken");
        _mapBackground = GetNode<TextureRect>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/TrackFrame/TrackMargin/Track/TrackRoot/MapBackground");
        _encounterTypeLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/EncounterTypePanel/EncounterTypeMargin/EncounterTypeLabel");
        _battleBackdropBand = GetNode<Control>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleBackdropBand");
        _battleBackdrop = GetNode<Control>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleBackdropBand/BattleBackdrop");
        _battleBackdropTexture = GetNode<TextureRect>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleBackdropBand/BattleBackdrop/BattleBackdropTexture");
        _playerActor = GetNode<ColorRect>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor");
        _enemyActor = GetNode<ColorRect>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor");
        _playerActorTitleLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor/PlayerActorMargin/PlayerActorVBox/PlayerActorTitle");
        _enemyActorTitleLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor/EnemyActorMargin/EnemyActorVBox/EnemyActorTitle");
        _playerActorHpBar = GetNode<ProgressBar>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/PlayerActor/PlayerActorMargin/PlayerActorVBox/PlayerActorHpBar");
        _enemyActorHpBar = GetNode<ProgressBar>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleActorsFrame/BattleActorsMargin/BattleActors/EnemyActor/EnemyActorMargin/EnemyActorVBox/EnemyActorHpBar");
        _enemyStatsLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleInfoFrame/BattleInfoMargin/BattleInfo/EnemyStats");
        _enemySkillsLabel = GetNode<Label>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleInfoFrame/BattleInfoMargin/BattleInfo/EnemySkills");
        _battleLogLabel = GetNode<RichTextLabel>("CanvasLayer/UIRoot/Content/SceneViewport/BattleScene/BattleMargin/BattleVBox/BattleLogFrame/BattleLogMargin/BattleLog");
        _rewardPanel = GetNode<PanelContainer>("CanvasLayer/UIRoot/RewardPanel");
        _resultPanel = GetNode<PanelContainer>("CanvasLayer/UIRoot/ResultPanel");
        _transitionFlash = GetNode<ColorRect>("CanvasLayer/UIRoot/TransitionFlash");
        _resultTitleLabel = GetNode<Label>("CanvasLayer/UIRoot/ResultPanel/VBox/ResultTitle");
        _resultSummaryLabel = GetNode<Label>("CanvasLayer/UIRoot/ResultPanel/VBox/ResultSummary");
        _encounterProgress = GetNode<ProgressBar>("CanvasLayer/UIRoot/Content/SceneViewport/MapScene/MapMargin/MapVBox/EncounterProgress");
        _mapPlayerTexture = LoadPrototypeTexture("map_player.png");
        _mapChestTextures =
        [
            LoadPrototypeTexture("map_chest_1.png"),
            LoadPrototypeTexture("map_chest_2.png"),
            LoadPrototypeTexture("map_chest_3.png")
        ];
        _mapObstacleTextures =
        [
            LoadPrototypeTexture("map_obstacle_1.png"),
            LoadPrototypeTexture("map_obstacle_2.png"),
            LoadPrototypeTexture("map_obstacle_3.png")
        ];
        _floorTileTextures =
        [
            LoadPrototypeTexture("floor_tile_1.png"),
            LoadPrototypeTexture("floor_tile_2.png"),
            LoadPrototypeTexture("floor_tile_3.png")
        ];
        _mapRiverTextures =
        [
            LoadPrototypeTexture("map_river_1.png"),
            LoadPrototypeTexture("map_river_2.png")
        ];
        _mapCastleTextures =
        [
            LoadPrototypeTexture("map_castle_1.png"),
            LoadPrototypeTexture("map_castle_2.png")
        ];
        _mapMountainBackdropTextures =
        [
            LoadPrototypeTexture("map_backdrop_mountain_1.png"),
            LoadPrototypeTexture("map_backdrop_mountain_2.png")
        ];
        _showcaseMapTexture = TryLoadPrototypeTexture("showcase_map_overworld.png");
        _showcaseBattleTexture = TryLoadPrototypeTexture("showcase_battle_background.png");
        _battleHeroVanguardTexture = LoadPrototypeTexture("battle_hero_vanguard.png");
        _battleHeroGuardianTexture = LoadPrototypeTexture("battle_hero_guardian.png");
        _battleHeroHunterTexture = LoadPrototypeTexture("battle_hero_hunter.png");
        _battleEnemyNormalTexture = LoadPrototypeTexture("battle_enemy_normal.png");
        _battleEnemyEliteTexture = LoadPrototypeTexture("battle_enemy_elite.png");
        _battleEnemyBossTexture = LoadPrototypeTexture("battle_enemy_boss.png");
        _rewardButtons =
        [
            GetNode<Button>("CanvasLayer/UIRoot/RewardPanel/RewardMargin/VBox/Rewards/RewardOption1"),
            GetNode<Button>("CanvasLayer/UIRoot/RewardPanel/RewardMargin/VBox/Rewards/RewardOption2"),
            GetNode<Button>("CanvasLayer/UIRoot/RewardPanel/RewardMargin/VBox/Rewards/RewardOption3")
        ];

        for (var i = 0; i < _rewardButtons.Length; i++)
        {
            var idx = i;
            _rewardButtons[i].Pressed += () => ChooseReward(idx);
        }

        BuildGridVisuals();
        SetupMapSprites();
        SetupBattleSprites();

        _state = _loop.CreateInitialState();
        _scenePhase = ScenePhaseMap;
        _lastEncounter = null;
        ResetMapState(1);
        _mapSceneRoot.Visible = true;
        _battleSceneRoot.Visible = false;
        _rewardPanel.Visible = false;
        _resultPanel.Visible = false;
        _mapSceneRoot.Modulate = new Color(1, 1, 1, 0);
        _battleSceneRoot.Modulate = new Color(1, 1, 1, 0);
        _rewardPanel.Modulate = new Color(1, 1, 1, 0);
        _transitionFlash.Modulate = new Color(1, 1, 1, 0);
        _contentRootBasePosition = _contentRoot.Position;
        _contentRoot.Scale = Vector2.One;
        _contentRoot.Position = _contentRootBasePosition;
        StartInitialPresentation();
    }

    public override void _Process(double delta)
    {
        if (!AreUiNodesAlive())
        {
            return;
        }

        if (_scenePhase == ScenePhaseBattle && !_state.IsGameOver && !_state.IsVictory)
        {
            if (!_useManualBattlePresentationForTest)
            {
                _battlePresentationSec += delta;
            }
            RefreshView();
            if (_battlePresentationSec >= GetBattlePresentationDurationSec())
            {
                AdvanceBattleFlow();
                return;
            }
        }

    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (!AreUiNodesAlive())
        {
            return;
        }

        if (_scenePhase != ScenePhaseMap || _state.IsGameOver || _state.IsVictory)
        {
            return;
        }

        if (@event is not InputEventKey keyEvent || !keyEvent.Pressed || keyEvent.Echo)
        {
            return;
        }

        GridPoint? target = keyEvent.Keycode switch
        {
            Key.W => new GridPoint(_playerPosition.X, _playerPosition.Y - 1),
            Key.S => new GridPoint(_playerPosition.X, _playerPosition.Y + 1),
            Key.A => new GridPoint(_playerPosition.X - 1, _playerPosition.Y),
            Key.D => new GridPoint(_playerPosition.X + 1, _playerPosition.Y),
            _ => null
        };

        if (target is null)
        {
            return;
        }

        TryMovePlayer(target);
    }

    public void AdvanceMapTime(double seconds)
    {
        if (!AreUiNodesAlive())
        {
            return;
        }

        if (_state.IsGameOver || _state.IsVictory || _scenePhase != ScenePhaseMap)
        {
            return;
        }

        RefreshView();
    }

    private static Texture2D LoadPrototypeTexture(string fileName)
    {
        foreach (var root in PrototypeAssetRoots)
        {
            var path = root + fileName;
            if (ResourceLoader.Exists(path))
            {
                return GD.Load<Texture2D>(path);
            }

            if (FileAccess.FileExists(path))
            {
                var image = Image.LoadFromFile(path);
                if (image is not null && !image.IsEmpty())
                {
                    return ImageTexture.CreateFromImage(image);
                }
            }
        }

        return CreateFallbackTexture(fileName);
    }

    private static Texture2D? TryLoadPrototypeTexture(string fileName)
    {
        foreach (var root in PrototypeAssetRoots)
        {
            var path = root + fileName;
            if (ResourceLoader.Exists(path))
            {
                return GD.Load<Texture2D>(path);
            }

            if (FileAccess.FileExists(path))
            {
                var image = Image.LoadFromFile(path);
                if (image is not null && !image.IsEmpty())
                {
                    return ImageTexture.CreateFromImage(image);
                }
            }
        }

        return null;
    }

    private static Texture2D CreateFallbackTexture(string fileName)
    {
        var image = Image.CreateEmpty(MapCellSize, MapCellSize, false, Image.Format.Rgba8);
        image.Fill(GetFallbackTextureColor(fileName));

        var accent = new Color(1f, 1f, 1f, 0.22f);
        for (var i = 0; i < MapCellSize; i++)
        {
            image.SetPixel(i, i, accent);
            image.SetPixel(MapCellSize - 1 - i, i, accent);
        }

        return ImageTexture.CreateFromImage(image);
    }

    private static Color GetFallbackTextureColor(string fileName)
    {
        if (fileName.Contains("hero", StringComparison.OrdinalIgnoreCase) || fileName.Contains("player", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.88f, 0.76f, 0.24f, 1f);
        }

        if (fileName.Contains("boss", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.72f, 0.18f, 0.18f, 1f);
        }

        if (fileName.Contains("elite", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.70f, 0.32f, 0.24f, 1f);
        }

        if (fileName.Contains("enemy", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.58f, 0.24f, 0.24f, 1f);
        }

        if (fileName.Contains("chest", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.22f, 0.46f, 0.86f, 1f);
        }

        if (fileName.Contains("obstacle", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.82f, 0.82f, 0.84f, 1f);
        }

        if (fileName.Contains("floor", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.18f, 0.20f, 0.27f, 1f);
        }

        if (fileName.Contains("frame", StringComparison.OrdinalIgnoreCase))
        {
            return new Color(0.77f, 0.69f, 0.42f, 1f);
        }

        return new Color(0.45f, 0.45f, 0.52f, 1f);
    }

    public void ChooseRewardForTest(int rewardIndex)
    {
        ChooseReward(rewardIndex);
    }

    public string GetScenePhaseForTest()
    {
        return _scenePhase;
    }

    public void AdvanceBattleFlowForTest()
    {
        AdvanceBattleFlow();
    }

    public void AdvanceBattlePresentationForTest(double seconds)
    {
        if (_scenePhase != ScenePhaseBattle)
        {
            return;
        }

        var maxDuration = GetBattlePresentationDurationSec();
        _manualBattlePresentationSec = Math.Min(maxDuration, _manualBattlePresentationSec + seconds);
        _battlePresentationSec = _manualBattlePresentationSec;
        RefreshView();

        if (_manualBattlePresentationSec >= maxDuration)
        {
            AdvanceBattleFlow();
        }
    }

    public void AdvanceUiAnimationForTest(double seconds)
    {
        if (_rewardPanel.Visible)
        {
            var alpha = Math.Min(1.0, _rewardPanel.Modulate.A + (seconds / RewardPanelFadeDurationSec));
            _rewardPanel.Modulate = new Color(1, 1, 1, (float)alpha);
        }

        if (_mapSceneRoot.Visible && _mapSceneRoot.Modulate.A < 1.0f)
        {
            var alpha = Math.Min(1.0, _mapSceneRoot.Modulate.A + (seconds / SceneFadeDurationSec));
            _mapSceneRoot.Modulate = new Color(1, 1, 1, (float)alpha);
        }

        if (_battleSceneRoot.Visible && _battleSceneRoot.Modulate.A < 1.0f)
        {
            var alpha = Math.Min(1.0, _battleSceneRoot.Modulate.A + (seconds / SceneFadeDurationSec));
            _battleSceneRoot.Modulate = new Color(1, 1, 1, (float)alpha);
        }

        _mapPlayerPulseSec += seconds;
        UpdateMapPlayerPresentation();

        if (_playerHpTween is null)
        {
            _playerActorHpBar.Value = _playerHpDisplayValue;
        }

        if (_enemyHpTween is null)
        {
            _enemyActorHpBar.Value = _enemyHpDisplayValue;
        }
    }

    public void ForceVictoryForTest()
    {
        _state = _state with
        {
            IsVictory = true,
            IsGameOver = false,
            Phase = "complete"
        };
        _scenePhase = ScenePhaseComplete;
        RefreshView();
    }

    public void ForceGameOverForTest()
    {
        _state = _state with
        {
            IsVictory = false,
            IsGameOver = true,
            Phase = "complete"
        };
        _scenePhase = ScenePhaseComplete;
        RefreshView();
    }

    public void SetStepIndexForTest(int stepIndex)
    {
        _state = _state with
        {
            StepIndex = stepIndex,
            IsGameOver = false,
            IsVictory = false,
            Phase = "battle"
        };
        _scenePhase = ScenePhaseMap;
        _lastEncounter = null;
        _encounterMoveSteps = 0;
        _battlePresentationSec = 0.0;
        _rewardFromChest = false;
        RefreshView();
    }

    public void StartEncounterForTest()
    {
        _useManualBattlePresentationForTest = true;
        _manualBattlePresentationSec = 0.0;
        StartEncounter();
        RefreshView();
    }

    public int GetMapGridSizeForTest()
    {
        return MapGridSize;
    }

    public int GetMapCellSizeForTest()
    {
        return MapCellSize;
    }

    public int GetChestCountForTest()
    {
        return _chests.Count;
    }

    public int GetObstacleCountForTest()
    {
        return _obstacles.Count;
    }

    public Vector2I GetPlayerGridPositionForTest()
    {
        return new Vector2I(_playerPosition.X, _playerPosition.Y);
    }

    public void MovePlayerToChestForTest()
    {
        if (_chests.Count == 0)
        {
            return;
        }

        _playerPosition = _chests[0];
        CollectChestAtPlayerPosition();
        RefreshView();
    }

    public int GetChestSpawnIndexForTest()
    {
        if (_chests.Count == 0)
        {
            return -1;
        }

        var hash = 17;
        foreach (var chest in _chests)
        {
            hash = (hash * 31) + (chest.Y * MapGridSize) + chest.X;
        }

        return hash;
    }

    public void MoveEncounterStepsForTest(int steps)
    {
        for (var i = 0; i < steps; i++)
        {
            if (_scenePhase != ScenePhaseMap || _state.IsGameOver || _state.IsVictory)
            {
                break;
            }

            _encounterMoveSteps = Math.Min(10, _encounterMoveSteps + 1);
            if (_encounterMoveSteps >= 10)
            {
                StartEncounter();
                break;
            }
        }

        RefreshView();
    }

    private void BuildGridVisuals()
    {
        foreach (var child in _gridRoot.GetChildren())
        {
            if (child is Node node && node.Name.ToString().StartsWith("Cell_"))
            {
                node.QueueFree();
            }
        }

        for (var y = 0; y < MapGridSize; y++)
        {
            for (var x = 0; x < MapGridSize; x++)
            {
                var cell = new ColorRect
                {
                    Name = $"Cell_{x}_{y}",
                    Color = Colors.Black,
                    Position = new Vector2(x * MapCellSize, y * MapCellSize),
                    Size = new Vector2(MapCellSize - 2, MapCellSize - 2)
                };
                _gridRoot.AddChild(cell);
                _gridCells[x, y] = cell;

                var floorSprite = new TextureRect
                {
                    Name = $"Floor_{x}_{y}",
                    Position = new Vector2(x * MapCellSize, y * MapCellSize),
                    Size = new Vector2(MapCellSize - 2, MapCellSize - 2),
                    StretchMode = TextureRect.StretchModeEnum.Scale,
                    MouseFilter = Control.MouseFilterEnum.Ignore,
                    Texture = GetFloorTileTextureForPoint(new GridPoint(x, y)),
                    Modulate = new Color(0.90f, 0.88f, 0.80f, 1.0f)
                };
                _gridRoot.AddChild(floorSprite);
                _gridFloorSprites[x, y] = floorSprite;

                var backdropSprite = new TextureRect
                {
                    Name = $"Backdrop_{x}_{y}",
                    Position = new Vector2(x * MapCellSize, y * MapCellSize),
                    Size = new Vector2(MapCellSize - 2, MapCellSize - 2),
                    StretchMode = TextureRect.StretchModeEnum.Scale,
                    MouseFilter = Control.MouseFilterEnum.Ignore,
                    Visible = false
                };
                _gridRoot.AddChild(backdropSprite);
                _gridBackdropSprites[x, y] = backdropSprite;

                var routeSprite = new ColorRect
                {
                    Name = $"Route_{x}_{y}",
                    Position = new Vector2((x * MapCellSize) + 18, (y * MapCellSize) + 18),
                    Size = new Vector2(12, 12),
                    Color = new Color(1.0f, 0.84f, 0.48f, 0.24f),
                    Visible = false
                };
                _gridRoot.AddChild(routeSprite);
                _gridRouteSprites[x, y] = routeSprite;

                var shadowSprite = new ColorRect
                {
                    Name = $"Shadow_{x}_{y}",
                    Position = new Vector2((x * MapCellSize) + 4, (y * MapCellSize) + 32),
                    Size = new Vector2(MapCellSize - 10, 10),
                    Color = new Color(0, 0, 0, 0.16f),
                    Visible = false
                };
                _gridRoot.AddChild(shadowSprite);
                _gridShadowSprites[x, y] = shadowSprite;

                var riverSprite = new TextureRect
                {
                    Name = $"River_{x}_{y}",
                    Position = new Vector2(x * MapCellSize, y * MapCellSize),
                    Size = new Vector2(MapCellSize - 2, MapCellSize - 2),
                    StretchMode = TextureRect.StretchModeEnum.Scale,
                    MouseFilter = Control.MouseFilterEnum.Ignore,
                    Visible = false
                };
                _gridRoot.AddChild(riverSprite);
                _gridRiverSprites[x, y] = riverSprite;

                var obstacleSprite = new TextureRect
                {
                    Name = $"Obstacle_{x}_{y}",
                    Position = new Vector2((x * MapCellSize) + 9, (y * MapCellSize) + 9),
                    Size = new Vector2(32, 32),
                    StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                    MouseFilter = Control.MouseFilterEnum.Ignore,
                    Visible = false,
                    Texture = GetObstacleTextureForPoint(new GridPoint(x, y))
                };
                _gridRoot.AddChild(obstacleSprite);
                _gridObstacleSprites[x, y] = obstacleSprite;

                var castleSprite = new TextureRect
                {
                    Name = $"Castle_{x}_{y}",
                    Position = new Vector2((x * MapCellSize) - 50, (y * MapCellSize) - 50),
                    Size = new Vector2(150, 150),
                    StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                    MouseFilter = Control.MouseFilterEnum.Ignore,
                    Visible = false
                };
                _gridRoot.AddChild(castleSprite);
                _gridCastleSprites[x, y] = castleSprite;
            }
        }
    }

    private void SetupMapSprites()
    {
        UpdateMapViewportLayout();
        AttachPlayerTokenVisuals();
        AttachSpriteToColorRect(_rewardChest, "RewardChestSprite", _mapChestTextures[0], new Vector2(34, 34));
        _mapBackground.Texture = _showcaseMapTexture;
        _mapBackground.Visible = _showcaseMapTexture is not null;
        _playerToken.Color = new Color(1, 1, 1, 0.0f);
        _rewardChest.Color = new Color(1, 1, 1, 0.0f);
        AlignMapPlayerTokenPivot();
        UpdateMapPlayerPresentation();
    }

    private void SetupBattleSprites()
    {
        AttachSpriteToColorRect(_playerActor, "PlayerActorSprite", _battleHeroVanguardTexture, new Vector2(128, 128));
        AttachSpriteToColorRect(_enemyActor, "EnemyActorSprite", _battleEnemyNormalTexture, new Vector2(128, 128));
        _battleBackdropTexture.Texture = _showcaseBattleTexture;
        _battleBackdropTexture.ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize;
        _battleBackdrop.Visible = _showcaseBattleTexture is not null;
    }

    private static void AttachSpriteToColorRect(ColorRect host, string spriteName, Texture2D texture, Vector2 size)
    {
        if (host.GetNodeOrNull<TextureRect>(spriteName) is not null)
        {
            return;
        }

        var sprite = new TextureRect
        {
            Name = spriteName,
            Texture = texture,
            CustomMinimumSize = size,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            MouseFilter = Control.MouseFilterEnum.Ignore
        };
        sprite.SetAnchorsPreset(Control.LayoutPreset.Center);
        sprite.Position = new Vector2(-size.X * 0.5f, -size.Y * 0.5f);
        sprite.AnchorLeft = 0.5f;
        sprite.AnchorTop = 0.5f;
        sprite.AnchorRight = 0.5f;
        sprite.AnchorBottom = 0.5f;
        host.AddChild(sprite);
    }

    private void AttachPlayerTokenVisuals()
    {
        AttachSpriteToColorRect(_playerToken, "PlayerTokenShadow", _mapPlayerTexture, new Vector2(42, 42));
        AttachSpriteToColorRect(_playerToken, "PlayerTokenOutline", _mapPlayerTexture, new Vector2(40, 40));
        AttachSpriteToColorRect(_playerToken, "PlayerTokenSprite", _mapPlayerTexture, new Vector2(38, 38));

        var shadow = _playerToken.GetNode<TextureRect>("PlayerTokenShadow");
        shadow.ZIndex = 0;
        shadow.Modulate = new Color(0, 0, 0, 0.42f);
        shadow.Position = new Vector2(-17, -11);

        var outline = _playerToken.GetNode<TextureRect>("PlayerTokenOutline");
        outline.ZIndex = 1;
        outline.Modulate = new Color(1.0f, 0.92f, 0.46f, 0.88f);
        outline.Position = new Vector2(-20, -20);

        var sprite = _playerToken.GetNode<TextureRect>("PlayerTokenSprite");
        sprite.ZIndex = 2;
        sprite.Modulate = Colors.White;
        sprite.Position = new Vector2(-19, -19);
    }

    private void UpdateMapPlayerPresentation()
    {
        var sprite = _playerToken.GetNodeOrNull<TextureRect>("PlayerTokenSprite");
        var outline = _playerToken.GetNodeOrNull<TextureRect>("PlayerTokenOutline");
        var shadow = _playerToken.GetNodeOrNull<TextureRect>("PlayerTokenShadow");
        if (sprite is null || outline is null || shadow is null)
        {
            return;
        }

        AlignMapPlayerTokenPivot();
        var phase = (float)(_mapPlayerPulseSec / MapPlayerPulseCycleSec * Math.PI * 2.0);
        var pulse = (Mathf.Sin(phase) + 1.0f) * 0.5f;
        var scale = MapPlayerTokenBaseScale + (pulse * MapPlayerTokenPulseScale);
        _playerToken.Scale = new Vector2(scale, scale);

        outline.Visible = true;
        shadow.Visible = true;
        outline.Modulate = new Color(
            1.0f,
            0.88f + (pulse * 0.10f),
            0.30f + (pulse * 0.22f),
            0.78f + (pulse * 0.20f));
        shadow.Modulate = new Color(0, 0, 0, 0.34f + (pulse * 0.18f));
        shadow.Position = new Vector2(-17, -9 + (pulse * 2.0f));
        sprite.Modulate = new Color(1.0f, 1.0f, 1.0f, 0.94f + (pulse * 0.06f));
    }

    private Texture2D GetChestTextureForPoint(GridPoint point)
    {
        return _mapChestTextures[Math.Abs((point.X * 7) + (point.Y * 11)) % _mapChestTextures.Length];
    }

    private Texture2D GetObstacleTextureForPoint(GridPoint point)
    {
        return _mapObstacleTextures[Math.Abs((point.X * 5) + (point.Y * 3)) % _mapObstacleTextures.Length];
    }

    private Texture2D GetFloorTileTextureForPoint(GridPoint point)
    {
        return _floorTileTextures[Math.Abs((point.X * 13) + (point.Y * 17)) % _floorTileTextures.Length];
    }

    private Texture2D GetRiverTextureForPoint(GridPoint point)
    {
        return _mapRiverTextures[Math.Abs((point.X * 3) + (point.Y * 5)) % _mapRiverTextures.Length];
    }

    private Texture2D GetCastleTextureForPoint(GridPoint point)
    {
        return _mapCastleTextures[Math.Abs((point.X * 11) + (point.Y * 7)) % _mapCastleTextures.Length];
    }

    private Texture2D GetBackdropTextureForPoint(GridPoint point)
    {
        return _mapMountainBackdropTextures[Math.Abs((point.X * 2) + (point.Y * 3)) % _mapMountainBackdropTextures.Length];
    }

    private bool HasBackdropAt(GridPoint point)
    {
        return point.Y <= 1 && point.X >= 1 && point.X <= 10;
    }

    private bool HasRiverAt(GridPoint point)
    {
        return !_obstacles.Contains(point) && (point.X == 4 || point.X == 5) && point.Y >= 1 && point.Y <= 10;
    }

    private bool HasCastleAt(GridPoint point)
    {
        return !_obstacles.Contains(point) && point.X >= 8 && point.X <= 10 && point.Y >= 2 && point.Y <= 4;
    }

    private Color BuildFloorModulate(GridPoint point)
    {
        if (_obstacles.Contains(point))
        {
            return new Color(0.56f, 0.58f, 0.60f, 1.0f);
        }

        if (HasRiverAt(point))
        {
            return new Color(0.70f, 0.84f, 1.02f, 1.0f);
        }

        if (_scenePhase == ScenePhaseMap)
        {
            var distance = Math.Abs(point.X - _playerPosition.X) + Math.Abs(point.Y - _playerPosition.Y);
            if (distance <= 1)
            {
                return new Color(0.86f, 0.90f, 0.72f, 1.0f);
            }

            if (_chests.Count > 0)
            {
                var chest = _chests[0];
                var onGuidingAxis = point.X == _playerPosition.X || point.Y == _playerPosition.Y || point.X == chest.X || point.Y == chest.Y;
                if (onGuidingAxis)
                {
                    return new Color(0.44f, 0.54f, 0.32f, 1.0f);
                }
            }
        }

        return new Color(0.34f, 0.46f, 0.26f, 1.0f);
    }

    private HashSet<GridPoint> BuildGuideRoute()
    {
        var route = new HashSet<GridPoint>();
        route.Add(_playerPosition);

        if (_scenePhase != ScenePhaseMap || _chests.Count == 0)
        {
            return route;
        }

        var chest = _chests[0];
        var current = _playerPosition;

        while (current.X != chest.X)
        {
            current = new GridPoint(current.X + Math.Sign(chest.X - current.X), current.Y);
            route.Add(current);
        }

        while (current.Y != chest.Y)
        {
            current = new GridPoint(current.X, current.Y + Math.Sign(chest.Y - current.Y));
            route.Add(current);
        }

        return route;
    }

    private Color BuildRouteMarkerColor(GridPoint point)
    {
        if (point == _playerPosition)
        {
            return new Color(1.0f, 0.94f, 0.62f, 0.85f);
        }

        if (_chests.Count > 0 && point == _chests[0])
        {
            return new Color(0.46f, 0.78f, 1.0f, 0.80f);
        }

        return new Color(1.0f, 0.84f, 0.48f, 0.34f);
    }

    private Texture2D GetBattleHeroTexture()
    {
        return _currentBuildArchetype switch
        {
            "鍏堥攱" => _battleHeroVanguardTexture,
            "瀹堟姢" => _battleHeroGuardianTexture,
            "鐚庢墜" => _battleHeroHunterTexture,
            _ => _battleHeroVanguardTexture
        };
    }

    private Texture2D GetBattleEnemyTexture(string encounterKind)
    {
        return encounterKind switch
        {
            "boss" => _battleEnemyBossTexture,
            "elite" => _battleEnemyEliteTexture,
            _ => _battleEnemyNormalTexture
        };
    }

    private void TryMovePlayer(GridPoint target)
    {
        if (!IsInside(target) || _obstacles.Contains(target))
        {
            return;
        }

        _playerPosition = target;
        AnimatePlayerTokenToCurrentCell();

        if (CollectChestAtPlayerPosition())
        {
            RefreshView();
            return;
        }

        RegisterEncounterStep();

        if (_scenePhase == ScenePhaseBattle)
        {
            return;
        }

        RefreshView();
    }

    private void RegisterEncounterStep()
    {
        if (_scenePhase != ScenePhaseMap || _state.IsGameOver || _state.IsVictory)
        {
            return;
        }

        _encounterMoveSteps = Math.Min(10, _encounterMoveSteps + 1);
        var encounterChance = _encounterMoveSteps / 10.0;

        if (_encounterMoveSteps >= 10 || _random.NextDouble() <= encounterChance)
        {
            StartEncounter();
        }
    }

    private bool CollectChestAtPlayerPosition()
    {
        var chestIndex = _chests.FindIndex(chest => chest == _playerPosition);
        if (chestIndex < 0)
        {
            return false;
        }

        _chests.RemoveAt(chestIndex);
        _rewardFromChest = true;
        _lastEncounter = BuildChestRewardEncounter();
        _scenePhase = ScenePhaseReward;
        _battlePresentationSec = 0.0;
        _encounterMoveSteps = 0;
        return true;
    }

    private DefaultRpgEncounterResult BuildChestRewardEncounter()
    {
        var rewardOptions = GetRewardOptionsForCurrentStep();
        return new DefaultRpgEncounterResult(
            new DefaultRpgEncounter("chest", "地图宝箱", 0, 0, 0),
            _state with { Phase = "reward" },
            rewardOptions,
            ["发现地图宝箱。", "直接获得一次肉鸽三选一奖励。"]);
    }

    private IReadOnlyList<HeIsComingRewardOption> GetRewardOptionsForCurrentStep()
    {
        var previewState = _loop.ResolveEncounter(_state);
        return previewState.RewardOptions.Count > 0 ? previewState.RewardOptions : [];
    }

    private void StartEncounter()
    {
        _lastEncounter = _loop.ResolveEncounter(_state);
        _scenePhase = ScenePhaseBattle;
        _encounterMoveSteps = 0;
        _battlePresentationSec = 0.0;
        _manualBattlePresentationSec = 0.0;
        _rewardFromChest = false;
        PlayEncounterFlash();
        PlayEncounterPunch();
        RefreshView();
    }

    private void ChooseReward(int rewardIndex)
    {
        if (_scenePhase != ScenePhaseReward || _lastEncounter is null || _lastEncounter.RewardOptions.Count == 0)
        {
            return;
        }

        _state = _loop.ApplyReward(_state, rewardIndex);
        var build = GetBuildArchetypeForRewardIndex(rewardIndex);
        _currentBuildArchetype = build.Name;
        _buildHistory.Add(build.HistoryShort);

        if (!_rewardFromChest)
        {
            SpawnChestAfterBattle();
        }

        _rewardFromChest = false;
        _scenePhase = ScenePhaseMap;
        _encounterMoveSteps = 0;
        _battlePresentationSec = 0.0;
        _lastEncounter = null;
        RemoveUnreachableChests();
        RefreshView();
    }

    private void AdvanceBattleFlow()
    {
        if (_scenePhase != ScenePhaseBattle || _lastEncounter is null)
        {
            return;
        }

        _useManualBattlePresentationForTest = false;
        _state = _lastEncounter.NextState;
        _battlePresentationSec = 0.0;
        _manualBattlePresentationSec = 0.0;

        if (_state.IsGameOver || _state.IsVictory)
        {
            _scenePhase = ScenePhaseComplete;
        }
        else if (_state.Phase == "reward")
        {
            _scenePhase = ScenePhaseReward;
        }
        else
        {
            _scenePhase = ScenePhaseMap;
        }

        RefreshView();
    }

    private void RefreshView()
    {
        if (!AreUiNodesAlive())
        {
            return;
        }

        UpdateMapSceneLayout();
        UpdateSceneVisibility();

        UpdateHeader();
        UpdateMap();
        UpdatePlayerPanel();
        UpdateBattlePanel();
        UpdateRewardPanel();
        UpdateResultPanel();

        if (_scenePhase == ScenePhaseMap && _mapSceneRoot.Visible && _mapSceneRoot.Modulate.A < 1.0f)
        {
            PlaySceneFade(_mapSceneRoot);
        }
    }

    private void UpdateHeader()
    {
        if (_state.IsVictory)
        {
            _statusLabel.Text = "首领被击败，原型通关。";
        }
        else if (_state.IsGameOver)
        {
            _statusLabel.Text = "我方倒下。游戏结束。";
        }
        else if (_scenePhase == ScenePhaseReward)
        {
            _statusLabel.Text = _rewardFromChest ? "宝箱已开启，请选择一项奖励。" : "战斗结束，请选择一项肉鸽奖励。";
        }
        else if (_scenePhase == ScenePhaseBattle)
        {
            _statusLabel.Text = "遭遇敌人。自动战斗结算中。";
        }
        else
        {
            _statusLabel.Text = "WASD 移动。靠近宝箱，或通过移动累计遇敌。";
        }

        var shownStep = _state.IsVictory || _state.IsGameOver
            ? Math.Min(15, _state.StepIndex)
            : Math.Max(1, _state.StepIndex - 1);
        _progressLabel.Text = $"遭遇 {shownStep}/15";
    }

    private void UpdateMapSceneLayout()
    {
        if (_mapSceneRoot.GetParent() is not Control viewport)
        {
            return;
        }

        _mapSceneRoot.AnchorLeft = 0.0f;
        _mapSceneRoot.AnchorTop = 0.0f;
        _mapSceneRoot.AnchorRight = 0.0f;
        _mapSceneRoot.AnchorBottom = 0.0f;
        _mapSceneRoot.OffsetLeft = 0.0f;
        _mapSceneRoot.OffsetTop = 0.0f;
        _mapSceneRoot.OffsetRight = 0.0f;
        _mapSceneRoot.OffsetBottom = 0.0f;
        _mapSceneRoot.Position = Vector2.Zero;
        _mapSceneRoot.Size = new Vector2(viewport.Size.X, _mapSceneRoot.Size.Y);
        UpdateMapViewportLayout();
        DumpInitialLayoutDebug(viewport);
    }

    private void DumpInitialLayoutDebug(Control viewport)
    {
        if (_layoutDebugFramesRemaining <= 0)
        {
            return;
        }

        var timerPanel = _timerLabel.GetParent()?.GetParent() as Control;
        GD.Print(
            $"LAYOUT_DEBUG frame={4 - _layoutDebugFramesRemaining} " +
            $"viewport_pos={viewport.GetGlobalRect().Position} viewport_size={viewport.GetGlobalRect().Size} " +
            $"map_pos={_mapSceneRoot.GetGlobalRect().Position} map_size={_mapSceneRoot.GetGlobalRect().Size} " +
            $"timer_pos={timerPanel?.GetGlobalRect().Position} timer_size={timerPanel?.GetGlobalRect().Size}");
        _layoutDebugFramesRemaining--;
    }

    private async void StartInitialPresentation()
    {
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        FinishInitialPresentation();
    }

    private void FinishInitialPresentation()
    {
        if (!AreUiNodesAlive())
        {
            return;
        }

        UpdateMapSceneLayout();
        _mapSceneRoot.Visible = _scenePhase == ScenePhaseMap || (_scenePhase == ScenePhaseReward && _rewardFromChest);
        UpdateSceneVisibility();
        UpdateHeader();
        UpdateMap();
        UpdatePlayerPanel();
        UpdateBattlePanel();
        UpdateRewardPanel();
        UpdateResultPanel();
        if (_mapSceneRoot.Visible && _mapSceneRoot.Modulate.A < 1.0f)
        {
            PlaySceneFade(_mapSceneRoot);
        }
    }

    private void UpdateMapViewportLayout()
    {
        _gridRoot.AnchorLeft = 0.0f;
        _gridRoot.AnchorTop = 0.0f;
        _gridRoot.AnchorRight = 0.0f;
        _gridRoot.AnchorBottom = 0.0f;
        _gridRoot.OffsetLeft = 0.0f;
        _gridRoot.OffsetTop = 0.0f;
        _gridRoot.OffsetRight = 0.0f;
        _gridRoot.OffsetBottom = 0.0f;
        _gridRoot.Position = Vector2.Zero;
        _gridRoot.Size = new Vector2(MapGridSize * MapCellSize, MapGridSize * MapCellSize);

        _mapBackground.AnchorLeft = 0.0f;
        _mapBackground.AnchorTop = 0.0f;
        _mapBackground.AnchorRight = 0.0f;
        _mapBackground.AnchorBottom = 0.0f;
        _mapBackground.OffsetLeft = 0.0f;
        _mapBackground.OffsetTop = 0.0f;
        _mapBackground.OffsetRight = 0.0f;
        _mapBackground.OffsetBottom = 0.0f;
        _mapBackground.Position = Vector2.Zero;
        _mapBackground.Size = _gridRoot.Size;
    }

    private void AlignMapPlayerTokenPivot()
    {
        _playerToken.PivotOffset = _playerToken.Size * 0.5f;
    }

    private void UpdateMap()
    {
        var current = _state.IsVictory || _state.IsGameOver
            ? Math.Min(15, _state.StepIndex)
            : Math.Max(1, _state.StepIndex - 1);

        _encounterProgress.MaxValue = 15;
        _encounterProgress.Value = current;
        RefreshMapLabels();
        PaintGrid();
    }

    private void RefreshMapLabels()
    {
        var encounterChance = _encounterMoveSteps * 10;
        _timerLabel.Text = $"已移动 {_encounterMoveSteps}格，当前遇敌率 {encounterChance}%，10格必遇敌。";
        _chestLabel.Text = _chests.Count == 0
            ? "当前地图没有宝箱，继续前进。"
            : $"地图宝箱 {_chests.Count} 个。黄色为我方，蓝色为宝箱。";
        _chestLabel.Modulate = _encounterMoveSteps >= 8 && _scenePhase == ScenePhaseMap
            ? new Color(1.0f, 0.86f, 0.55f)
            : Colors.White;
    }

    private void PaintGrid()
    {
        var useShowcaseMapBackground = _mapBackground.Visible && _mapBackground.Texture is not null;

        _road.Color = useShowcaseMapBackground
            ? new Color(1, 1, 1, 0.0f)
            : _scenePhase == ScenePhaseMap && _encounterMoveSteps >= 8
            ? new Color(0.28f, 0.46f, 0.18f)
            : new Color(0.18f, 0.34f, 0.14f);

        var guideRoute = BuildGuideRoute();

        for (var y = 0; y < MapGridSize; y++)
        {
            for (var x = 0; x < MapGridSize; x++)
            {
                var point = new GridPoint(x, y);
                _gridCells[x, y].Color = useShowcaseMapBackground
                    ? new Color(1, 1, 1, 0.0f)
                    : BuildCellColor(point, _chests, _obstacles, _playerPosition);
                _gridFloorSprites[x, y].Visible = !useShowcaseMapBackground;
                _gridFloorSprites[x, y].Modulate = BuildFloorModulate(point);
                _gridBackdropSprites[x, y].Visible = !useShowcaseMapBackground && HasBackdropAt(point);
                _gridBackdropSprites[x, y].Texture = GetBackdropTextureForPoint(point);
                _gridBackdropSprites[x, y].Modulate = new Color(1, 1, 1, 0.88f);
                _gridRouteSprites[x, y].Visible = guideRoute.Contains(point) && !_obstacles.Contains(point);
                _gridRouteSprites[x, y].Color = BuildRouteMarkerColor(point);
                _gridShadowSprites[x, y].Visible = _obstacles.Contains(point);
                _gridRiverSprites[x, y].Visible = !useShowcaseMapBackground && HasRiverAt(point);
                _gridRiverSprites[x, y].Texture = GetRiverTextureForPoint(point);
                _gridObstacleSprites[x, y].Visible = _obstacles.Contains(point);
                _gridCastleSprites[x, y].Visible = !useShowcaseMapBackground && HasCastleAt(point);
                _gridCastleSprites[x, y].Texture = GetCastleTextureForPoint(point);
            }
        }

        if (_playerMoveTween is null)
        {
            _playerToken.Position = new Vector2((_playerPosition.X * MapCellSize) + 10, (_playerPosition.Y * MapCellSize) + 10);
        }
        _playerToken.Color = new Color(1, 1, 1, 0.0f);
        UpdateMapPlayerPresentation();

        if (_chests.Count > 0 && _scenePhase == ScenePhaseMap)
        {
            var chest = _chests[0];
            _rewardChest.Show();
            _rewardChest.Position = new Vector2((chest.X * MapCellSize) + 8, (chest.Y * MapCellSize) + 8);
            _rewardChest.Color = new Color(1, 1, 1, 0.0f);
            _rewardChest.GetNode<TextureRect>("RewardChestSprite").Texture = GetChestTextureForPoint(chest);
        }
        else
        {
            _rewardChest.Hide();
        }
    }

    private void UpdatePlayerPanel()
    {
        _playerStatsLabel.Text = $"生命 {_state.PlayerHp}\n攻击 {_state.PlayerAttack}\n防御 {_state.PlayerDefense}\n暴击 {Math.Round(_state.CritRate * 100)}%";
        _playerSkillsLabel.Text = $"被动\n{string.Join("\n", _state.PassiveSkills)}\n\n装备\n{string.Join("\n", _state.EquippedItems)}";
        _buildDirectionLabel.Text = BuildBuildDirectionText();
        _buildHistoryLabel.Text = BuildBuildHistoryText();
    }

    private void UpdateBattlePanel()
    {
        UpdateBattleBackdropLayout();
        _playerActorTitleLabel.Text = $"我方  HP {_state.PlayerHp}";
        _playerActorHpBar.MaxValue = 100;
        var playerHpTarget = Math.Clamp(_state.PlayerHp / 42.0 * 100.0, 0.0, 100.0);

        if (_lastEncounter is null || _scenePhase == ScenePhaseMap)
        {
            _playerActor.GetNode<TextureRect>("PlayerActorSprite").Texture = GetBattleHeroTexture();
            _enemyActor.GetNode<TextureRect>("EnemyActorSprite").Texture = _battleEnemyNormalTexture;
            _enemyActorTitleLabel.Text = "敌方待机";
            _enemyActorHpBar.MaxValue = 100;
            SetBattleHpBarsImmediately(playerHpTarget, 68.0);
            _encounterTypeLabel.Text = "行军途中";
            _encounterTypeLabel.Modulate = Colors.White;
            ApplyActorColors(new Color(0.262745f, 0.537255f, 0.45098f), new Color(0.596078f, 0.25098f, 0.25098f));
            _enemyStatsLabel.Text = "前方暂无敌人。";
            _enemySkillsLabel.Text = "被动\n暂无";
            _battleLogLabel.Text = "在地图上移动，累计遇敌率，或寻找宝箱获取奖励。";
            return;
        }

        if (_lastEncounter.Encounter.Kind == "chest")
        {
            _playerActor.GetNode<TextureRect>("PlayerActorSprite").Texture = GetBattleHeroTexture();
            _enemyActor.GetNode<TextureRect>("EnemyActorSprite").Texture = GetChestTextureForPoint(_playerPosition);
            _enemyActorTitleLabel.Text = "宝箱奖励";
            _enemyActorHpBar.MaxValue = 100;
            SetBattleHpBarsImmediately(playerHpTarget, 100.0);
            _encounterTypeLabel.Text = "宝箱奖励";
            _encounterTypeLabel.Modulate = new Color(0.35f, 0.70f, 1.0f);
            _enemyStatsLabel.Text = "地图宝箱\n可直接获得三选一奖励";
            _enemySkillsLabel.Text = "效果\n跳过战斗";
            _battleLogLabel.Text = string.Join("\n", _lastEncounter.BattleLog);
            ApplyActorColors(GetBuildArchetypeByName(_currentBuildArchetype).ActorColor, new Color(0.20f, 0.40f, 0.90f));
            return;
        }

        _playerActor.GetNode<TextureRect>("PlayerActorSprite").Texture = GetBattleHeroTexture();
        _enemyActor.GetNode<TextureRect>("EnemyActorSprite").Texture = GetBattleEnemyTexture(_lastEncounter.Encounter.Kind);
        _enemyActorTitleLabel.Text = $"{_lastEncounter.Encounter.Name}  HP {_lastEncounter.Encounter.Hp}";
        _enemyActorHpBar.MaxValue = 100;
        UpdateBattleHpBars(playerHpTarget, BuildEnemyHpDisplayTarget(_lastEncounter));
        ApplyEncounterPresentation(_lastEncounter.Encounter.Kind);
        _enemyStatsLabel.Text = $"{_lastEncounter.Encounter.Name}\n生命 {_lastEncounter.Encounter.Hp}\n攻击 {_lastEncounter.Encounter.Attack}\n防御 {_lastEncounter.Encounter.Defense}";
        _enemySkillsLabel.Text = _lastEncounter.Encounter.Kind switch
        {
            "boss" => "被动\n末日光环\n重甲",
            "elite" => "被动\n守势架式\n反击重击",
            _ => "被动\n野性冲撞"
        };

        var builder = new StringBuilder();
        foreach (var line in BuildVisibleBattleLogLines(_lastEncounter.BattleLog))
        {
            builder.AppendLine(line);
        }

        _battleLogLabel.Text = builder.ToString().TrimEnd();
    }

    private void UpdateBattleBackdropLayout()
    {
        if (_battleBackdropBand.GetParent() is not Control parent)
        {
            return;
        }

        var bandHeight = Math.Min(BattleBackdropBandHeight, parent.Size.Y);
        var bandTop = Math.Max(0.0f, (parent.Size.Y - bandHeight) * 0.5f);

        _battleBackdropBand.AnchorLeft = 0.0f;
        _battleBackdropBand.AnchorTop = 0.0f;
        _battleBackdropBand.AnchorRight = 0.0f;
        _battleBackdropBand.AnchorBottom = 0.0f;
        _battleBackdropBand.OffsetLeft = 0.0f;
        _battleBackdropBand.OffsetTop = 0.0f;
        _battleBackdropBand.OffsetRight = 0.0f;
        _battleBackdropBand.OffsetBottom = 0.0f;
        _battleBackdropBand.Position = new Vector2(0.0f, bandTop);
        _battleBackdropBand.Size = new Vector2(parent.Size.X, bandHeight);
        _battleBackdropBand.CustomMinimumSize = new Vector2(0.0f, bandHeight);

        _battleBackdrop.AnchorLeft = 0.0f;
        _battleBackdrop.AnchorTop = 0.0f;
        _battleBackdrop.AnchorRight = 0.0f;
        _battleBackdrop.AnchorBottom = 0.0f;
        _battleBackdrop.OffsetLeft = 0.0f;
        _battleBackdrop.OffsetTop = 0.0f;
        _battleBackdrop.OffsetRight = 0.0f;
        _battleBackdrop.OffsetBottom = 0.0f;
        _battleBackdrop.Position = Vector2.Zero;
        _battleBackdrop.Size = _battleBackdropBand.Size;
        _battleBackdrop.CustomMinimumSize = Vector2.Zero;

        _battleBackdropTexture.AnchorLeft = 0.0f;
        _battleBackdropTexture.AnchorTop = 0.0f;
        _battleBackdropTexture.AnchorRight = 1.0f;
        _battleBackdropTexture.AnchorBottom = 1.0f;
        _battleBackdropTexture.OffsetLeft = 0.0f;
        _battleBackdropTexture.OffsetTop = 0.0f;
        _battleBackdropTexture.OffsetRight = 0.0f;
        _battleBackdropTexture.OffsetBottom = 0.0f;
        _battleBackdropTexture.Position = Vector2.Zero;
        _battleBackdropTexture.CustomMinimumSize = Vector2.Zero;
        _battleBackdropTexture.ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize;
    }

    private void UpdateRewardPanel()
    {
        var rewardOptions = _lastEncounter?.RewardOptions ?? [];
        var shouldShowReward = _scenePhase == ScenePhaseReward
            && rewardOptions.Count > 0
            && !_state.IsVictory
            && !_state.IsGameOver;

        if (shouldShowReward && !_rewardPanel.Visible)
        {
            _rewardPanel.Visible = true;
            _rewardPanel.Modulate = new Color(1, 1, 1, 0);
            PlayRewardPanelFadeIn();
        }
        else if (!shouldShowReward)
        {
            _rewardPanel.Visible = false;
            _rewardPanel.Modulate = new Color(1, 1, 1, 0);
        }

        for (var i = 0; i < _rewardButtons.Length; i++)
        {
            if (i < rewardOptions.Count)
            {
                var reward = rewardOptions[i];
                var archetype = GetBuildArchetypeForRewardIndex(i);
                _rewardButtons[i].Visible = true;
                _rewardButtons[i].Text = $"[{archetype.Name}] {reward.Title}\n{reward.Description}\n侧重 {archetype.Focus}";
                _rewardButtons[i].Modulate = archetype.ActorColor;
            }
            else
            {
                _rewardButtons[i].Visible = false;
                _rewardButtons[i].Modulate = Colors.White;
            }
        }
    }

    private double BuildEnemyHpDisplayTarget(DefaultRpgEncounterResult encounter)
    {
        var playerDamage = Math.Max(1, _state.PlayerAttack - encounter.Encounter.Defense) + (_state.CritRate >= 0.30 ? 2 : 0);
        var enemyRemaining = Math.Max(0, encounter.Encounter.Hp - playerDamage);
        return Math.Clamp(enemyRemaining / Math.Max(1.0, encounter.Encounter.Hp) * 100.0, 0.0, 100.0);
    }

    private void SetBattleHpBarsImmediately(double playerTarget, double enemyTarget)
    {
        _playerHpTween?.Kill();
        _enemyHpTween?.Kill();
        _playerHpDisplayValue = playerTarget;
        _enemyHpDisplayValue = enemyTarget;
        _playerActorHpBar.Value = playerTarget;
        _enemyActorHpBar.Value = enemyTarget;
    }

    private void UpdateBattleHpBars(double playerTarget, double enemyTarget)
    {
        var playerShouldDelay = _scenePhase == ScenePhaseBattle && _lastEncounter is not null && _lastEncounter.Encounter.Kind != "chest"
            && _battlePresentationSec < 4.0;
        var enemyShouldDelay = _scenePhase == ScenePhaseBattle && _lastEncounter is not null && _lastEncounter.Encounter.Kind != "chest"
            && _battlePresentationSec < 1.0;

        UpdatePlayerHpBar(playerTarget, playerShouldDelay);
        UpdateEnemyHpBar(enemyTarget, enemyShouldDelay);
    }

    private void UpdatePlayerHpBar(double targetValue, bool delayDrop)
    {
        var clampedTarget = Math.Clamp(targetValue, 0.0, 100.0);
        if (delayDrop)
        {
            if (_playerHpDisplayValue < clampedTarget)
            {
                _playerHpTween?.Kill();
                _playerHpDisplayValue = clampedTarget;
                _playerActorHpBar.Value = clampedTarget;
            }
            return;
        }

        if (Math.Abs(_playerHpDisplayValue - clampedTarget) < 0.01)
        {
            _playerHpDisplayValue = clampedTarget;
            _playerActorHpBar.Value = clampedTarget;
            return;
        }

        _playerHpTween?.Kill();
        _playerHpTween = CreateTween();
        var playerPreviewValue = Mathf.Lerp((float)_playerHpDisplayValue, (float)clampedTarget, 0.35f);
        _playerHpDisplayValue = playerPreviewValue;
        _playerActorHpBar.Value = playerPreviewValue;
        _playerHpTween.TweenMethod(Callable.From<double>(value =>
        {
            _playerHpDisplayValue = value;
            _playerActorHpBar.Value = value;
        }), _playerHpDisplayValue, clampedTarget, HpBarTweenDurationSec);
        _playerHpTween.Finished += () =>
        {
            _playerHpDisplayValue = clampedTarget;
            _playerActorHpBar.Value = clampedTarget;
            _playerHpTween = null;
        };
    }

    private void UpdateEnemyHpBar(double targetValue, bool delayDrop)
    {
        var clampedTarget = Math.Clamp(targetValue, 0.0, 100.0);
        if (delayDrop)
        {
            if (_enemyHpDisplayValue < clampedTarget)
            {
                _enemyHpTween?.Kill();
                _enemyHpDisplayValue = clampedTarget;
                _enemyActorHpBar.Value = clampedTarget;
            }
            return;
        }

        if (Math.Abs(_enemyHpDisplayValue - clampedTarget) < 0.01)
        {
            _enemyHpDisplayValue = clampedTarget;
            _enemyActorHpBar.Value = clampedTarget;
            return;
        }

        _enemyHpTween?.Kill();
        _enemyHpTween = CreateTween();
        var enemyPreviewValue = Mathf.Lerp((float)_enemyHpDisplayValue, (float)clampedTarget, 0.35f);
        _enemyHpDisplayValue = enemyPreviewValue;
        _enemyActorHpBar.Value = enemyPreviewValue;
        _enemyHpTween.TweenMethod(Callable.From<double>(value =>
        {
            _enemyHpDisplayValue = value;
            _enemyActorHpBar.Value = value;
        }), _enemyHpDisplayValue, clampedTarget, HpBarTweenDurationSec);
        _enemyHpTween.Finished += () =>
        {
            _enemyHpDisplayValue = clampedTarget;
            _enemyActorHpBar.Value = clampedTarget;
            _enemyHpTween = null;
        };
    }

    private void ApplyEncounterPresentation(string encounterKind)
    {
        var build = GetBuildArchetypeByName(_currentBuildArchetype);
        Color enemyBaseColor;

        switch (encounterKind)
        {
            case "boss":
                _encounterTypeLabel.Text = "首领遭遇";
                _encounterTypeLabel.Modulate = new Color(1.0f, 0.78f, 0.3f);
                enemyBaseColor = new Color(0.62f, 0.14f, 0.14f);
                break;
            case "elite":
                _encounterTypeLabel.Text = "精英遭遇";
                _encounterTypeLabel.Modulate = new Color(0.95f, 0.52f, 0.24f);
                enemyBaseColor = new Color(0.72f, 0.3f, 0.16f);
                break;
            default:
                _encounterTypeLabel.Text = "普通遭遇";
                _encounterTypeLabel.Modulate = new Color(0.82f, 0.86f, 0.92f);
                enemyBaseColor = new Color(0.596078f, 0.25098f, 0.25098f);
                break;
        }

        ApplyActorColors(build.ActorColor, enemyBaseColor);
    }

    private void ApplyActorColors(Color playerBaseColor, Color enemyBaseColor)
    {
        _playerActor.Color = ShouldFlashPlayerActor() ? new Color(1.0f, 1.0f, 1.0f, 0.14f) : new Color(playerBaseColor.R, playerBaseColor.G, playerBaseColor.B, 0.0f);
        _enemyActor.Color = ShouldFlashEnemyActor() ? new Color(1.0f, 0.92f, 0.92f, 0.14f) : new Color(enemyBaseColor.R, enemyBaseColor.G, enemyBaseColor.B, 0.0f);
    }

    private bool ShouldFlashPlayerActor()
    {
        return IsBattlePresentationWindowActive(1, PlayerStrikeFlashStartSec, PlayerStrikeFlashEndSec);
    }

    private bool ShouldFlashEnemyActor()
    {
        return IsBattlePresentationWindowActive(4, EnemyCounterFlashStartSec, EnemyCounterFlashEndSec);
    }

    private IReadOnlyList<string> BuildVisibleBattleLogLines(IReadOnlyList<string> fullBattleLog)
    {
        var lines = BuildBattlePresentationLines(fullBattleLog);
        if (_scenePhase != ScenePhaseBattle)
        {
            return lines;
        }

        var visibleCount = Math.Min(lines.Count, 1 + (int)Math.Floor(_battlePresentationSec / BattleLogStepDurationSec));
        return lines.Take(visibleCount).ToArray();
    }

    private bool IsBattlePresentationWindowActive(int stepIndex, double relativeStartSec, double relativeEndSec)
    {
        if (_scenePhase != ScenePhaseBattle)
        {
            return false;
        }

        var stepStartSec = stepIndex * BattleLogStepDurationSec;
        return _battlePresentationSec >= stepStartSec + relativeStartSec
            && _battlePresentationSec < stepStartSec + relativeEndSec;
    }

    private List<string> BuildBattlePresentationLines(IReadOnlyList<string> fullBattleLog)
    {
        var lines = fullBattleLog.ToList();
        if (_lastEncounter?.Encounter.Kind == "boss")
        {
            lines.Insert(0, $"首领警报：{_lastEncounter.Encounter.Name} 已降临道路。");
        }

        if (_lastEncounter is not null && _lastEncounter.Encounter.Kind != "chest")
        {
            lines.Insert(Math.Min(2, lines.Count), GetBuildArchetypeByName(_currentBuildArchetype).TriggerLog);
        }

        return lines;
    }

    private double GetBattlePresentationDurationSec()
    {
        if (_lastEncounter is null || _lastEncounter.Encounter.Kind == "chest")
        {
            return 0.0;
        }

        return BuildBattlePresentationLines(_lastEncounter.BattleLog).Count * BattleLogStepDurationSec;
    }

    private void UpdateResultPanel()
    {
        if (_state.IsVictory)
        {
            _resultPanel.Show();
            _resultPanel.Modulate = new Color(0.74f, 1.0f, 0.82f);
            _resultTitleLabel.Modulate = new Color(0.08f, 0.40f, 0.18f);
            _resultTitleLabel.Text = "原型通关";
            _resultSummaryLabel.Text = "魔王先驱倒在了你的流派组合之前。";
            return;
        }

        if (_state.IsGameOver)
        {
            _resultPanel.Show();
            _resultPanel.Modulate = new Color(1.0f, 0.78f, 0.78f);
            _resultTitleLabel.Modulate = new Color(0.55f, 0.10f, 0.10f);
            _resultTitleLabel.Text = "游戏结束";
            _resultSummaryLabel.Text = "行军止步于此。先驱粉碎了这次挑战。";
            return;
        }

        _resultPanel.Hide();
        _resultPanel.Modulate = Colors.White;
        _resultTitleLabel.Modulate = Colors.White;
        _resultTitleLabel.Text = "结果";
        _resultSummaryLabel.Text = "概要";
    }

    private string BuildBuildDirectionText()
    {
        var build = GetBuildArchetypeByName(_currentBuildArchetype);
        return $"流派\n{build.Name}路线\n侧重 {build.Focus}\n被动 {build.PassiveSummary}";
    }

    private string BuildBuildHistoryText()
    {
        if (_buildHistory.Count == 0)
        {
            return "历史\n---";
        }

        return $"历史\n{string.Join(" -> ", _buildHistory)}";
    }

    private void ResetMapState(int chestCount)
    {
        _obstacles.Clear();
        _chests.Clear();

        if (_showcaseMapTexture is not null)
        {
            _playerPosition = RandomPoint();
            _chests.Add(RandomPoint(exclude: [_playerPosition]));
            while (_chests.Count < chestCount)
            {
                TryAddRandomChest(ignoreObstacles: true);
            }

            _encounterMoveSteps = 0;
            _battlePresentationSec = 0.0;
            _rewardFromChest = false;
            return;
        }

        while (true)
        {
            _playerPosition = RandomPoint();
            var firstChest = RandomPoint(exclude: [_playerPosition]);
            var proposedObstacles = BuildObstacleLayout(_playerPosition, firstChest);
            if (proposedObstacles is null)
            {
                continue;
            }

            _obstacles.UnionWith(proposedObstacles);
            _chests.Add(firstChest);

            while (_chests.Count < chestCount)
            {
                TryAddRandomChest();
            }

            RemoveUnreachableChests();
            break;
        }

        _encounterMoveSteps = 0;
        _battlePresentationSec = 0.0;
        _rewardFromChest = false;
    }

    private HashSet<GridPoint>? BuildObstacleLayout(GridPoint player, GridPoint firstChest)
    {
        var obstacles = new HashSet<GridPoint>();
        var attempts = 0;
        while (obstacles.Count < ObstacleCount && attempts < 1000)
        {
            attempts++;
            var point = RandomPoint(exclude: [player, firstChest]);
            obstacles.Add(point);
        }

        return HasPath(player, firstChest, obstacles) ? obstacles : null;
    }

    private void SpawnChestAfterBattle()
    {
        if (_chests.Count >= MaxChestCount)
        {
            return;
        }

        TryAddRandomChest(ignoreObstacles: _showcaseMapTexture is not null);
    }

    private void TryAddRandomChest(bool ignoreObstacles = false)
    {
        for (var attempt = 0; attempt < 200; attempt++)
        {
            var point = RandomPoint(exclude: _chests.Append(_playerPosition).Concat(_obstacles).ToArray());
            if (_chests.Contains(point))
            {
                continue;
            }

            if (!ignoreObstacles && !HasPath(_playerPosition, point, _obstacles))
            {
                continue;
            }

            _chests.Add(point);
            return;
        }
    }

    private void RemoveUnreachableChests()
    {
        _chests.RemoveAll(chest => !HasPath(_playerPosition, chest, _obstacles));
    }

    private GridPoint RandomPoint(IEnumerable<GridPoint>? exclude = null)
    {
        var excluded = exclude is null ? new HashSet<GridPoint>() : new HashSet<GridPoint>(exclude);
        while (true)
        {
            var point = new GridPoint(_random.Next(MapGridSize), _random.Next(MapGridSize));
            if (!excluded.Contains(point))
            {
                return point;
            }
        }
    }

    private static bool IsInside(GridPoint point)
    {
        return point.X >= 0 && point.X < MapGridSize && point.Y >= 0 && point.Y < MapGridSize;
    }

    private static bool HasPath(GridPoint start, GridPoint goal, HashSet<GridPoint> obstacles)
    {
        if (start == goal)
        {
            return true;
        }

        var queue = new Queue<GridPoint>();
        var visited = new HashSet<GridPoint> { start };
        queue.Enqueue(start);

        while (queue.Count > 0)
        {
            var current = queue.Dequeue();
            foreach (var next in EnumerateNeighbors(current))
            {
                if (!IsInside(next) || obstacles.Contains(next) || !visited.Add(next))
                {
                    continue;
                }

                if (next == goal)
                {
                    return true;
                }

                queue.Enqueue(next);
            }
        }

        return false;
    }

    private static IEnumerable<GridPoint> EnumerateNeighbors(GridPoint point)
    {
        yield return new GridPoint(point.X + 1, point.Y);
        yield return new GridPoint(point.X - 1, point.Y);
        yield return new GridPoint(point.X, point.Y + 1);
        yield return new GridPoint(point.X, point.Y - 1);
    }

    private static BuildArchetype GetBuildArchetypeForRewardIndex(int rewardIndex)
    {
        return ClampRewardIndex(rewardIndex) switch
        {
            0 => new BuildArchetype("先锋", "攻击 / 节奏", "先手额外施加 1 点压制。", "先锋被动发动，进一步施压。", "锋", new Color(0.86f, 0.39f, 0.28f)),
            1 => new BuildArchetype("守护", "生命 / 防御", "长线作战时减少承受伤害。", "守护被动发动，稳住了反击。", "守", new Color(0.33f, 0.56f, 0.80f)),
            _ => new BuildArchetype("猎手", "暴击 / 爆发", "在下一次交锋前提高暴击率。", "猎手被动锁定弱点，打出爆发。", "猎", new Color(0.42f, 0.78f, 0.50f))
        };
    }

    private static BuildArchetype GetBuildArchetypeByName(string archetypeName)
    {
        return archetypeName switch
        {
            "Vanguard" or "先锋" => new BuildArchetype("先锋", "攻击 / 节奏", "先手额外施加 1 点压制。", "先锋被动发动，进一步施压。", "锋", new Color(0.86f, 0.39f, 0.28f)),
            "Guardian" or "守护" => new BuildArchetype("守护", "生命 / 防御", "长线作战时减少承受伤害。", "守护被动发动，稳住了反击。", "守", new Color(0.33f, 0.56f, 0.80f)),
            "Hunter" or "猎手" => new BuildArchetype("猎手", "暴击 / 爆发", "在下一次交锋前提高暴击率。", "猎手被动锁定弱点，打出爆发。", "猎", new Color(0.42f, 0.78f, 0.50f)),
            _ => new BuildArchetype("均衡", "综合成长", "尚未形成专精被动。", "均衡行军，稳步推进。", "---", new Color(0.262745f, 0.537255f, 0.45098f))
        };
    }

    private static int ClampRewardIndex(int rewardIndex)
    {
        if (rewardIndex < 0)
        {
            return 0;
        }

        if (rewardIndex > 2)
        {
            return 2;
        }

        return rewardIndex;
    }

    private bool AreUiNodesAlive()
    {
        return GodotObject.IsInstanceValid(this)
            && GodotObject.IsInstanceValid(_gridRoot)
            && GodotObject.IsInstanceValid(_statusLabel)
            && GodotObject.IsInstanceValid(_chestLabel)
            && GodotObject.IsInstanceValid(_battleLogLabel)
            && GodotObject.IsInstanceValid(_playerActor)
            && GodotObject.IsInstanceValid(_enemyActor)
            && GodotObject.IsInstanceValid(_transitionFlash);
    }

    private void UpdateSceneVisibility()
    {
        var shouldShowMap = _scenePhase == ScenePhaseMap || (_scenePhase == ScenePhaseReward && _rewardFromChest);
        var shouldShowBattle = _scenePhase == ScenePhaseBattle
            || _scenePhase == ScenePhaseComplete
            || (_scenePhase == ScenePhaseReward && !_rewardFromChest);

        if (shouldShowMap)
        {
            if (!_mapSceneRoot.Visible)
            {
                _mapSceneRoot.Visible = true;
                _mapSceneRoot.Modulate = new Color(1, 1, 1, 0);
                PlaySceneFade(_mapSceneRoot);
            }
        }
        else
        {
            _mapSceneRoot.Visible = false;
            _mapSceneRoot.Modulate = new Color(1, 1, 1, 0);
        }

        if (shouldShowBattle)
        {
            if (!_battleSceneRoot.Visible)
            {
                _battleSceneRoot.Visible = true;
                _battleSceneRoot.Modulate = new Color(1, 1, 1, 0);
                PlaySceneFade(_battleSceneRoot);
            }
        }
        else
        {
            _battleSceneRoot.Visible = false;
            _battleSceneRoot.Modulate = new Color(1, 1, 1, 0);
        }
    }

    private void AnimatePlayerTokenToCurrentCell()
    {
        _playerMoveTween?.Kill();
        _playerMoveTween = CreateTween();
        _playerMoveTween.TweenProperty(
            _playerToken,
            "position",
            new Vector2((_playerPosition.X * MapCellSize) + 10, (_playerPosition.Y * MapCellSize) + 10),
            MapMoveTweenDurationSec);
        _playerMoveTween.Finished += () => _playerMoveTween = null;
    }

    private void PlaySceneFade(CanvasItem target)
    {
        _sceneFadeTween?.Kill();
        _sceneFadeTween = CreateTween();
        _sceneFadeTween.TweenProperty(target, "modulate:a", 1.0f, SceneFadeDurationSec);
        _sceneFadeTween.Finished += () => _sceneFadeTween = null;
    }

    private void PlayRewardPanelFadeIn()
    {
        _rewardPanelTween?.Kill();
        _rewardPanelTween = CreateTween();
        _rewardPanelTween.TweenProperty(_rewardPanel, "modulate:a", 1.0f, RewardPanelFadeDurationSec);
        _rewardPanelTween.Finished += () => _rewardPanelTween = null;
    }

    private void PlayEncounterFlash()
    {
        _transitionFlashTween?.Kill();
        _transitionFlash.Visible = true;
        _transitionFlash.Modulate = new Color(1, 1, 1, 0.9f);
        _transitionFlashTween = CreateTween();
        _transitionFlashTween.TweenProperty(_transitionFlash, "modulate:a", 0.0f, EncounterFlashDurationSec);
        _transitionFlashTween.Finished += () =>
        {
            _transitionFlash.Visible = false;
            _transitionFlashTween = null;
        };
    }

    private void PlayEncounterPunch()
    {
        _encounterPunchTween?.Kill();
        _contentRoot.Scale = Vector2.One;
        _contentRoot.Position = _contentRootBasePosition;

        _encounterPunchTween = CreateTween();
        _encounterPunchTween.SetParallel(true);
        _encounterPunchTween.TweenProperty(_contentRoot, "scale", EncounterPunchScale, EncounterPunchDurationSec)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.Out);
        _encounterPunchTween.TweenProperty(_contentRoot, "position", _contentRootBasePosition + EncounterPunchOffset, EncounterPunchDurationSec)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.Out);

        _encounterPunchTween.Chain().SetParallel(true);
        _encounterPunchTween.TweenProperty(_contentRoot, "scale", Vector2.One, EncounterPunchDurationSec)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.In);
        _encounterPunchTween.TweenProperty(_contentRoot, "position", _contentRootBasePosition, EncounterPunchDurationSec)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.In);

        _encounterPunchTween.Finished += () =>
        {
            _contentRoot.Scale = Vector2.One;
            _contentRoot.Position = _contentRootBasePosition;
            _encounterPunchTween = null;
        };
    }

    private static Color BuildCellColor(GridPoint point, IReadOnlyCollection<GridPoint> chests, IReadOnlySet<GridPoint> obstacles, GridPoint playerPosition)
    {
        if (obstacles.Contains(point))
        {
            return ((point.X + point.Y) % 2) == 0
                ? new Color(0.92f, 0.94f, 0.98f)
                : new Color(0.82f, 0.85f, 0.92f);
        }

        if (chests.Contains(point))
        {
            return ((point.X + point.Y) % 2) == 0
                ? new Color(0.18f, 0.38f, 0.88f)
                : new Color(0.26f, 0.48f, 1.0f);
        }

        if (point == playerPosition)
        {
            return ((point.X + point.Y) % 2) == 0
                ? new Color(0.96f, 0.88f, 0.24f)
                : new Color(1.0f, 0.96f, 0.42f);
        }

        return ((point.X + point.Y) % 2) == 0
            ? new Color(0.06f, 0.07f, 0.09f)
            : new Color(0.10f, 0.11f, 0.14f);
    }
}
