using System.Collections.Generic;
using System.Linq;
using System.Text;
using Game.Core.Prototypes;
using Godot;

namespace Game.Godot.Prototypes;

public partial class DqRpgPrototype : Node2D
{
    private readonly DqRpgPrototypeLoop _loop = new();

    private DqRpgPrototypeState _state = default!;
    private DqRpgEncounter? _currentEncounter;
    private IReadOnlyList<DqRpgRewardOption> _currentRewards = [];
    private bool _rewardFromChest;

    private Label _headerLabel = default!;
    private Label _statsLabel = default!;
    private Label _objectiveLabel = default!;
    private RichTextLabel _logLabel = default!;
    private ColorRect _playerToken = default!;
    private ColorRect _enemyToken = default!;
    private ColorRect _chestToken = default!;
    private ColorRect _enemyMapToken = default!;
    private PanelContainer _rewardPanel = default!;
    private Button[] _rewardButtons = [];

    private Vector2I _playerGrid = new(1, 1);
    private Vector2I _enemyGrid = new(8, 4);
    private Vector2I _chestGrid = new(4, 7);

    private const int GridSize = 10;
    private const int CellSize = 48;
    private const float GridInset = 16.0f;

    public override void _Ready()
    {
        _headerLabel = GetNode<Label>("CanvasLayer/UI/HeaderLabel");
        _statsLabel = GetNode<Label>("CanvasLayer/UI/StatsLabel");
        _objectiveLabel = GetNode<Label>("CanvasLayer/UI/ObjectiveLabel");
        _logLabel = GetNode<RichTextLabel>("CanvasLayer/UI/LogPanel/LogLabel");
        _rewardPanel = GetNode<PanelContainer>("CanvasLayer/UI/RewardPanel");
        _playerToken = GetNode<ColorRect>("Map/PlayerToken");
        _enemyToken = GetNode<ColorRect>("Battle/EnemyToken");
        _chestToken = GetNode<ColorRect>("Map/ChestToken");
        _enemyMapToken = GetNode<ColorRect>("Map/EnemyToken");
        _rewardButtons =
        [
            GetNode<Button>("CanvasLayer/UI/RewardPanel/RewardVBox/RewardOption1"),
            GetNode<Button>("CanvasLayer/UI/RewardPanel/RewardVBox/RewardOption2"),
            GetNode<Button>("CanvasLayer/UI/RewardPanel/RewardVBox/RewardOption3")
        ];

        for (var i = 0; i < _rewardButtons.Length; i++)
        {
            var index = i;
            _rewardButtons[i].Pressed += () => SelectReward(index);
        }

        _state = _loop.CreateInitialState();
        UpdateMapTokenPositions();
        RefreshView();
        AppendLog(_loop.DescribePlayableLoop());
    }

    public override void _UnhandledInput(InputEvent @event)
    {
        if (@event is not InputEventKey keyEvent || !keyEvent.Pressed || keyEvent.Echo)
        {
            return;
        }

        if (_rewardPanel.Visible)
        {
            if (keyEvent.Keycode is Key.Key1 or Key.Kp1)
            {
                SelectReward(0);
            }
            else if (keyEvent.Keycode is Key.Key2 or Key.Kp2)
            {
                SelectReward(1);
            }
            else if (keyEvent.Keycode is Key.Key3 or Key.Kp3)
            {
                SelectReward(2);
            }

            return;
        }

        if (_state.IsGameOver || _state.IsVictory)
        {
            if (keyEvent.Keycode == Key.R)
            {
                RestartRun();
            }

            return;
        }

        if (_state.Phase == "map")
        {
            var direction = keyEvent.Keycode switch
            {
                Key.W => new Vector2I(0, -1),
                Key.S => new Vector2I(0, 1),
                Key.A => new Vector2I(-1, 0),
                Key.D => new Vector2I(1, 0),
                _ => Vector2I.Zero
            };

            if (direction != Vector2I.Zero)
            {
                MoveOnMap(direction);
            }

            return;
        }

        if (_state.Phase == "battle" && keyEvent.Keycode == Key.Space)
        {
            ResolveCurrentBattle();
        }
    }

    private void MoveOnMap(Vector2I direction)
    {
        var next = new Vector2I(
            Mathf.Clamp(_playerGrid.X + direction.X, 0, GridSize - 1),
            Mathf.Clamp(_playerGrid.Y + direction.Y, 0, GridSize - 1));

        if (next == _playerGrid)
        {
            return;
        }

        _playerGrid = next;
        UpdateMapTokenPositions();

        if (_playerGrid == _enemyGrid)
        {
            StartEncounter();
            return;
        }

        if (_playerGrid == _chestGrid)
        {
            StartChestReward();
            return;
        }

        _state = _state with
        {
            LastEvent = $"Moved to tile ({_playerGrid.X}, {_playerGrid.Y})."
        };
        RefreshView();
    }

    private void StartEncounter()
    {
        var encounter = _loop.CreateEncounter(_state);
        _currentEncounter = encounter;
        _state = _loop.EnterBattle(_state, encounter);
        AppendLog(_state.LastEvent);
        RefreshView();
    }

    private void ResolveCurrentBattle()
    {
        if (_currentEncounter is null)
        {
            return;
        }

        var result = _loop.ResolveBattle(_state, _currentEncounter);
        _state = result.NextState;
        _currentRewards = result.RewardOptions;

        foreach (var line in result.BattleLog)
        {
            AppendLog(line);
        }

        if (_state.IsGameOver || _state.IsVictory)
        {
            _currentEncounter = null;
            RefreshView();
            return;
        }

        _rewardFromChest = false;
        ShowRewards(_currentRewards);
        RefreshView();
    }

    private void StartChestReward()
    {
        _rewardFromChest = true;
        _state = _loop.EnterChestReward(_state);
        _currentRewards = _loop.CreateRewardOptions(_state, fromChest: true);
        AppendLog(_state.LastEvent);
        ShowRewards(_currentRewards);
        RefreshView();
    }

    private void ShowRewards(IReadOnlyList<DqRpgRewardOption> rewards)
    {
        for (var i = 0; i < _rewardButtons.Length; i++)
        {
            if (i < rewards.Count)
            {
                var reward = rewards[i];
                _rewardButtons[i].Text = $"{i + 1}. {reward.Title}\n{reward.Description}";
                _rewardButtons[i].Visible = true;
                _rewardButtons[i].Disabled = false;
            }
            else
            {
                _rewardButtons[i].Visible = false;
                _rewardButtons[i].Disabled = true;
            }
        }

        _rewardPanel.Visible = true;
    }

    private void SelectReward(int rewardIndex)
    {
        if (!_rewardPanel.Visible)
        {
            return;
        }

        _state = _loop.ApplyReward(_state, rewardIndex, _rewardFromChest);
        _currentRewards = [];
        _rewardPanel.Visible = false;
        _currentEncounter = null;

        if (_rewardFromChest)
        {
            _chestGrid = FindNextOpenTile(preferUpperHalf: false);
        }
        else
        {
            _enemyGrid = FindNextOpenTile(preferUpperHalf: true);
        }

        _rewardFromChest = false;
        UpdateMapTokenPositions();
        AppendLog(_state.LastEvent);
        RefreshView();
    }

    private void RestartRun()
    {
        _state = _loop.CreateInitialState();
        _currentEncounter = null;
        _currentRewards = [];
        _rewardFromChest = false;
        _playerGrid = new Vector2I(1, 1);
        _enemyGrid = new Vector2I(8, 4);
        _chestGrid = new Vector2I(4, 7);
        _rewardPanel.Visible = false;
        _logLabel.Clear();
        AppendLog("Prototype restarted.");
        AppendLog(_loop.DescribePlayableLoop());
        UpdateMapTokenPositions();
        RefreshView();
    }

    private Vector2I FindNextOpenTile(bool preferUpperHalf)
    {
        for (var y = 0; y < GridSize; y++)
        {
            var actualY = preferUpperHalf ? y : GridSize - 1 - y;
            for (var x = 0; x < GridSize; x++)
            {
                var candidate = new Vector2I(x, actualY);
                if (candidate != _playerGrid && candidate != _enemyGrid && candidate != _chestGrid)
                {
                    return candidate;
                }
            }
        }

        return new Vector2I(0, 0);
    }

    private void UpdateMapTokenPositions()
    {
        _playerToken.Position = GridToPosition(_playerGrid);
        _enemyMapToken.Position = GridToPosition(_enemyGrid);
        _chestToken.Position = GridToPosition(_chestGrid);
    }

    private static Vector2 GridToPosition(Vector2I point)
    {
        return new Vector2(
            GridInset + (point.X * CellSize),
            GridInset + (point.Y * CellSize));
    }

    private void RefreshView()
    {
        var mapVisible = _state.Phase == "map" || _state.Phase == "reward" || _state.IsGameOver || _state.IsVictory;
        GetNode<Control>("Map").Visible = mapVisible;
        GetNode<Control>("Battle").Visible = _state.Phase == "battle";
        _rewardPanel.Visible = _rewardPanel.Visible && !_state.IsGameOver && !_state.IsVictory;
        _enemyMapToken.Visible = _state.Phase != "battle";
        _enemyToken.Visible = _state.Phase == "battle";

        _headerLabel.Text = _state.Phase switch
        {
            "map" => "DQ RPG Prototype - Map",
            "battle" => $"DQ RPG Prototype - Battle: {_currentEncounter?.Name ?? "Unknown"}",
            "reward" => "DQ RPG Prototype - Reward",
            _ => _state.IsVictory ? "DQ RPG Prototype - Victory" : "DQ RPG Prototype - Defeat"
        };

        _statsLabel.Text = $"HP: {_state.PlayerHp}   ATK: {_state.PlayerAttack}   Wins: {_state.BattlesWon}/{DqRpgPrototypeLoop.WinBattleTarget}   Chests: {_state.ChestsOpened}";

        _objectiveLabel.Text = BuildObjectiveText();
        var enemyModulate = _currentEncounter?.Kind switch
        {
            "boss" => new Color(0.82f, 0.20f, 0.20f),
            "elite" => new Color(0.86f, 0.48f, 0.16f),
            _ => new Color(0.56f, 0.22f, 0.72f)
        };
        _enemyToken.Color = enemyModulate;
    }

    private string BuildObjectiveText()
    {
        if (_state.IsVictory)
        {
            return "Boss defeated. Prototype loop proved. Press R to restart.";
        }

        if (_state.IsGameOver)
        {
            return "Run failed after one defeat. Press R to retry.";
        }

        if (_rewardPanel.Visible)
        {
            return "Pick 1/2/3 to select a reward and continue.";
        }

        return _state.Phase switch
        {
            "map" => "Use WASD to move. Touch the chest for rewards or collide with the monster to enter battle.",
            "battle" => "Press Space to resolve the player-first turn-based attack exchange.",
            _ => _state.LastEvent
        };
    }

    private void AppendLog(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
        {
            return;
        }

        var existing = _logLabel.Text;
        var builder = new StringBuilder();
        if (!string.IsNullOrWhiteSpace(existing))
        {
            builder.Append(existing.TrimEnd());
            builder.Append('\n');
        }

        builder.Append("- ");
        builder.Append(line);
        _logLabel.Text = builder.ToString();
        _logLabel.ScrollToLine(_logLabel.GetLineCount());
    }
}
