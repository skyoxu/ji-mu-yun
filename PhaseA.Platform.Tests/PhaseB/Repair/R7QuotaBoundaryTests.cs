using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class R7QuotaBoundaryTests
{
    [Fact]
    public async Task Account_usage_isolated_and_soft_delete_is_idempotent_across_restart()
    {
        var root = Directory.CreateTempSubdirectory("r7-quota-").FullName;
        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = Path.Combine(root, "metadata.sqlite3"),
            Pooling = false
        }.ToString();
        try
        {
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
            {
                ["HOSTED_WORKSPACE_ROOT"] = root
            });
            var store = new PhaseAMetadataStore(connectionString, options);
            var accountA = await store.CreateUserAccountAsync("r7-a", 1);
            var accountB = await store.CreateUserAccountAsync("r7-b", 1);
            var projectA = await CreateProject(store, accountA.AccountId, root, "r7-project-a");
            var projectB = await CreateProject(store, accountB.AccountId, root, "r7-project-b");
            var sourceA = Directory.CreateDirectory(Path.Combine(root, "a", "repo")).FullName;
            var sourceB = Directory.CreateDirectory(Path.Combine(root, "b", "repo")).FullName;
            File.WriteAllText(Path.Combine(sourceA, "supported.txt"), "a-content");
            File.WriteAllText(Path.Combine(sourceB, "supported.txt"), new string('b', 512));

            var storage = new WorkspaceStorageService(connectionString);
            storage.SetQuota(accountA.AccountId, 4096);
            storage.SetQuota(accountB.AccountId, 4096);
            var contextA = RequestContext.FromIdentity(new AccountIdentity(accountA.AccountId, "owner", PhaseAAuth.UserRole), "r7-a", accountA.Token, "r7-a");
            var contextB = RequestContext.FromIdentity(new AccountIdentity(accountB.AccountId, "owner", PhaseAAuth.UserRole), "r7-b", accountB.Token, "r7-b");
            _ = storage.CreateSnapshot(contextA, sourceA, "r7-snapshot-a", "r7-workspace-a", projectA, "r7-policy", new HashSet<string>());
            var beforeB = storage.GetQuota(accountA.AccountId).UsedBytes;
            _ = storage.CreateSnapshot(contextB, sourceB, "r7-snapshot-b", "r7-workspace-b", projectB, "r7-policy", new HashSet<string>());
            var afterB = storage.GetQuota(accountA.AccountId).UsedBytes;
            Assert.Equal(beforeB, afterB);

            storage.SoftDeleteSnapshot(contextA, "r7-snapshot-a");
            var afterDelete = storage.GetQuota(accountA.AccountId).UsedBytes;
            storage.SoftDeleteSnapshot(contextA, "r7-snapshot-a");
            Assert.Equal(afterDelete, storage.GetQuota(accountA.AccountId).UsedBytes);

            var restarted = new WorkspaceStorageService(connectionString);
            Assert.Equal(afterDelete, restarted.GetQuota(accountA.AccountId).UsedBytes);
            Assert.True(restarted.GetQuota(accountB.AccountId).UsedBytes > 0);
        }
        finally
        {
            SqliteConnection.ClearAllPools();
            try { Directory.Delete(root, true); } catch (IOException) { }
        }
    }

    private static async Task<string> CreateProject(PhaseAMetadataStore store, string accountId, string root, string projectId)
    {
        var projectRoot = Directory.CreateDirectory(Path.Combine(root, projectId)).FullName;
        var result = await store.CreateProjectAsync(new ProjectCreationCommand(
            projectId,
            accountId,
            projectId,
            projectId,
            "manual",
            "default",
            false,
            [],
            projectRoot,
            Path.Combine(projectRoot, "repo"),
            Path.Combine(projectRoot, "runtime"),
            Path.Combine(projectRoot, "meta")));
        Assert.True(result.Succeeded, result.FailureCode);
        return projectId;
    }
}
