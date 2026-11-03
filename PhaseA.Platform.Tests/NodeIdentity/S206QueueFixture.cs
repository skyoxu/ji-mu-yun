using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Tests.NodeIdentity;

// ADR-0061: queue contract tests authenticate real disposable owners before injecting queue faults.
internal sealed class S206QueueFixture
{
    internal PhaseAMetadataStore Store = null!;
    internal RequestContext Context = null!, ControlContext = null!;
    internal string AccountId => Context.AccountId;
    internal static async Task<S206QueueFixture> CreateAsync(string projectId, bool administrator = false)
    {
        var root = S206TestSupport.CreateOwnedFixtureRoot("ci-queue-contract-");
        Directory.CreateDirectory(root);
        var options = S206TestSupport.OwnedNodeOptions(new() { ["HOSTED_WORKSPACE_ROOT"] = Path.Combine(root, "workspaces") });
        var connection = new SqliteConnectionStringBuilder { DataSource = Path.Combine(root, "metadata.sqlite3"), Pooling = false }.ToString();
        await SqliteMetadataSchema.InitializeSingleNodeTestAsync(connection, options);
        var f = new S206QueueFixture { Store = new PhaseAMetadataStore(connection, options) };
        f.ControlContext = await f.Store.ResolveStartupMaintenanceContextAsync();
        var credential = options.AdminTokenHash;
        if (!administrator)
        {
            var owner = await f.Store.CreateUserAccountAsync("queue-owner", 2);
            credential = PhaseAAuth.HashTokenForStorage(owner.Token);
        }
        f.Context = await S206TestSupport.FixtureContextAsync(f.Store, credential);
        var layout = WorkspaceLayoutBuilder.Build(options.HostedWorkspaceRoot, f.AccountId, projectId);
        var project = await f.Store.CreateProjectAsync(new(projectId, f.AccountId, "Queue", "Queue", "manual", "default", false, [],
            layout.RootPath, layout.RepoPath, layout.RuntimePath, layout.MetaPath));
        if (!project.Succeeded) throw new InvalidOperationException("Owned queue project setup failed.");
        return f;
    }
}
