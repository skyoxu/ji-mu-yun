using System.Text.Json;

namespace PhaseA.Platform.Projects;

public static class ProjectCreationRequestJsonPolicy
{
    private static readonly HashSet<string> ForbiddenGitUrlProperties = new(StringComparer.OrdinalIgnoreCase)
    {
        "git_url",
        "gitUrl",
        "repository_url",
        "repositoryUrl",
        "repo_url",
        "repoUrl",
        "remote_url",
        "remoteUrl"
    };

    public static bool ContainsForbiddenGitUrl(JsonElement json)
    {
        if (json.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        foreach (var property in json.EnumerateObject())
        {
            if (ForbiddenGitUrlProperties.Contains(property.Name) && property.Value.ValueKind is not JsonValueKind.Null)
            {
                return true;
            }
        }

        return false;
    }
}
