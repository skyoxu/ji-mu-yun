using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S49BoundaryTests
{
    [Fact] public async Task O_0207F0833E73() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-owner",1); var p=await f.CreateProjectAsync(a.AccountId); var snapshot=await f.Store.GetProjectSnapshotAsync(p); Require(snapshot is not null,"FAILURE-O-0207F0833E73"); }
    [Fact] public async Task O_03CC05EA7AE3() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-project",1); var p=await f.CreateProjectAsync(a.AccountId); _=await f.Store.CreateRunAsync(p,null,"evidence"); Require(await f.ScalarAsync("SELECT project_id FROM runs WHERE project_id=$p",("$p",p)),"FAILURE-O-03CC05EA7AE3"); }
    [Fact] public async Task O_042590B6DEE0() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-scope",1); Require(await f.ScalarAsync("SELECT token_hash FROM accounts WHERE id=$a",("$a",a.AccountId)),"FAILURE-O-042590B6DEE0"); }
    [Fact] public async Task O_056E42118EAA() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-account",1); await f.Store.RecordAdminAccountAuditEventAsync(a.AccountId,"pin",a.AccountId,new { project_id="p" }); Require(await f.ScalarAsync("SELECT actor_account_id FROM admin_account_audit_events WHERE target_account_id=$a",("$a",a.AccountId)),"FAILURE-O-056E42118EAA"); }
    [Fact] public async Task O_11A24FF68C8D() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-status",1); Require(await f.ScalarAsync("SELECT is_disabled FROM accounts WHERE id=$a",("$a",a.AccountId)),"FAILURE-O-11A24FF68C8D"); }
    [Fact] public async Task O_137FC21EF88F() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-revoke",1); var r=await f.Store.RotateUserTokenAsync(a.AccountId); Require(r is not null,"FAILURE-O-137FC21EF88F"); Require(await f.ScalarAsync("SELECT token_hash FROM accounts WHERE id=$a",("$a",a.AccountId)),"FAILURE-O-137FC21EF88F"); }
    [Fact] public async Task O_1416ED189D0E() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-time",1); await f.Store.RecordAdminAccountAuditEventAsync(a.AccountId,"time",a.AccountId,new { }); Require(await f.ScalarAsync("SELECT created_utc FROM admin_account_audit_events WHERE actor_account_id=$a",("$a",a.AccountId)),"FAILURE-O-1416ED189D0E"); }
    [Fact] public async Task O_265C09B9F588() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-legacy",1); var p=await f.CreateProjectAsync(a.AccountId); Require((await f.Store.GetProjectSnapshotAsync(p))?.AccountId==a.AccountId,"FAILURE-O-265C09B9F588"); }
    [Fact] public async Task O_4C8C665EB67B() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-pin",1); await f.Store.RecordAdminAccountAuditEventAsync(a.AccountId,"pin",a.AccountId,new { }); var e=await f.Store.ListAdminAccountAuditEventsAsync(20); Require(e.Any(x=>x.Action=="pin"),"FAILURE-O-4C8C665EB67B"); }
    [Fact] public async Task O_4F0BF4CA0C6E() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-created",1); Require(await f.ScalarAsync("SELECT created_utc FROM accounts WHERE id=$a",("$a",a.AccountId)),"FAILURE-O-4F0BF4CA0C6E"); }
    [Fact] public async Task O_58816733B7B4() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-retain",1); await f.ExecuteAsync("UPDATE accounts SET is_disabled=1 WHERE id=$a",("$a",a.AccountId)); await f.ExecuteAsync("UPDATE accounts SET is_disabled=0 WHERE id=$a",("$a",a.AccountId)); Require(await f.ScalarAsync("SELECT username FROM accounts WHERE id=$a",("$a",a.AccountId)),"FAILURE-O-58816733B7B4"); }
    [Fact] public async Task O_75715824A625() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-runner",1); var p=await f.CreateProjectAsync(a.AccountId); var r=await f.Store.CreateRunAsync(p,null,"runner"); Require(await f.ScalarAsync("SELECT run_type FROM runs WHERE id=$r",("$r",r)),"FAILURE-O-75715824A625"); }
    [Fact] public async Task O_7A20639460B3() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-run",1); var p=await f.CreateProjectAsync(a.AccountId); var r=await f.Store.CreateRunAsync(p,null,"run"); Require(await f.ScalarAsync("SELECT id FROM runs WHERE id=$r",("$r",r)),"FAILURE-O-7A20639460B3"); }
    [Fact] public async Task O_968D2375FB3C() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-auth",1); await f.Store.RecordAdminAccountAuditEventAsync(a.AccountId,"authorize",a.AccountId,new { }); var e=await f.Store.ListAdminAccountAuditEventsAsync(20); Require(e.Any(x=>x.Action=="authorize"),"FAILURE-O-968D2375FB3C"); }
    [Fact] public async Task O_AACAD4D36374() { await using var f=await F.CreateAsync(); var a=await f.Store.CreateUserAccountAsync("s49-ref",1); var p=await f.CreateProjectAsync(a.AccountId); var r=await f.Store.CreateRunAsync(p,null,"restore"); Require(await f.ScalarAsync("SELECT id FROM runs WHERE id=$r",("$r",r)),"FAILURE-O-AACAD4D36374"); }

    private static void Require(object? value,string id) { if(value is null || (value is string s && string.IsNullOrWhiteSpace(s))) throw new Xunit.Sdk.XunitException($"{id}: required evidence was missing"); }
    private sealed class F : IAsyncDisposable
    {
        private readonly string _db; public string Cs { get; } public PhaseAMetadataStore Store { get; }
        private F(string db,string cs,PhaseAMetadataStore store){_db=db;Cs=cs;Store=store;}
        public static async Task<F> CreateAsync(){var db=Path.Combine(Path.GetTempPath(),$"s49-{Guid.NewGuid():N}.sqlite3");var cs=$"Data Source={db}";await SqliteMetadataSchema.InitializeAsync(cs);var o=PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string,string?>());return new F(db,cs,new PhaseAMetadataStore(cs,o));}
        public async Task<string> CreateProjectAsync(string account){var id=$"p-{Guid.NewGuid():N}";var root=Path.Combine(Path.GetTempPath(),id);Directory.CreateDirectory(root);var result=await Store.CreateProjectAsync(new ProjectCreationCommand(id,account,"s49","s49","test","test",false,Array.Empty<string>(),root,root,root,root));return result.ProjectId;}
        public async Task<object?> ScalarAsync(string sql,params (string,string)[] ps){await using var c=new SqliteConnection(Cs);await c.OpenAsync();await using var cmd=c.CreateCommand();cmd.CommandText=sql;foreach(var p in ps)cmd.Parameters.AddWithValue(p.Item1,p.Item2);return await cmd.ExecuteScalarAsync();}
        public async Task ExecuteAsync(string sql,params (string,string)[] ps){await using var c=new SqliteConnection(Cs);await c.OpenAsync();await using var cmd=c.CreateCommand();cmd.CommandText=sql;foreach(var p in ps)cmd.Parameters.AddWithValue(p.Item1,p.Item2);await cmd.ExecuteNonQueryAsync();}
        public ValueTask DisposeAsync(){SqliteConnection.ClearAllPools();try{File.Delete(_db);}catch{}return ValueTask.CompletedTask;}
    }
}
