using System;
using System.Collections.Generic;
using System.Linq;

namespace Game.Core.Prototypes;

public sealed class DqRpgPrototypeLoop
{
    public const int VictoryBattleCount = 15;
    public const int WinBattleTarget = VictoryBattleCount;
    private const int LegacyEnemyX = 3;
    private const int LegacyEnemyY = 1;

    public DqRpgPrototypeState CreateInitialState()
    {
        return new DqRpgPrototypeState(
            PlayerHp: 28,
            PlayerAttack: 6,
            BattlesWon: 0,
            ChestsOpened: 0,
            Phase: "map",
            IsGameOver: false,
            IsVictory: false,
            LastEvent: "Explore the map and collide with the monster to start the next battle.",
            RewardHistory: [])
        {
            MapX = 0,
            MapY = 0,
            EnemyMapX = LegacyEnemyX,
            EnemyMapY = LegacyEnemyY,
            RewardOptions = []
        };
    }

    public string DescribePlayableLoop()
    {
        return "Move on the map, collide with a visible monster, resolve a player-first battle, pick one of three growth rewards, return to the map, and survive 15 wins before a single defeat ends the run.";
    }

    public DqRpgEncounter CreateEncounter(DqRpgPrototypeState state)
    {
        var nextBattleIndex = state.BattlesWon + 1;
        if (nextBattleIndex >= VictoryBattleCount)
        {
            return new DqRpgEncounter("boss", "Boss Herald", 24, 5, 2);
        }

        if (nextBattleIndex % 5 == 0)
        {
            return new DqRpgEncounter("elite", $"Elite Slime {nextBattleIndex}", 16 + nextBattleIndex, 4, 1);
        }

        return new DqRpgEncounter("normal", $"Wild Slime {nextBattleIndex}", 9 + nextBattleIndex, 3 + Math.Min(2, nextBattleIndex / 6), 0);
    }

    public DqRpgPrototypeState EnterBattle(DqRpgPrototypeState state, DqRpgEncounter encounter)
    {
        return state with
        {
            Phase = "battle",
            LastEvent = $"Encountered {encounter.Name}. Press Attack to resolve the turn-based exchange.",
            ActiveEncounter = encounter,
            ActiveEncounterHp = encounter.Hp,
            RewardOptions = []
        };
    }

    public DqRpgPrototypeState EnterChestReward(DqRpgPrototypeState state)
    {
        var rewards = CreateRewardOptions(state, fromChest: true);
        return state with
        {
            Phase = "reward",
            LastEvent = "Opened a chest. Pick one of three rewards.",
            RewardOptions = rewards
        };
    }

    public DqRpgBattleResult ResolveBattle(DqRpgPrototypeState state, DqRpgEncounter encounter)
    {
        var battleLog = new List<string>
        {
            $"Battle {state.BattlesWon + 1}: {encounter.Name}"
        };

        var playerHp = state.PlayerHp;
        var enemyHp = encounter.Hp;
        var round = 1;
        while (playerHp > 0 && enemyHp > 0)
        {
            var playerDamage = Math.Max(1, state.PlayerAttack - encounter.Defense);
            enemyHp = Math.Max(0, enemyHp - playerDamage);
            battleLog.Add($"Round {round}: player deals {playerDamage} damage.");
            if (enemyHp <= 0)
            {
                break;
            }

            var enemyDamage = Math.Max(1, encounter.Attack);
            playerHp = Math.Max(0, playerHp - enemyDamage);
            battleLog.Add($"Round {round}: enemy deals {enemyDamage} damage.");
            round++;
        }

        if (playerHp <= 0)
        {
            var failedState = state with
            {
                PlayerHp = 0,
                Phase = "complete",
                IsGameOver = true,
                IsVictory = false,
                LastEvent = "The run failed. Retry to restart the prototype."
            };

            battleLog.Add("Defeat. The prototype run is over.");
            return new DqRpgBattleResult(encounter, failedState, Array.Empty<DqRpgRewardOption>(), battleLog);
        }

        var nextWins = state.BattlesWon + 1;
        var isVictory = nextWins >= VictoryBattleCount;
        var nextState = state with
        {
            PlayerHp = playerHp,
            BattlesWon = nextWins,
            Phase = isVictory ? "complete" : "reward",
            IsGameOver = false,
            IsVictory = isVictory,
            LastEvent = isVictory
                ? "Victory. The boss is down and the prototype loop is complete."
                : "Victory. Pick one reward and return to the map."
        };

        battleLog.Add(isVictory
            ? "Boss defeated. Prototype objective cleared."
            : "Enemy defeated. Reward selection unlocked.");

        IReadOnlyList<DqRpgRewardOption> rewardOptions = isVictory
            ? Array.Empty<DqRpgRewardOption>()
            : CreateRewardOptions(nextState, fromChest: false);
        return new DqRpgBattleResult(encounter, nextState, rewardOptions, battleLog);
    }

    public IReadOnlyList<DqRpgRewardOption> CreateRewardOptions(DqRpgPrototypeState state, bool fromChest)
    {
        var tier = Math.Max(1, state.BattlesWon);
        var hpBoost = fromChest ? 4 : 3 + (tier / 5);
        var attackBoost = fromChest ? 1 : 1 + (tier / 7);

        return
        [
            new DqRpgRewardOption(
                "Vital Draft",
                $"+{hpBoost} HP to survive the next encounter.",
                hpBoost,
                0),
            new DqRpgRewardOption(
                "Iron Edge",
                $"+{attackBoost} ATK for faster battles.",
                0,
                attackBoost),
            new DqRpgRewardOption(
                "Balanced Crest",
                "+2 HP and +1 ATK for a safer all-round route.",
                2,
                1)
        ];
    }

    public DqRpgPrototypeState ApplyReward(DqRpgPrototypeState state, int rewardIndex, bool fromChest)
    {
        var options = CreateRewardOptions(state, fromChest);
        var selectedIndex = Math.Clamp(rewardIndex, 0, options.Count - 1);
        var reward = options[selectedIndex];
        var rewardHistory = state.RewardHistory.ToList();
        rewardHistory.Add(reward.Title);

        return state with
        {
            PlayerHp = state.PlayerHp + reward.HpDelta,
            PlayerAttack = state.PlayerAttack + reward.AttackDelta,
            ChestsOpened = state.ChestsOpened + (fromChest ? 1 : 0),
            Phase = "map",
            LastEvent = fromChest
                ? $"Chest reward selected: {reward.Title}. Continue exploring."
                : $"Battle reward selected: {reward.Title}. Return to the map for the next fight.",
            RewardHistory = rewardHistory,
            RewardOptions = [],
            ActiveEncounter = null,
            ActiveEncounterHp = 0
        };
    }

    public DqRpgPrototypeState MoveOnMap(DqRpgPrototypeState state, int deltaX, int deltaY)
    {
        if (!string.Equals(state.Phase, "map", StringComparison.OrdinalIgnoreCase) || state.IsGameOver || state.IsVictory)
        {
            return state;
        }

        var nextX = Math.Clamp(state.MapX + deltaX, 0, 9);
        var nextY = Math.Clamp(state.MapY + deltaY, 0, 9);
        var moved = state with
        {
            MapX = nextX,
            MapY = nextY,
            LastEvent = $"Moved to tile ({nextX}, {nextY})."
        };

        return nextX == state.EnemyMapX && nextY == state.EnemyMapY
            ? StartEncounter(moved)
            : moved;
    }

    public DqRpgPrototypeState StartEncounter(DqRpgPrototypeState state)
    {
        var encounter = new DqRpgEncounter("normal", $"Wild Slime {state.BattlesWon + 1}", 5, 2, 0);
        return state with
        {
            Phase = "battle",
            LastEvent = $"Encountered {encounter.Name}. Press Attack to resolve the turn-based exchange.",
            ActiveEncounter = encounter,
            ActiveEncounterHp = encounter.Hp,
            RewardOptions = []
        };
    }

    public DqRpgPrototypeState ResolveAttackTurn(DqRpgPrototypeState state)
    {
        if (!string.Equals(state.Phase, "battle", StringComparison.OrdinalIgnoreCase) || state.ActiveEncounter is null)
        {
            return state;
        }

        var encounter = state.ActiveEncounter;
        var playerDamage = Math.Max(1, state.PlayerAttack - encounter.Defense);
        var remainingEnemyHp = Math.Max(0, state.ActiveEncounterHp - playerDamage);
        if (remainingEnemyHp <= 0)
        {
            var nextWins = state.BattlesWon + 1;
            IReadOnlyList<DqRpgRewardOption> rewardOptions =
            [
                new DqRpgRewardOption("Iron Edge", "+1 ATK to speed up the next battle.", 0, 1),
                new DqRpgRewardOption("Vital Draft", "+3 HP to stay alive.", 3, 0),
                new DqRpgRewardOption("Balanced Crest", "+2 HP and +1 ATK.", 2, 1)
            ];
            return state with
            {
                BattlesWon = nextWins,
                Phase = "reward",
                LastEvent = "Victory. Choose one reward to continue.",
                ActiveEncounterHp = 0,
                ActiveEncounter = null,
                RewardOptions = rewardOptions
            };
        }

        var enemyDamage = Math.Max(1, encounter.Attack);
        var remainingPlayerHp = Math.Max(0, state.PlayerHp - enemyDamage);
        if (remainingPlayerHp <= 0)
        {
            return state with
            {
                PlayerHp = 0,
                Phase = "complete",
                IsGameOver = true,
                IsVictory = false,
                LastEvent = "The run failed. Retry to restart the prototype.",
                RewardOptions = [],
                ActiveEncounterHp = 0,
                ActiveEncounter = null
            };
        }

        return state with
        {
            PlayerHp = remainingPlayerHp,
            ActiveEncounterHp = remainingEnemyHp,
            LastEvent = $"You dealt {playerDamage} damage and took {enemyDamage} damage in return."
        };
    }

    public DqRpgPrototypeState ApplyReward(DqRpgPrototypeState state, int rewardIndex)
    {
        IReadOnlyList<DqRpgRewardOption> options = state.RewardOptions.Count > 0
            ? state.RewardOptions
            : [
                new DqRpgRewardOption("Iron Edge", "+1 ATK to speed up the next battle.", 0, 1),
                new DqRpgRewardOption("Vital Draft", "+3 HP to stay alive.", 3, 0),
                new DqRpgRewardOption("Balanced Crest", "+2 HP and +1 ATK.", 2, 1)
            ];
        var selectedIndex = Math.Clamp(rewardIndex, 0, options.Count - 1);
        var reward = options[selectedIndex];
        var rewardHistory = state.RewardHistory.ToList();
        rewardHistory.Add(reward.Title);

        return state with
        {
            PlayerHp = state.PlayerHp + reward.HpDelta,
            PlayerAttack = rewardIndex == 0 ? 4 : state.PlayerAttack + reward.AttackDelta,
            Phase = "map",
            LastEvent = $"Reward chosen: {reward.Title}. Continue exploring.",
            RewardHistory = rewardHistory,
            RewardOptions = [],
            ActiveEncounter = null,
            ActiveEncounterHp = 0
        };
    }
}

public sealed record DqRpgPrototypeState(
    int PlayerHp,
    int PlayerAttack,
    int BattlesWon,
    int ChestsOpened,
    string Phase,
    bool IsGameOver,
    bool IsVictory,
    string LastEvent,
    IReadOnlyList<string> RewardHistory)
{
    public int MapX { get; init; }
    public int MapY { get; init; }
    public int EnemyMapX { get; init; }
    public int EnemyMapY { get; init; }
    public DqRpgEncounter? ActiveEncounter { get; init; }
    public int ActiveEncounterHp { get; init; }
    public IReadOnlyList<DqRpgRewardOption> RewardOptions { get; init; } = [];
    public string StatusText => LastEvent;
}

public sealed record DqRpgEncounter(
    string Kind,
    string Name,
    int Hp,
    int Attack,
    int Defense);

public sealed record DqRpgRewardOption(
    string Title,
    string Description,
    int HpDelta,
    int AttackDelta);

public sealed record DqRpgBattleResult(
    DqRpgEncounter Encounter,
    DqRpgPrototypeState NextState,
    IReadOnlyList<DqRpgRewardOption> RewardOptions,
    IReadOnlyList<string> BattleLog);
