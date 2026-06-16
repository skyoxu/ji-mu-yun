namespace PhaseA.Platform.Runs;

internal static class PrototypePlayerVisibleTextPolicy
{
    public const string PromptRule =
        "Player-visible text rule: keep code identifiers, class names, method names, node names, resource paths, test names, logs, and platform-required fixed node names in English; but any text players can see inside the Godot game screen, including Label, Button, RichTextLabel, HUD, menus, battle logs, quest prompts, result prompts, and win/fail/error prompts, must default to Chinese. Use non-Chinese player-visible text only when the user explicitly requests another language or the game setting requires it. Do not rename platform-validated fixed nodes for localization.";

    public const string PrototypeRecordRule =
        "Rule: Player-visible text inside the generated Godot game screen must default to Chinese, including Label, Button, RichTextLabel, HUD, menus, battle logs, quest prompts, result prompts, and win/fail/error prompts. Keep code identifiers, class names, method names, node names, resource paths, tests, logs, and platform-required fixed node names in English. Use non-Chinese player-visible text only when the user explicitly requests another language or the game setting requires it.";
}
