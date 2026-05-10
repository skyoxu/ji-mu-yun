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
        ArgumentNullException.ThrowIfNull(request);
        var slug = SanitizeSlug(request.Slug!);
        var relativePath = $"docs/prototypes/{DateTime.UtcNow:yyyy-MM-dd}-{slug}.md";
        var absolutePath = Path.Combine(_options.RepositoryRoot, relativePath.Replace('/', Path.DirectorySeparatorChar));
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
        var lines = new List<string>
        {
            $"# Prototype: {slug}",
            "",
            "- Status: active",
            "- Owner: phase-a-platform",
            $"- Date: {DateTime.UtcNow:yyyy-MM-dd}",
            "- Related formal task ids: none yet",
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
}
