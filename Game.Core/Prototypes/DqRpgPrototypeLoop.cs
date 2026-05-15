using System;
using System.Collections.Generic;
using System.Linq;

namespace Game.Core.Prototypes;

public sealed class DqRpgPrototypeLoop
{
    public const int VictoryBattleCount = 15;
    public const int WinBattleTarget = VictoryBattleCount;

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
            RewardHistory: []);
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
            LastEvent = $"Encountered {encounter.Name}. Press Attack to resolve the turn-based exchange."
        };
    }

    public DqRpgPrototypeState EnterChestReward(DqRpgPrototypeState state)
    {
        return state with
        {
            Phase = "reward",
            LastEvent = "Opened a chest. Pick one of three rewards."
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
            return new DqRpgBattleResult(encounter, failedState, [], battleLog);
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

        var rewardOptions = isVictory ? [] : CreateRewardOptions(nextState, fromChest: false);
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
            RewardHistory = rewardHistory
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
    IReadOnlyList<string> RewardHistory);

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
