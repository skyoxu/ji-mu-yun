using PhaseA.Platform.Configuration;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeCommandBuilder
{
    private readonly PhaseAPlatformOptions _options;

    public PrototypeCommandBuilder(PhaseAPlatformOptions options)
    {
        _options = options;
    }

    public HostedProcessCommand BuildTdd(PrototypeTddRequest request, string repositoryRoot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "run-prototype-tdd",
            "--slug",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!),
            "--stage",
            request.Stage!.ToLowerInvariant()
        };

        if (!string.IsNullOrWhiteSpace(request.Expect))
        {
            arguments.Add("--expect");
            arguments.Add(request.Expect);
        }

        if (!string.IsNullOrWhiteSpace(request.RecordPath))
        {
            arguments.Add("--record-path");
            arguments.Add(request.RecordPath);
        }

        if (!string.IsNullOrWhiteSpace(request.Filter))
        {
            arguments.Add("--filter");
            arguments.Add(request.Filter);
        }

        foreach (var target in request.DotnetTarget ?? [])
        {
            if (!string.IsNullOrWhiteSpace(target))
            {
                arguments.Add("--dotnet-target");
                arguments.Add(target);
            }
        }

        foreach (var path in request.GdunitPath ?? [])
        {
            if (!string.IsNullOrWhiteSpace(path))
            {
                arguments.Add("--gdunit-path");
                arguments.Add(path);
            }
        }

        if (request.TimeoutSec is not null)
        {
            arguments.Add("--timeout-sec");
            arguments.Add(request.TimeoutSec.Value.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            arguments.Add("--godot-bin");
            arguments.Add(_options.GodotBin);
        }

        return Build(arguments, repositoryRoot);
    }

    public HostedProcessCommand BuildScene(PrototypeSceneRequest request, string repositoryRoot)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        var arguments = new List<string>
        {
            "-3",
            "scripts/python/dev_cli.py",
            "create-prototype-scene",
            "--slug",
            PrototypeRecordWriter.SanitizeSlug(request.Slug!)
        };

        if (!string.IsNullOrWhiteSpace(request.SceneRoot))
        {
            arguments.Add("--scene-root");
            arguments.Add(request.SceneRoot);
        }

        if (!string.IsNullOrWhiteSpace(request.PrototypeRoot))
        {
            arguments.Add("--prototype-root");
            arguments.Add(request.PrototypeRoot);
        }

        var recommendation = PrototypeEngineRecommendation.From(request);

        if (recommendation is not null && !string.IsNullOrWhiteSpace(recommendation.EngineBackend))
        {
            arguments.Add("--engine-backend");
            arguments.Add(recommendation.EngineBackend);
        }

        if (recommendation is not null && !string.IsNullOrWhiteSpace(recommendation.EngineApplyMode))
        {
            arguments.Add("--engine-apply-mode");
            arguments.Add(recommendation.EngineApplyMode);
        }

        if (recommendation is not null && !string.IsNullOrWhiteSpace(recommendation.EngineConfidence))
        {
            arguments.Add("--engine-confidence");
            arguments.Add(recommendation.EngineConfidence);
        }

        if (recommendation is not null && !string.IsNullOrWhiteSpace(recommendation.EngineReason))
        {
            arguments.Add("--engine-reason");
            arguments.Add(recommendation.EngineReason);
        }

        if (recommendation is not null)
        {
            arguments.Add("--engine-requires-plugin");
            arguments.Add(recommendation.EngineRequiresPlugin ? "true" : "false");
        }

        if (recommendation is not null && !string.IsNullOrWhiteSpace(recommendation.EngineInstallTarget))
        {
            arguments.Add("--engine-install-target");
            arguments.Add(recommendation.EngineInstallTarget);
        }

        return Build(arguments, repositoryRoot);
    }

    private HostedProcessCommand Build(IReadOnlyList<string> arguments, string repositoryRoot)
    {
        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            environment["GODOT_BIN"] = _options.GodotBin;
        }

        return new HostedProcessCommand(_options.PythonCommand, arguments, repositoryRoot, environment);
    }

    private sealed record PrototypeEngineRecommendation(
        string EngineBackend,
        string EngineApplyMode,
        string EngineConfidence,
        string EngineReason,
        bool EngineRequiresPlugin,
        string EngineInstallTarget)
    {
        public static PrototypeEngineRecommendation? From(PrototypeSceneRequest request)
        {
            if (!string.IsNullOrWhiteSpace(request.EngineBackend))
            {
                var backend = request.EngineBackend.Trim();
                var requiresPlugin = request.EngineRequiresPlugin ?? IsRapier(backend);
                var applyMode = string.IsNullOrWhiteSpace(request.EngineApplyMode)
                    ? (requiresPlugin ? "confirm_apply" : "recommend_only")
                    : request.EngineApplyMode.Trim();
                if (IsRapier(backend) && string.Equals(applyMode, "auto_apply_prototype_only", StringComparison.OrdinalIgnoreCase))
                {
                    applyMode = "confirm_apply";
                }

                return new PrototypeEngineRecommendation(
                    backend,
                    applyMode,
                    string.IsNullOrWhiteSpace(request.EngineConfidence) ? "low" : request.EngineConfidence.Trim(),
                    string.IsNullOrWhiteSpace(request.EngineReason) ? DefaultReason(backend) : request.EngineReason.Trim(),
                    requiresPlugin,
                    string.IsNullOrWhiteSpace(request.EngineInstallTarget) ? "project_local_addon" : request.EngineInstallTarget.Trim());
            }

            return Infer(request);
        }

        private static PrototypeEngineRecommendation? Infer(PrototypeSceneRequest request)
        {
            var gameplayIntakeValues = new[]
            {
                request.Hypothesis,
                request.CorePlayerFantasy,
                request.MinimumPlayableLoop,
                request.GameFeature,
                request.CoreGameplayLoop,
                request.WinFailConditions
            }.Where(value => !string.IsNullOrWhiteSpace(value)).ToArray();
            if (gameplayIntakeValues.Length == 0)
            {
                return null;
            }

            var intakeValues = new[]
            {
                request.GameType,
            }.Where(value => !string.IsNullOrWhiteSpace(value)).Concat(gameplayIntakeValues);
            var haystack = string.Join("\n", intakeValues).ToLowerInvariant();
            var gameType = PrototypeRecordWriter.SanitizeSlug(request.GameType ?? string.Empty).ToLowerInvariant();

            var strongPhysicsTerms = new[]
            {
                "deterministic", "determinism", "replay", "rollback", "sync", "同步", "回放", "确定性", "复杂碰撞", "physics feel", "物理手感"
            };
            var physicsTerms = new[]
            {
                "physics", "rigidbody", "collision", "撞", "碰撞", "弹跳", "gravity", "重力", "platform", "平台跳跃", "movement", "移动"
            };
            var threeDTerms = new[] { "3d", "third person", "first person", "fps", "tps", "三维", "第三人称", "第一人称" };
            var twoDTerms = new[] { "2d", "top-down", "side", "platformer", "横版", "俯视角", "平面" };
            var stateFlowTerms = new[] { "turn-based", "回合", "card", "deck", "ui", "菜单", "剧情", "visual novel", "rpg", "jrpg" };
            var directPhysicsTerms = physicsTerms
                .Where(term => !string.Equals(term, "movement", StringComparison.OrdinalIgnoreCase) && term != "移动")
                .ToArray();

            var hasStrongPhysics = ContainsAny(haystack, strongPhysicsTerms);
            var hasDirectPhysics = ContainsAny(haystack, directPhysicsTerms);
            var is3d = ContainsAny(haystack, threeDTerms);
            var is2d = ContainsAny(haystack, twoDTerms) || !is3d;
            var isStateFlow = gameType is "rpg" or "jrpg" || ContainsAny(haystack, stateFlowTerms);

            if (hasStrongPhysics && is3d)
            {
                return Rapier("rapier_3d", "Prototype asks for deterministic or complex 3D physics feel.");
            }

            if (hasStrongPhysics && is2d)
            {
                return Rapier("rapier_2d", "Prototype asks for deterministic or complex 2D physics feel.");
            }

            if (isStateFlow && !hasDirectPhysics)
            {
                return BuiltIn("none", "medium", "Prototype appears driven by UI, turn flow, or story state transitions.");
            }

            if (hasDirectPhysics && is3d)
            {
                return BuiltIn("jolt_3d", "medium", "Prototype has 3D collision or gravity needs that fit built-in 3D physics first.");
            }

            if (hasDirectPhysics)
            {
                return BuiltIn("godot_physics_2d", "medium", "Prototype has ordinary 2D collision or gravity needs; use built-in 2D physics first.");
            }

            return BuiltIn("none", "low", "No clear physics-handling requirement was found in the current prototype intake.");
        }

        private static PrototypeEngineRecommendation Rapier(string backend, string reason)
        {
            return new PrototypeEngineRecommendation(backend, "confirm_apply", "medium", reason, true, "project_local_addon");
        }

        private static PrototypeEngineRecommendation BuiltIn(string backend, string confidence, string reason)
        {
            return new PrototypeEngineRecommendation(backend, "recommend_only", confidence, reason, false, "project_local_addon");
        }

        private static bool ContainsAny(string haystack, IEnumerable<string> terms)
        {
            return terms.Any(term => haystack.Contains(term, StringComparison.OrdinalIgnoreCase));
        }

        private static bool IsRapier(string backend)
        {
            return string.Equals(backend, "rapier_2d", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(backend, "rapier_3d", StringComparison.OrdinalIgnoreCase);
        }

        private static string DefaultReason(string backend)
        {
            return IsRapier(backend)
                ? "Prototype asks for Rapier as a project-local addon recommendation until explicitly applied."
                : "No engine-specific physics backend was recommended for this prototype scaffold.";
        }
    }
}
