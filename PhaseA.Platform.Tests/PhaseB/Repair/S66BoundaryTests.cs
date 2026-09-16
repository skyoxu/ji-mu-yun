using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S66BoundaryTests
{
    [Fact]
    public async Task O_242D0431B63A()
    {
        await using var fixture = await IdentityFixture.CreateAsync();
        var resolved = await fixture.ResolveContextAsync("s66-tenant-principal");

        Require(
            resolved is not null &&
            resolved.Context.AccountId == resolved.ServerAccount.AccountId &&
            resolved.Context.PrincipalId == resolved.PrincipalId &&
            !string.Equals(resolved.Context.AccountId, resolved.Context.PrincipalId, StringComparison.Ordinal),
            "FAILURE-O-242D0431B63A",
            "The resolved context did not preserve distinct server-account and principal identifiers.");
    }

    [Fact]
    public async Task O_4EA9FCB86873()
    {
        await using var fixture = await IdentityFixture.CreateAsync();
        var resolved = await fixture.ResolveContextAsync("s66-server-relations");

        Require(
            resolved is not null &&
            resolved.ServerAccount.AccountId == resolved.IssuedAccountId &&
            resolved.Context.AccountId == resolved.ServerAccount.AccountId &&
            resolved.Context.PrincipalId == resolved.PrincipalId &&
            resolved.Context.Roles.SetEquals([PhaseAAuth.UserRole]) &&
            !string.Equals(resolved.Context.AccountId, resolved.Context.PrincipalId, StringComparison.Ordinal),
            "FAILURE-O-4EA9FCB86873",
            "The valid credential did not resolve a distinct principal and server-owned account membership context.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class IdentityFixture : IAsyncDisposable
    {
        private readonly string _databasePath;
        private readonly PhaseAMetadataStore _store;

        private IdentityFixture(string databasePath, PhaseAMetadataStore store)
        {
            _databasePath = databasePath;
            _store = store;
        }

        public static async Task<IdentityFixture> CreateAsync()
        {
            var databasePath = Path.Combine(Path.GetTempPath(), $"s66-{Guid.NewGuid():N}.sqlite3");
            var connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            return new IdentityFixture(databasePath, new PhaseAMetadataStore(connectionString, options));
        }

        public async Task<ResolvedContext?> ResolveContextAsync(string username)
        {
            var issued = await _store.CreateUserAccountAsync(username, 1);
            var serverAccount = await _store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(issued.Token));
            if (serverAccount is null)
            {
                return null;
            }

            var principalId = $"principal-{Guid.NewGuid():N}";
            var identity = new AccountIdentity(serverAccount.AccountId, serverAccount.Username, PhaseAAuth.UserRole);
            var context = RequestContext.FromIdentity(identity, principalId, issued.AccountId, "s66-correlation");
            return new ResolvedContext(issued.AccountId, serverAccount, principalId, context);
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
        string IssuedAccountId,
        AccountSnapshot ServerAccount,
        string PrincipalId,
        RequestContext Context);
}
