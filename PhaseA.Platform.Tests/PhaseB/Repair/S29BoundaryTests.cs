using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S29BoundaryTests
{
    [Fact]
    public async Task O_B7041EE09EE2()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var resolved = await fixture.ResolveContextAsync("s29-server-roles", "client-admin");

        Require(
            resolved is not null &&
            resolved.Context.Roles.SetEquals([PhaseAAuth.UserRole]) &&
            !resolved.Context.Roles.Contains("client-admin"),
            "FAILURE-O-B7041EE09EE2",
            "The resolved context did not project roles from the server relationship independently of client input.");
    }

    [Fact]
    public async Task O_8252A64854FC()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var resolved = await fixture.ResolveContextAsync("s29-credential-id", "client-admin");

        Require(
            resolved is not null &&
            string.Equals(resolved.Context.CredentialId, resolved.IssuedCredentialId, StringComparison.Ordinal) &&
            !string.Equals(resolved.Context.CredentialId, resolved.PrincipalId, StringComparison.Ordinal),
            "FAILURE-O-8252A64854FC",
            "The resolved context did not identify the credential used for server resolution.");
    }

    [Fact]
    public async Task O_68EB3FECA634()
    {
        await using var fixture = await BoundaryFixture.CreateAsync();
        var ownership = await fixture.ResolveOwnershipAcrossPlacementVariantsAsync();

        Require(
            ownership.Count == 3 &&
            ownership.All(observation =>
                string.Equals(observation.ResolvedAccountId, ownership.ServerAccountId, StringComparison.Ordinal) &&
                string.Equals(observation.ResolvedProjectId, ownership.ServerProjectId, StringComparison.Ordinal) &&
                string.Equals(observation.ResolvedWorkspaceId, ownership.ServerWorkspaceId, StringComparison.Ordinal)) &&
            ownership.Select(observation => observation.ResolvedAccountId).Distinct(StringComparer.Ordinal).Count() == 1 &&
            ownership.Select(observation => observation.ResolvedProjectId).Distinct(StringComparer.Ordinal).Count() == 1 &&
            ownership.Select(observation => observation.ResolvedWorkspaceId).Distinct(StringComparer.Ordinal).Count() == 1,
            "FAILURE-O-68EB3FECA634",
            "Ownership changed when placement references varied instead of being resolved from server account, project, and workspace relations.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class BoundaryFixture : IAsyncDisposable
    {
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;

        private BoundaryFixture(string databasePath, PhaseAMetadataStore store)
        {
            _databasePath = databasePath;
            _store = store;
        }

        public static async Task<BoundaryFixture> CreateAsync()
        {
            var databasePath = Path.Combine(Path.GetTempPath(), $"s29-{Guid.NewGuid():N}.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            return new BoundaryFixture(databasePath, new PhaseAMetadataStore(connectionString, options));
        }

        public async Task<ResolvedContext?> ResolveContextAsync(string username, string clientSuppliedRole)
        {
            var issued = await _store.CreateUserAccountAsync(username, 2);
            var serverAccount = await _store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(issued.Token));
            if (serverAccount is null)
            {
                return null;
            }

            var principalId = $"principal-{Guid.NewGuid():N}";
            var serverRole = serverAccount.IsAdmin ? PhaseAAuth.AdminRole : PhaseAAuth.UserRole;
            var identity = new AccountIdentity(serverAccount.AccountId, serverAccount.Username, serverRole);
            var context = RequestContext.FromIdentity(identity, principalId, issued.AccountId, "s29-correlation");
            return new ResolvedContext(issued.AccountId, principalId, clientSuppliedRole, context);
        }

        public async Task<OwnershipObservations> ResolveOwnershipAcrossPlacementVariantsAsync()
        {
            var issued = await _store.CreateUserAccountAsync("s29-owner", 2);
            var projectRoot = Path.Combine(Path.GetTempPath(), $"s29-project-{Guid.NewGuid():N}");
            var created = await _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                issued.AccountId,
                "S29 ownership",
                "S29 ownership",
                "manual",
                "default",
                false,
                [],
                projectRoot,
                Path.Combine(projectRoot, "repo"),
                Path.Combine(projectRoot, "runtime"),
                Path.Combine(projectRoot, "meta")));
            var serverProject = await _store.GetProjectSnapshotAsync(created.ProjectId!);
            if (serverProject is null)
            {
                throw new Xunit.Sdk.XunitException("S29 fixture could not resolve its server project relation.");
            }

            var changedProjectRoot = Path.Combine(Path.GetTempPath(), $"s29-placement-{Guid.NewGuid():N}");
            var changedProject = await _store.CreateProjectAsync(new ProjectCreationCommand(
                $"project-{Guid.NewGuid():N}",
                issued.AccountId,
                "S29 placement",
                "S29 placement",
                "manual",
                "default",
                false,
                [],
                changedProjectRoot,
                Path.Combine(changedProjectRoot, "repo"),
                Path.Combine(changedProjectRoot, "runtime"),
                Path.Combine(changedProjectRoot, "meta")));
            var changedPlacement = await _store.GetProjectSnapshotAsync(changedProject.ProjectId!);
            if (changedPlacement is null)
            {
                throw new Xunit.Sdk.XunitException("S29 fixture could not resolve its changed placement relation.");
            }

            var placementReferences = new string?[] { null, serverProject.WorkspaceId, changedPlacement.WorkspaceId };
            var observations = new List<OwnershipObservation>();
            foreach (var placementReference in placementReferences)
            {
                await _store.CreateRunAsync(serverProject.ProjectId, placementReference, "s29-placement");
                var resolved = await _store.GetProjectSnapshotAsync(serverProject.ProjectId);
                if (resolved is null)
                {
                    throw new Xunit.Sdk.XunitException("S29 fixture could not resolve the project after placement variation.");
                }

                observations.Add(new OwnershipObservation(
                    placementReference,
                    resolved.AccountId,
                    resolved.ProjectId,
                    resolved.WorkspaceId));
            }

            return new OwnershipObservations(issued.AccountId, serverProject.ProjectId, serverProject.WorkspaceId, observations);
        }

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(_databasePath))
            {
                File.Delete(_databasePath);
            }

            return ValueTask.CompletedTask;
        }
    }

    private sealed record ResolvedContext(
        string IssuedCredentialId,
        string PrincipalId,
        string ClientSuppliedRole,
        RequestContext Context);

    private sealed record OwnershipObservation(
        string? PlacementReference,
        string ResolvedAccountId,
        string ResolvedProjectId,
        string ResolvedWorkspaceId);

    private sealed record OwnershipObservations(
        string ServerAccountId,
        string ServerProjectId,
        string ServerWorkspaceId,
        IReadOnlyList<OwnershipObservation> Values) : IReadOnlyList<OwnershipObservation>
    {
        public int Count => Values.Count;
        public OwnershipObservation this[int index] => Values[index];
        public IEnumerator<OwnershipObservation> GetEnumerator() => Values.GetEnumerator();
        System.Collections.IEnumerator System.Collections.IEnumerable.GetEnumerator() => GetEnumerator();
    }
}
