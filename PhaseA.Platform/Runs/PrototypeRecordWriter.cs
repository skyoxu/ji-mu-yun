using System.Text.RegularExpressions;
using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeRecordWriter
{
    private readonly PhaseAPlatformOptions _options;

    public PrototypeRecordWriter(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public string Write(PrototypeWorkflowRequest request)
    {
        return Write(request, _options.RepositoryRoot);
    }

    public string Write(PrototypeWorkflowRequest request, string repositoryRoot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        var slug = SanitizeSlug(request.Slug!);
        var relativePath = $"docs/prototypes/{DateTime.UtcNow:yyyy-MM-dd}-{slug}.md";
        var absolutePath = Path.Combine(repositoryRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(absolutePath)!);
        File.WriteAllText(absolutePath, BuildMarkdown(request, slug), System.Text.Encoding.UTF8);
        return relativePath;
    }

    public static string SanitizeSlug(string value)
    {
        var cleaned = Regex.Replace(value.Trim(), "[^A-Za-z0-9_-]+", "-");
        cleaned = Regex.Replace(cleaned, "-{2,}", "-").Trim('-', '_');
        return string.IsNullOrWhiteSpace(cleaned) ? "prototype" : cleaned;
    }

    private static string BuildMarkdown(PrototypeWorkflowRequest request, string slug)
    {
        var successCriteria = request.SuccessCriteria!.Where(item => !string.IsNullOrWhiteSpace(item)).ToArray();
        var gameName = request.GameName?.Trim() ?? "";
        var gameType = request.GameType?.Trim() ?? "";
        var gameTypeSource = request.GameTypeSource?.Trim() ?? "";
        var lines = new List<string>
        {
            $"# Prototype: {slug}",
            "",
            "- Status: active",
            "- Owner: phase-a-platform",
            $"- Date: {DateTime.UtcNow:yyyy-MM-dd}",
            "- Related formal task ids: none yet",
            $"- Game Name: {(string.IsNullOrWhiteSpace(gameName) ? "TBD" : gameName)}",
            $"- Game Type: {(string.IsNullOrWhiteSpace(gameType) ? "TBD" : gameType)}",
            $"- Game Type Source: {(string.IsNullOrWhiteSpace(gameTypeSource) ? "TBD" : gameTypeSource)}",
            "",
            "## Prototype Input Contract",
            "- Rule: Every non-empty field in this section is user/project intent and must be reflected in gameplay, UI, scene flow, validation, or an explicit needs-fix blocker.",
            "- Rule: Type templates and RPG defaults may fill gaps, but must not override concrete user values.",
            $"- {PrototypePlayerVisibleTextPolicy.PrototypeRecordRule}",
            "",
            "| Field | Value | Must Reflect In |",
            "| --- | --- | --- |",
            $"| slug | {Md(slug)} | Prototype folder, scene name, route state, artifacts |",
            $"| game_name | {Md(string.IsNullOrWhiteSpace(gameName) ? "TBD" : gameName)} | Title, menu copy, visible UI labels when useful |",
            $"| game_type | {Md(string.IsNullOrWhiteSpace(gameType) ? "TBD" : gameType)} | Route skill, type kit, default scene/asset rules |",
            $"| game_type_source | {Md(string.IsNullOrWhiteSpace(gameTypeSource) ? "TBD" : gameTypeSource)} | Type-specific skill selection and ambiguity handling |",
            $"| hypothesis | {Md(request.Hypothesis!.Trim())} | Scenario framing, final report, acceptance focus |",
            $"| core_player_fantasy | {Md(request.CorePlayerFantasy!.Trim())} | Primary verbs, UI feedback, scene presentation |",
            $"| minimum_playable_loop | {Md(request.MinimumPlayableLoop!.Trim())} | Scene flow, state transitions, smoke/acceptance target |",
            $"| success_criteria | {Md(string.Join("; ", successCriteria.Select(item => item.Trim())))} | Iteration goals, final validation checklist, needs-fix blockers |",
            $"| game_feature | {Md(request.GameFeature!.Trim())} | Gameplay mechanics, scene objects, scripts, tests |",
            $"| core_gameplay_loop | {Md(request.CoreGameplayLoop!.Trim())} | Map/battle/reward/control flow and loop continuity |",
            $"| win_fail_conditions | {Md(request.WinFailConditions!.Trim())} | Settlement UI, game-over/retry, battle/map outcome logic |",
            "",
            "## Hypothesis",
            $"- {request.Hypothesis!.Trim()}",
            "",
            "## Core Player Fantasy",
            $"- {request.CorePlayerFantasy!.Trim()}",
            "",
            "## Minimum Playable Loop",
            $"- {request.MinimumPlayableLoop!.Trim()}",
            "",
            "## Game Feature",
            $"- {request.GameFeature!.Trim()}",
            "",
            "## Core Gameplay Loop",
            $"- {request.CoreGameplayLoop!.Trim()}",
            "",
            "## Win / Fail Conditions",
            $"- {request.WinFailConditions!.Trim()}",
            "",
            "## Scope",
            "- In:",
            "  - Prototype lane only",
            "- Out:",
            "  - Chapter 3 formal delivery",
            "  - Chapter 4 formal delivery",
            "  - Chapter 5 formal delivery",
            "  - Chapter 6 formal delivery",
            "  - Chapter 7 formal delivery",
            "",
            "## Success Criteria"
        };

        lines.AddRange(successCriteria.Select(item => $"- {item.Trim()}"));
        lines.AddRange([
            "",
            "## Promote Signals",
            "- Prototype evidence shows the loop is worth formal delivery later.",
            "",
            "## Archive Signals",
            "- Prototype has useful learning but is not ready for formal delivery.",
            "",
            "## Discard Signals",
            "- Prototype loop is not viable.",
            "",
            "## Evidence",
            "- Code paths:",
            "  - docs/prototypes",
            "- Logs / media / notes:",
            "  - logs/ci/active-prototypes",
            "",
            "## Decision",
            "- archive",
            "",
            "## Next Step",
            "- Stay in prototype lane until explicitly promoted later."
        ]);

        return string.Join("\n", lines) + "\n";
    }

    private static string Md(string value)
    {
        return value.Replace("|", "\\|", StringComparison.Ordinal).Replace("\r", " ", StringComparison.Ordinal).Replace("\n", "<br>", StringComparison.Ordinal);
    }
}
