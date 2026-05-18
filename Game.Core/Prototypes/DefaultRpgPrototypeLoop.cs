namespace Game.Core.Prototypes;

public sealed class DefaultRpgPrototypeLoop
{
    public DefaultRpgPrototypeState CreateInitialState()
    {
        return new DefaultRpgPrototypeState(
            StepIndex: 1,
            PlayerHp: 42,
            PlayerAttack: 11,
            PlayerDefense: 4,
            CritRate: 0.15,
            PassiveSkills: ["先发制人"],
            EquippedItems: ["旅者之刃"],
            Phase: "battle",
            IsGameOver: false,
            IsVictory: false);
    }

    public DefaultRpgEncounterResult ResolveEncounter(DefaultRpgPrototypeState state)
    {
        var encounter = BuildEncounter(state.StepIndex);
        var critTriggered = state.CritRate >= 0.30;
        var playerDamage = Math.Max(1, state.PlayerAttack - encounter.Defense) + (critTriggered ? 2 : 0);
        var enemyDamage = Math.Max(1, encounter.Attack - state.PlayerDefense);

        var enemyHpAfterPlayerTurn = Math.Max(0, encounter.Hp - playerDamage);
        var playerHpAfterBattle = Math.Max(0, state.PlayerHp - (enemyHpAfterPlayerTurn > 0 ? enemyDamage : 0));

        if (encounter.Kind == "boss")
        {
            var bossHp = encounter.Hp;
            var playerHp = state.PlayerHp;

            while (bossHp > 0 && playerHp > 0)
            {
                bossHp = Math.Max(0, bossHp - playerDamage);
                if (bossHp <= 0)
                {
                    break;
                }

                playerHp = Math.Max(0, playerHp - enemyDamage);
            }

            enemyHpAfterPlayerTurn = bossHp;
            playerHpAfterBattle = playerHp;
        }

        var gameOver = playerHpAfterBattle <= 0;
        var victory = !gameOver && encounter.Kind == "boss" && enemyHpAfterPlayerTurn <= 0;
        var phase = gameOver || victory ? "complete" : "reward";

        var nextState = state with
        {
            PlayerHp = playerHpAfterBattle,
            Phase = phase,
            IsGameOver = gameOver,
            IsVictory = victory,
            StepIndex = gameOver || victory ? state.StepIndex : state.StepIndex + 1
        };

        var rewardOptions = gameOver || victory ? [] : BuildRewardOptions(state.StepIndex);
        var battleLog = new List<string>
        {
            $"第 {state.StepIndex} 战：{encounter.Name}",
            $"我方先手，造成 {playerDamage} 点伤害。",
            critTriggered ? "暴击被动触发，追加了爆发伤害。" : "本回合未触发暴击被动。",
            enemyHpAfterPlayerTurn <= 0
                ? $"{encounter.Name} 尚未反击便被击败。"
                : $"{encounter.Name} 反击，造成 {enemyDamage} 点伤害。",
            gameOver
                ? "我方生命归零。游戏结束。"
                : victory
                    ? "首领被击败，原型通关。"
                    : "请从三项肉鸽奖励中选择其一。"
        };

        return new DefaultRpgEncounterResult(encounter, nextState, rewardOptions, battleLog);
    }

    public DefaultRpgPrototypeState ApplyReward(DefaultRpgPrototypeState state, int rewardIndex)
    {
        var rewards = BuildRewardOptions(Math.Max(1, state.StepIndex - 1));
        var reward = rewards[ClampRewardIndex(rewardIndex, rewards.Count)];
        var passiveSkills = state.PassiveSkills.ToList();
        var equippedItems = state.EquippedItems.ToList();

        var nextState = state with
        {
            Phase = "battle"
        };

        switch (reward.Category)
        {
            case "equipment":
                equippedItems.Add(reward.Title);
                nextState = nextState with
                {
                    PlayerHp = state.PlayerHp + reward.HpDelta,
                    PlayerAttack = state.PlayerAttack + reward.AttackDelta,
                    PlayerDefense = state.PlayerDefense + reward.DefenseDelta,
                    EquippedItems = equippedItems
                };
                break;
            case "attribute":
                nextState = nextState with
                {
                    PlayerHp = state.PlayerHp + reward.HpDelta,
                    PlayerAttack = state.PlayerAttack + reward.AttackDelta,
                    PlayerDefense = state.PlayerDefense + reward.DefenseDelta,
                    CritRate = Math.Min(0.75, state.CritRate + reward.CritDelta)
                };
                break;
            case "skill":
                passiveSkills.Add(reward.Title);
                nextState = nextState with
                {
                    PlayerAttack = state.PlayerAttack + reward.AttackDelta,
                    PlayerDefense = state.PlayerDefense + reward.DefenseDelta,
                    PlayerHp = state.PlayerHp + reward.HpDelta,
                    CritRate = Math.Min(0.75, state.CritRate + reward.CritDelta),
                    PassiveSkills = passiveSkills
                };
                break;
        }

        return nextState;
    }

    public DefaultRpgPrototypeResult ResolveBattleAndReward(
        int playerHp,
        int playerAttack,
        int playerDefense,
        double critRate,
        int enemyHp,
        int enemyAttack,
        int enemyDefense,
        int rewardSeed)
    {
        var encounterTriggered = true;
        var playerTurnDamage = Math.Max(1, playerAttack - enemyDefense);
        var enemyTurnDamage = enemyHp > playerTurnDamage
            ? Math.Max(1, enemyAttack - playerDefense)
            : 0;

        var playerHpAfterBattle = Math.Max(0, playerHp - enemyTurnDamage);
        var rewardCategory = RewardCategories[Math.Abs(rewardSeed - 1) % RewardCategories.Length];

        return new DefaultRpgPrototypeResult(
            EncounterTriggered: encounterTriggered,
            BattleResolved: true,
            PlayerHpAfterBattle: playerHpAfterBattle,
            RewardCategory: rewardCategory,
            CritRate: critRate);
    }

    private static DefaultRpgEncounter BuildEncounter(int stepIndex)
    {
        if (stepIndex >= 15)
        {
            return new DefaultRpgEncounter("boss", "首领：魔王先驱", 30, 12, 6);
        }

        if (stepIndex % 5 == 0)
        {
            return new DefaultRpgEncounter("elite", $"精英 {stepIndex / 5}：黑甲队长", 20 + stepIndex, 9, 4);
        }

        var normalAttack = 6 + (stepIndex / 3);
        if (stepIndex >= 10)
        {
            normalAttack -= 1;
        }

        return new DefaultRpgEncounter("normal", $"史莱姆群 {stepIndex}", 11 + stepIndex, normalAttack, 2 + (stepIndex / 4));
    }

    private static IReadOnlyList<HeIsComingRewardOption> BuildRewardOptions(int stepIndex)
    {
        return
        [
            new HeIsComingRewardOption("equipment", $"旅者护符 +{stepIndex}", "生命+2 攻击+1", 2, 1, 0, 0),
            new HeIsComingRewardOption("attribute", $"活力火花 {stepIndex}", "生命+4 暴击+3%", 4, 0, 0, 0.03),
            new HeIsComingRewardOption("skill", $"被动：猎手直觉 {stepIndex}", "生命+2 攻击+1 暴击+5%", 2, 1, 0, 0.05)
        ];
    }

    private static int ClampRewardIndex(int rewardIndex, int count)
    {
        if (count <= 0)
        {
            return 0;
        }

        if (rewardIndex < 0)
        {
            return 0;
        }

        if (rewardIndex >= count)
        {
            return count - 1;
        }

        return rewardIndex;
    }

    private static readonly string[] RewardCategories = ["equipment", "attribute", "skill"];
}

public sealed record DefaultRpgPrototypeState(
    int StepIndex,
    int PlayerHp,
    int PlayerAttack,
    int PlayerDefense,
    double CritRate,
    IReadOnlyList<string> PassiveSkills,
    IReadOnlyList<string> EquippedItems,
    string Phase,
    bool IsGameOver,
    bool IsVictory);

public sealed record DefaultRpgEncounter(
    string Kind,
    string Name,
    int Hp,
    int Attack,
    int Defense);

public sealed record HeIsComingRewardOption(
    string Category,
    string Title,
    string Description,
    int HpDelta,
    int AttackDelta,
    int DefenseDelta,
    double CritDelta);

public sealed record DefaultRpgEncounterResult(
    DefaultRpgEncounter Encounter,
    DefaultRpgPrototypeState NextState,
    IReadOnlyList<HeIsComingRewardOption> RewardOptions,
    IReadOnlyList<string> BattleLog);

public sealed record DefaultRpgPrototypeResult(
    bool EncounterTriggered,
    bool BattleResolved,
    int PlayerHpAfterBattle,
    string RewardCategory,
    double CritRate);
