using System.Text;
using System.Text.RegularExpressions;

namespace PhaseA.Platform.Runs;

internal static class PrototypeSceneReferenceInspector
{
    public static bool EntrySceneInstancesScene(string projectRepoPath, string entryScene, string targetScene)
    {
        if (!TryResolveSceneFile(projectRepoPath, entryScene, out _, out var entryPath))
        {
            return false;
        }

        var target = PrototypeGodotSmokeService.ResolveSceneReference(projectRepoPath, targetScene);
        return target is not null &&
               ReadInstancedPackedScenes(projectRepoPath, entryPath)
                   .Any(scene => string.Equals(scene, target, StringComparison.OrdinalIgnoreCase));
    }

    public static bool TryFindFirstInstancedPrototypeScene(
        string projectRepoPath,
        string entryScene,
        string slug,
        out string instancedScene)
    {
        instancedScene = "";
        if (!TryResolveSceneFile(projectRepoPath, entryScene, out _, out var entryPath))
        {
            return false;
        }

        foreach (var scene in ReadInstancedPackedScenes(projectRepoPath, entryPath))
        {
            if (!IsPrototypeSceneForSlug(projectRepoPath, scene, slug))
            {
                continue;
            }

            instancedScene = scene;
            return true;
        }

        return false;
    }

    private static IReadOnlyList<string> ReadInstancedPackedScenes(string projectRepoPath, string scenePath)
    {
        var packedScenes = new Dictionary<string, string>(StringComparer.Ordinal);
        var instancedScenes = new List<string>();
        try
        {
            foreach (var line in File.ReadLines(scenePath, Encoding.UTF8))
            {
                if (line.StartsWith("[ext_resource", StringComparison.Ordinal) &&
                    TryReadSceneAttribute(line, "type", out var resourceType) &&
                    string.Equals(resourceType, "PackedScene", StringComparison.Ordinal) &&
                    TryReadSceneAttribute(line, "path", out var resourcePath) &&
                    TryReadSceneAttribute(line, "id", out var resourceId))
                {
                    var resolvedScene = PrototypeGodotSmokeService.ResolveSceneReference(projectRepoPath, resourcePath);
                    if (!string.IsNullOrWhiteSpace(resolvedScene))
                    {
                        packedScenes[resourceId] = resolvedScene;
                    }

                    continue;
                }

                if (TryReadSceneInstanceResourceId(line, out var instanceResourceId) &&
                    packedScenes.TryGetValue(instanceResourceId, out var instancedScene))
                {
                    instancedScenes.Add(instancedScene);
                }
            }
        }
        catch (IOException)
        {
            return [];
        }
        catch (UnauthorizedAccessException)
        {
            return [];
        }

        return instancedScenes;
    }

    private static bool IsPrototypeSceneForSlug(string projectRepoPath, string scene, string slug)
    {
        if (!TryResolveSceneFile(projectRepoPath, scene, out var normalizedScene, out _))
        {
            return false;
        }

        var normalizedSlug = PrototypeRecordWriter.SanitizeSlug(slug);
        var expectedPrefix = $"res://Game.Godot/Prototypes/{normalizedSlug}/";
        return normalizedScene.StartsWith(expectedPrefix, StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryResolveSceneFile(
        string projectRepoPath,
        string scene,
        out string normalizedScene,
        out string fullPath)
    {
        normalizedScene = PrototypeGodotSmokeService.ResolveSceneReference(projectRepoPath, scene) ?? "";
        fullPath = "";
        if (string.IsNullOrWhiteSpace(normalizedScene))
        {
            return false;
        }

        var relativePath = normalizedScene["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
        fullPath = Path.Combine(projectRepoPath, relativePath);
        return File.Exists(fullPath);
    }

    private static bool TryReadSceneAttribute(string line, string attributeName, out string value)
    {
        value = "";
        var match = Regex.Match(
            line,
            $@"\b{Regex.Escape(attributeName)}=""(?<value>[^""]+)""",
            RegexOptions.CultureInvariant);
        if (!match.Success)
        {
            return false;
        }

        value = match.Groups["value"].Value;
        return true;
    }

    private static bool TryReadSceneInstanceResourceId(string line, out string resourceId)
    {
        resourceId = "";
        var match = Regex.Match(
            line,
            "instance=ExtResource\\(\"(?<id>[^\"]+)\"\\)",
            RegexOptions.CultureInvariant);
        if (!match.Success)
        {
            return false;
        }

        resourceId = match.Groups["id"].Value;
        return true;
    }
}
