using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: supplemental node identity for disposable seeder/OS-boundary fixtures.
// This is real, isolated metadata authentication; no production guard is replaced.
internal sealed class OwnedCiOperation
{
    internal PhaseAMetadataStore Store = null!;
    internal RequestContext Context = null!;
    internal static async Task<OwnedCiOperation> CreateAsync(PhaseAPlatformOptions options,
        string root, string repo, string account, string project)
    {
        var temp = Path.GetFullPath(Path.GetTempPath());
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        if (!Path.GetFullPath(root).StartsWith(Path.TrimEndingDirectorySeparator(temp) + Path.DirectorySeparatorChar, comparison))
            throw new InvalidOperationException("CI authority requires an owned temporary fixture root.");
        var metadata = S206TestSupport.CreateOwnedFixtureRoot("ci-operation-authority-");
        Directory.CreateDirectory(metadata);
        var connectionString = new SqliteConnectionStringBuilder
            { DataSource = Path.Combine(metadata, "metadata.sqlite3"), Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(connectionString, options);
        var token = Guid.NewGuid().ToString("N");
        using (var connection = new SqliteConnection(connectionString))
        {
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = """
                INSERT INTO accounts(id,username,token_hash,is_admin,created_utc,home_node_id,authority_revision)
                VALUES($account,$account,$token,0,$now,$node,1);
                INSERT INTO project_limits(account_id,project_limit,created_utc,updated_utc)
                VALUES($account,2,$now,$now);
                """;
            command.Parameters.AddWithValue("$account", account);
            command.Parameters.AddWithValue("$token", PhaseAAuth.HashTokenForStorage(token));
            command.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O"));
            command.Parameters.AddWithValue("$node", options.NodeId!);
            command.ExecuteNonQuery();
        }
        var result = new OwnedCiOperation { Store = new PhaseAMetadataStore(connectionString, options) };
        var created = await result.Store.CreateProjectAsync(new(project, account, "CI boundary", "CI boundary",
            "manual", "default", false, [], root, repo, Path.Combine(root, "runtime"), Path.Combine(root, "meta")));
        if (!created.Succeeded) throw new InvalidOperationException("CI project binding failed: " + created.FailureCode);
        result.Context = await S206TestSupport.FixtureContextAsync(result.Store, PhaseAAuth.HashTokenForStorage(token));
        return result;
    }

    internal static IProjectWorkspaceSeeder Seeder(PhaseAPlatformOptions options, string repo)
    {
        var root = Path.GetDirectoryName(repo)!;
        var owned = CreateAsync(options, root, repo, "ci-seeder-owner", "ci-seeder-project").GetAwaiter().GetResult();
        return new AuthenticatedSeeder(new ProjectWorkspaceSeeder(options, owned.Store), owned.Context);
    }

    private sealed class AuthenticatedSeeder(IProjectWorkspaceSeeder seeder, RequestContext context) : IProjectWorkspaceSeeder
    {
        public void EnsureSeeded(string repo)
        {
            using var current = RequestContext.UseCurrent(context);
            seeder.EnsureSeeded(repo);
        }
    }

    internal static IHostedProcessRunner Runner() => new AuthenticatedRunner();
    private sealed class AuthenticatedRunner : IHostedProcessRunner
    {
        public async Task<HostedProcessResult> RunAsync(HostedProcessCommand command, CancellationToken cancellationToken = default)
        {
            if (!RunnerIsolationPolicy.TryGetWorkspaceDescriptor(command.WorkingDirectory, out var descriptor))
                return await new HostedProcessRunner().RunAsync(command, cancellationToken);
            var options = S206TestSupport.OwnedNodeOptions(new()
            {
                ["HOSTED_WORKSPACE_ROOT"] = Path.GetDirectoryName(descriptor.WorkspaceRoot)!
            });
            var owned = await CreateAsync(options, descriptor.WorkspaceRoot, command.WorkingDirectory,
                descriptor.AccountId, descriptor.ProjectId);
            using var current = RequestContext.UseCurrent(owned.Context);
            return await new HostedProcessRunner(authority: owned.Store).RunAsync(command, cancellationToken);
        }
    }
}
