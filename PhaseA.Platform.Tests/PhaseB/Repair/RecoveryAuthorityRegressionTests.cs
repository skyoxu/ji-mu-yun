using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Workspaces;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

// ADR-0036/0061: each negative changes a current production source.
public sealed class RecoveryAuthorityRegressionTests : IDisposable
{
    private readonly string _root = Directory.CreateTempSubdirectory("recovery-authority-").FullName;
    private readonly string _connection;
    private readonly string _account;
    private const string Project = "authority-project";
    private string Repo => Path.Combine(_root, "project", "repo");

    public RecoveryAuthorityRegressionTests()
    {
        _connection = $"Data Source={Path.Combine(_root, "metadata.sqlite3")};Pooling=False";
        SqliteMetadataSchema.InitializeAsync(_connection).GetAwaiter().GetResult();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?> { ["HOSTED_WORKSPACE_ROOT"] = _root });
        var store = new PhaseAMetadataStore(_connection, options);
        _account = store.CreateUserAccountAsync("authority-owner", 1).GetAwaiter().GetResult().AccountId;
        var projectRoot = Path.Combine(_root, "project");
        store.CreateProjectAsync(new ProjectCreationCommand(Project, _account, "Authority", "Authority", "manual", "default", false, [],
            projectRoot, Repo, Path.Combine(projectRoot, "runtime"), Path.Combine(projectRoot, "meta"))).GetAwaiter().GetResult();
        RouteAuthorityFixture.Seed(_connection, _account, Project, projectRoot);
    }

    private RouteRecoveryAuthoritySnapshot Resolve() => new RouteRecoveryAuthorityResolver(_connection).Resolve(_account, Project);

    [Fact]
    public void NoActiveSessionOrRepair_IsNotApplicable() => Assert.True(Resolve().CanContinue);

    [Theory]
    [InlineData("")]
    [InlineData("{}")]
    [InlineData("not-json")]
    public void InvalidContract_Blocks(string content)
    {
        File.WriteAllText(Path.Combine(Repo, "routes/prototype-contract/latest.json"), content);
        Assert.Contains("prototype_contract_missing", Resolve().Blockers);
    }

    [Fact]
    public void ChangedGdd_InvalidatesFrozenContract()
    {
        File.AppendAllText(Path.Combine(Repo, "docs/gdd/GDD.md"), " changed");
        Assert.Contains("prototype_contract_missing", Resolve().Blockers);
    }

    [Fact]
    public void ChangedPersistedPrompt_Blocks()
    {
        File.AppendAllText(Path.Combine(Repo, "meta/prompt.json"), " changed");
        Assert.Contains("selected_route_skill_prompt_block_missing", Resolve().Blockers);
    }

    [Fact]
    public void ActiveSessionWithoutCurrentGoal_Blocks()
    {
        InsertSession("active");
        Assert.Contains("current_goal_state_invalid", Resolve().Blockers);
    }

    [Fact]
    public void NeedsFixWithoutDiagnostic_Blocks()
    {
        InsertSession("needs_fix");
        Assert.Contains("current_repair_evidence_invalid", Resolve().Blockers);
    }

    [Fact]
    public void ValidActiveGoal_PermitsContinuation()
    {
        InsertSession("active");
        Execute("INSERT INTO project_iteration_goals(id,session_id,goal_index,title,description,status,created_utc,updated_utc) VALUES('g','s',0,'Goal','Implement current goal','ready',$utc,$utc)");
        Assert.True(Resolve().CanContinue);
    }

    private void InsertSession(string status) => Execute("INSERT INTO project_iteration_sessions(id,project_id,account_id,source_kind,source_message,overall_goal,status,current_goal_index,created_utc,updated_utc) VALUES('s',$project,$account,'manual','request','Current goal','" + status + "',0,$utc,$utc)");

    private void Execute(string sql)
    {
        using var db = new SqliteConnection(_connection); db.Open(); using var command = db.CreateCommand();
        command.CommandText = sql;
        command.Parameters.AddWithValue("$project", Project); command.Parameters.AddWithValue("$account", _account);
        command.Parameters.AddWithValue("$utc", DateTimeOffset.UtcNow.ToString("O")); command.ExecuteNonQuery();
    }

    public void Dispose() { SqliteConnection.ClearAllPools(); Directory.Delete(_root, true); }
}
