using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static partial class PrototypeRepairMutationGuard
{
    private static readonly string[] PrototypeTestRoots =
    [
        Path.Combine("Game.Core.Tests", "Prototypes"),
        Path.Combine("Tests.Godot", "tests", "Prototype")
    ];

    public static PrototypeRepairMutationGuardResult Validate(ProjectSnapshot project, ProjectIterationGoalSnapshot? goal)
    {
        if (goal is null)
        {
            return PrototypeRepairMutationGuardResult.NotRequired("not_goal_repair");
        }

        if (!PrototypeRouteSkillPolicy.IsRpgProject(project) &&
            !PrototypeRouteSkillPolicy.IsSurvivorsLikeProject(project))
        {
            return PrototypeRepairMutationGuardResult.NotRequired("not_specialized_prototype_project");
        }

        var violations = new List<PrototypeRepairMutationGuardViolation>();
        foreach (var relativeRoot in PrototypeTestRoots)
        {
            var absoluteRoot = Path.Combine(project.RepoPath, relativeRoot);
            if (!Directory.Exists(absoluteRoot))
            {
                continue;
            }

            foreach (var file in Directory.EnumerateFiles(absoluteRoot, "*.cs", SearchOption.AllDirectories))
            {
                var text = File.ReadAllText(file);
                AddForbiddenXunitShimViolations(project.RepoPath, file, text, violations);
            }
        }

        return violations.Count == 0
            ? PrototypeRepairMutationGuardResult.Success()
            : PrototypeRepairMutationGuardResult.Failed("test_framework_shadowing_detected", violations);
    }

    private static void AddForbiddenXunitShimViolations(
        string repoPath,
        string file,
        string text,
        List<PrototypeRepairMutationGuardViolation> violations)
    {
        AddViolationIfMatch(repoPath, file, text, XunitNamespaceRegex(), "namespace_xunit", violations);
        AddViolationIfMatch(repoPath, file, text, XunitFactAttributeRegex(), "xunit_fact_attribute_shadow", violations);
        AddViolationIfMatch(repoPath, file, text, XunitTheoryAttributeRegex(), "xunit_theory_attribute_shadow", violations);
        AddViolationIfMatch(repoPath, file, text, XunitInlineDataAttributeRegex(), "xunit_inline_data_attribute_shadow", violations);
        AddViolationIfMatch(repoPath, file, text, XunitAssertClassRegex(), "xunit_assert_shadow", violations);
    }

    private static void AddViolationIfMatch(
        string repoPath,
        string file,
        string text,
        Regex regex,
        string rule,
        List<PrototypeRepairMutationGuardViolation> violations)
    {
        var match = regex.Match(text);
        if (!match.Success)
        {
            return;
        }

        var line = text.AsSpan(0, match.Index).Count('\n') + 1;
        violations.Add(new PrototypeRepairMutationGuardViolation(
            NormalizeRelativePath(Path.GetRelativePath(repoPath, file)),
            line,
            rule));
    }

    private static string NormalizeRelativePath(string value)
    {
        return value.Replace('\\', '/');
    }

    [GeneratedRegex(@"(^|\s)namespace\s+Xunit(\s|$|[.;{])")]
    private static partial Regex XunitNamespaceRegex();

    [GeneratedRegex(@"\b(class|record|struct)\s+FactAttribute\b")]
    private static partial Regex XunitFactAttributeRegex();

    [GeneratedRegex(@"\b(class|record|struct)\s+TheoryAttribute\b")]
    private static partial Regex XunitTheoryAttributeRegex();

    [GeneratedRegex(@"\b(class|record|struct)\s+InlineDataAttribute\b")]
    private static partial Regex XunitInlineDataAttributeRegex();

    [GeneratedRegex(@"\b(class|record|struct)\s+Assert\b")]
    private static partial Regex XunitAssertClassRegex();
}

internal sealed record PrototypeRepairMutationGuardResult(
    string Status,
    string? Reason,
    IReadOnlyList<PrototypeRepairMutationGuardViolation> Violations)
{
    [JsonIgnore]
    public bool Passed => string.Equals(Status, "passed", StringComparison.Ordinal);

    public static PrototypeRepairMutationGuardResult Success()
    {
        return new PrototypeRepairMutationGuardResult("passed", null, []);
    }

    public static PrototypeRepairMutationGuardResult Failed(string reason, IReadOnlyList<PrototypeRepairMutationGuardViolation> violations)
    {
        return new PrototypeRepairMutationGuardResult("failed", reason, violations);
    }

    public static PrototypeRepairMutationGuardResult NotRequired(string reason)
    {
        return new PrototypeRepairMutationGuardResult("not_required", reason, []);
    }

    public object ToEvidence()
    {
        return new
        {
            status = Status,
            reason = Reason,
            violations = Violations
        };
    }
}

internal sealed record PrototypeRepairMutationGuardViolation(string Path, int Line, string Rule);
