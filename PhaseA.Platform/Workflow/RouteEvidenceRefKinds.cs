namespace PhaseA.Platform.Workflow;

public static class RouteEvidenceRefKinds
{
    public static readonly IReadOnlySet<string> Values = new HashSet<string>(
        ["log", "artifact", "sidecar", "screenshot", "db_row", "smoke", "validator"],
        StringComparer.Ordinal);

    public static bool Contains(string kind)
    {
        return Values.Contains(kind);
    }
}
