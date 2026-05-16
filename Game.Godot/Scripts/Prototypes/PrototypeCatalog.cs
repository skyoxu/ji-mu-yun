using Godot;
using System.Collections.Generic;

namespace Game.Godot.Scripts.Prototypes;

public static class PrototypeCatalog
{
    public const string DqRpgPrototypeSlug = "dq-rpg";
    public const string DqRpgPrototypeScenePath = "res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn";
    public const string DefaultRpgPrototypeSlug = "default-rpg-template";
    public const string DefaultRpgPrototypeScenePath = "res://Game.Godot/Prototypes/DefaultRpgTemplate/DefaultRpgPrototype.tscn";

    public static readonly IReadOnlyDictionary<string, string> SceneBySlug = new Dictionary<string, string>
    {
        [DqRpgPrototypeSlug] = DqRpgPrototypeScenePath,
        [DefaultRpgPrototypeSlug] = DefaultRpgPrototypeScenePath,
    };

    public static string DefaultMenuPrototypeSlug => ResolveDefaultMenuPrototypeSlug();

    public static string DefaultMenuPrototypeScenePath => ResolveScenePath(DefaultMenuPrototypeSlug);

    public static string ResolveScenePath(string slug)
    {
        return SceneBySlug.TryGetValue(slug, out var scenePath)
            ? scenePath
            : string.Empty;
    }

    private static string ResolveDefaultMenuPrototypeSlug()
    {
        foreach (var candidate in new[] { DqRpgPrototypeSlug, DefaultRpgPrototypeSlug })
        {
            var scenePath = ResolveScenePath(candidate);
            if (!string.IsNullOrWhiteSpace(scenePath) && ResourceLoader.Exists(scenePath))
            {
                return candidate;
            }
        }

        return DefaultRpgPrototypeSlug;
    }
}
