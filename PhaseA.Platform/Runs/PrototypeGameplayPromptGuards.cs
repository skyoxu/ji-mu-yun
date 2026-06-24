namespace PhaseA.Platform.Runs;

internal static class PrototypeGameplayPromptGuards
{
    public static string BuildCombatPressureGuardPromptBlock()
    {
        return """
            Combat pressure interpretation guard:
            - Treat "enemy pressure", "combat pressure", "wave pressure", or similar wording as visible, player-readable threat pacing: enemy positioning, approach, attack windup, projectile, area warning, spawn cadence, collision, or another explicit GDD/spec mechanic.
            - Do not implement hidden damage-over-time, unavoidable timer damage, standing-still damage, guaranteed counter damage after player attacks, or "pressure" HP loss unless the GDD/spec explicitly requires that exact mechanic.
            - If an existing module already contains hidden pressure damage or guaranteed attack retaliation without GDD/spec support, remove it or convert it into visible enemy contact, attack, projectile, telegraphed area, or spawn-pressure behavior.
            - Any damage source must be understandable from gameplay feedback and should be avoidable or controllable through the designed movement, dodge, positioning, defense, or timing model.
            """;
    }
}
