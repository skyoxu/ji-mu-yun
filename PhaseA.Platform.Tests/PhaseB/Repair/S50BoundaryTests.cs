using Microsoft.Data.Sqlite;
using PhaseA.Platform.Security;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S50BoundaryTests : IDisposable
{
    private const string AccountId = "account-s50";
    private readonly string _root = Path.Combine(Path.GetTempPath(), "phase-s50-" + Guid.NewGuid().ToString("N"));
    private readonly string _connectionString;
    private readonly WorkspaceStorageService _storage;
    private readonly RequestContext _context;

    public S50BoundaryTests()
    {
        Directory.CreateDirectory(_root);
        _connectionString = $"Data Source={Path.Combine(_root, "storage.db")}";
        using (var connection = new SqliteConnection(_connectionString))
        {
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText = "CREATE TABLE projects (id TEXT PRIMARY KEY, account_id TEXT NOT NULL);";
            command.ExecuteNonQuery();
        }

        _storage = new WorkspaceStorageService(_connectionString);
        _context = new RequestContext("principal-s50", AccountId, new HashSet<string>(StringComparer.Ordinal) { "member" }, "credential-s50", "correlation-s50");
    }

    [Fact]
    public void O_0540475EB849()
    {
        var record = CreateSnapshot("retention-complete", "project-retention", 8);
        _storage.SoftDeleteSnapshot(_context, record.Manifest.SnapshotId);
        var actions = GetAuditActions(record.Manifest.SnapshotId);

        Assert.True(
            record.Manifest.Retention == "30-day" && actions.Contains("expiry") && actions.Contains("cleanup") && actions.Contains("deletion"),
            "FAILURE-O-0540475EB849: the 30-day retention action matrix did not record an auditable deletion.");
    }

    [Fact]
    public void O_17ED20E8D615()
    {
        var record = CreateSnapshot("safe-selector", "project-retention", 8);
        var unsafeBroadPrefix = Path.Combine(_root, "placements");
        var rejected = Record.Exception(() => _storage.SoftDeleteSnapshot(_context, unsafeBroadPrefix)) is KeyNotFoundException;
        var unchanged = Assert.Single(_storage.ListSnapshots(AccountId, "project-retention")).Deleted == false;

        Assert.True(rejected && unchanged, "FAILURE-O-17ED20E8D615: an unsafe broad path selector was not refused before changing the selected resource.");
    }

    [Fact]
    public void O_2EDAD0C079A7()
    {
        var pinned = CreateSnapshot("pinned-input", "project-retention", 8);
        _storage.SoftDeleteSnapshot(_context, pinned.Manifest.SnapshotId);
        var persisted = Assert.Single(_storage.ListSnapshots(AccountId, "project-retention", includeDeleted: true));

        Assert.True(!persisted.Deleted, "FAILURE-O-2EDAD0C079A7: a pinned retention input was made unavailable by an exercised retention action.");
    }

    [Fact]
    public void O_350460F95643()
    {
        var record = CreateSnapshot("deletion-profile", "project-retention", 8);
        _storage.SoftDeleteSnapshot(_context, record.Manifest.SnapshotId);

        Assert.True(
            record.Manifest.Retention == "30-day" && GetAuditActions(record.Manifest.SnapshotId).Contains("deletion"),
            "FAILURE-O-350460F95643: deletion was not represented as an action under the 30-day retention profile.");
    }

    [Fact]
    public void O_38DA71E9D444()
    {
        _storage.SetQuota(AccountId, 100);
        CreateSnapshot("quota-project-one", "project-one", 11);
        CreateSnapshot("quota-project-two", "project-two", 13);

        Assert.True(_storage.GetQuota(AccountId).UsedBytes == 24, "FAILURE-O-38DA71E9D444: user quota did not include actual bytes from every owned Snapshot.");
    }

    [Fact]
    public void O_571C78093983()
    {
        var root = CreateRoot("ordinary-edit", "ordinary.txt", 8);
        File.AppendAllText(Path.Combine(root, "ordinary.txt"), "edit");

        Assert.True(!_storage.ListSnapshots(AccountId, "project-edit").Any(), "FAILURE-O-571C78093983: an ordinary edit created a Snapshot.");
    }

    [Fact]
    public void O_5D176438FFA6()
    {
        var callerInfluencedRoot = CreateRoot("caller-host-path", "artifact.dat", 8);
        EnsureProject("project-logical-owner");
        var record = _storage.CreateSnapshot(_context, callerInfluencedRoot, "logical-owner", "workspace-logical", "project-logical-owner", "policy-30-day", new HashSet<string>(StringComparer.OrdinalIgnoreCase));

        Assert.True(
            record.Manifest.AccountId == AccountId && record.Manifest.ProjectId == "project-logical-owner" && record.Manifest.WorkspaceId == "workspace-logical",
            "FAILURE-O-5D176438FFA6: a caller-controlled host path determined resource ownership.");
    }

    [Fact]
    public void O_7958B030A69B()
    {
        _storage.SetQuota(AccountId, 20);
        CreateSnapshot("shared-quota-one", "project-one", 12);
        var rejected = Record.Exception(() => CreateSnapshot("shared-quota-two", "project-two", 9)) is IOException;

        Assert.True(rejected, "FAILURE-O-7958B030A69B: quota was not enforced as shared user-level actual usage.");
    }

    [Fact]
    public void O_7E825F215702()
    {
        var liveRoot = CreateRoot("live-workspace", "live.dat", 7);
        _storage.SetQuota(AccountId, 100);
        var measuredLiveBytes = new FileInfo(Path.Combine(liveRoot, "live.dat")).Length;

        Assert.True(_storage.GetQuota(AccountId).UsedBytes == measuredLiveBytes, "FAILURE-O-7E825F215702: user quota excluded actual live Workspace bytes.");
    }

    [Fact]
    public void O_B085F1A35441()
    {
        var liveRoot = CreateRoot("restart-live-workspace", "live.dat", 7);
        _storage.SetQuota(AccountId, 100);
        var snapshot = CreateSnapshot("soft-deleted-snapshot", "project-restart", 5);
        _storage.SoftDeleteSnapshot(_context, snapshot.Manifest.SnapshotId);
        var restarted = new WorkspaceStorageService(_connectionString);
        var measuredActiveWorkspaceBytes = new FileInfo(Path.Combine(liveRoot, "live.dat")).Length;

        Assert.True(restarted.GetQuota(AccountId).UsedBytes == measuredActiveWorkspaceBytes, "FAILURE-O-B085F1A35441: restart reconciliation did not retain active live Workspace logical usage.");
    }

    [Fact]
    public void O_CC964B3582F6()
    {
        var record = CreateSnapshot("deletion-audit", "project-retention", 8);
        _storage.SoftDeleteSnapshot(_context, record.Manifest.SnapshotId);

        Assert.True(GetAuditActions(record.Manifest.SnapshotId).Contains("deletion"), "FAILURE-O-CC964B3582F6: the exercised deletion has no deletion audit record.");
    }

    [Fact]
    public void O_D2840720344F()
    {
        var record = CreateSnapshot("logical-create", "project-create", 8, workspaceId: "workspace-create");

        Assert.True(
            record.Manifest.AccountId == AccountId && record.Manifest.ProjectId == "project-create" && record.Manifest.WorkspaceId == "workspace-create",
            "FAILURE-O-D2840720344F: creation did not preserve logical identity through the local storage contract.");
    }

    [Fact]
    public void O_D664E1FFDFB3()
    {
        var record = CreateSnapshot("expiry-profile", "project-retention", 8);
        _storage.SoftDeleteSnapshot(_context, record.Manifest.SnapshotId);

        Assert.True(
            record.Manifest.Retention == "30-day" && GetAuditActions(record.Manifest.SnapshotId).Contains("expiry"),
            "FAILURE-O-D664E1FFDFB3: expiry was not recorded under the 30-day retention profile.");
    }

    [Fact]
    public void O_D9BA6D66CD0D()
    {
        var callerInfluencedRoot = CreateRoot("caller-storage-path", "artifact.dat", 8);
        EnsureProject("project-storage-authority");
        var record = _storage.CreateSnapshot(_context, callerInfluencedRoot, "storage-authority", "workspace-storage", "project-storage-authority", "policy-30-day", new HashSet<string>(StringComparer.OrdinalIgnoreCase));

        Assert.True(
            record.Manifest.AccountId == AccountId && record.Manifest.ProjectId == "project-storage-authority" && record.Manifest.WorkspaceId == "workspace-storage",
            "FAILURE-O-D9BA6D66CD0D: a caller-controlled host path determined storage authority.");
    }

    [Fact]
    public void O_DF1BBA997C44()
    {
        const string projectId = "project-mixed";
        EnsureProject(projectId);
        var root = CreateRoot("mixed-snapshot", "persistent.godot", 8);
        File.WriteAllBytes(Path.Combine(root, "temporary.tmp"), Enumerable.Repeat((byte)'t', 5).ToArray());
        var record = _storage.CreateSnapshot(_context, root, "mixed-snapshot", "workspace-mixed", projectId, "policy-30-day", new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ".tmp" });

        Assert.True(record.Manifest.Files.All(file => file.RelativePath != "temporary.tmp"), "FAILURE-O-DF1BBA997C44: temporary content was retained in Snapshot inventory.");
    }

    [Fact]
    public void O_E20FAEA5ABC8()
    {
        var original = CreateSnapshot("placement-change", "project-placement", 8, workspaceId: "workspace-placement");
        var newRoot = Path.Combine(_root, "moved-placement");
        Directory.Move(Path.GetDirectoryName(original.ManifestPath)!, newRoot);
        var restarted = new WorkspaceStorageService(_connectionString);
        var resolved = restarted.ListSnapshots(AccountId, "project-placement", includeDeleted: true);

        Assert.True(
            resolved.Count == 1 && resolved[0].Manifest.WorkspaceId == "workspace-placement" && resolved[0].Manifest.AccountId == AccountId && resolved[0].Manifest.ProjectId == "project-placement",
            "FAILURE-O-E20FAEA5ABC8: moving placement lost logical Workspace identity during resolution.");
    }

    [Fact]
    public void O_E79036BF6FA3()
    {
        var record = CreateSnapshot("persistent-snapshot", "project-persistent", 8, fileName: "save.tres");
        var file = Assert.Single(record.Manifest.Files);

        Assert.True(file.RelativePath == "save.tres" && file.Length == 8, "FAILURE-O-E79036BF6FA3: supported persistent artifact data was omitted from Snapshot output.");
    }

    [Fact]
    public void O_EB1DEE188517()
    {
        _storage.SetQuota(AccountId, 16);
        CreateSnapshot("existing-snapshot", "project-quota", 8);
        var liveRoot = CreateRoot("pending-live-workspace", "live.dat", 8);
        var measuredLiveBytes = new FileInfo(Path.Combine(liveRoot, "live.dat")).Length;
        var rejected = Record.Exception(() => CreateSnapshot("pending-write", "project-quota", 1)) is IOException;

        Assert.True(measuredLiveBytes == 8 && rejected, "FAILURE-O-EB1DEE188517: an over-limit Workspace write was accepted without aggregate live Workspace and Snapshot accounting.");
    }

    [Fact]
    public void O_FA0C21A344E7()
    {
        var conflictingPlacement = CreateRoot("placement-account-other-project-other", "artifact.dat", 8);
        EnsureProject("project-server-owned");
        var record = _storage.CreateSnapshot(_context, conflictingPlacement, "placement-nonauthority", "workspace-server-owned", "project-server-owned", "policy-30-day", new HashSet<string>(StringComparer.OrdinalIgnoreCase));

        Assert.True(
            record.Manifest.AccountId == AccountId && record.Manifest.ProjectId == "project-server-owned",
            "FAILURE-O-FA0C21A344E7: supplied placement values changed server-controlled ownership.");
    }

    private WorkspaceSnapshotRecord CreateSnapshot(string snapshotId, string projectId, int bytes, string? workspaceId = null, string fileName = "artifact.dat")
    {
        EnsureProject(projectId);
        var root = CreateRoot(snapshotId, fileName, bytes);
        return _storage.CreateSnapshot(_context, root, snapshotId, workspaceId ?? "workspace-s50", projectId, "policy-30-day", new HashSet<string>(StringComparer.OrdinalIgnoreCase));
    }

    private string CreateRoot(string name, string fileName, int bytes)
    {
        var root = Path.Combine(_root, "placements", name + "-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        File.WriteAllBytes(Path.Combine(root, fileName), Enumerable.Repeat((byte)'x', bytes).ToArray());
        return root;
    }

    private void EnsureProject(string projectId)
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "INSERT OR IGNORE INTO projects(id,account_id) VALUES($id,$account)";
        command.Parameters.AddWithValue("$id", projectId);
        command.Parameters.AddWithValue("$account", AccountId);
        command.ExecuteNonQuery();
    }

    private HashSet<string> GetAuditActions(string snapshotId)
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT action FROM snapshot_retention_audit WHERE snapshot_id=$id";
        command.Parameters.AddWithValue("$id", snapshotId);
        using var reader = command.ExecuteReader();
        var actions = new HashSet<string>(StringComparer.Ordinal);
        while (reader.Read()) actions.Add(reader.GetString(0));
        return actions;
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
