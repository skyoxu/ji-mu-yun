using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;
namespace PhaseA.Platform.Tests.PhaseB.Repair;
public sealed class S1BoundaryTests
{
    [Fact]
    public async Task O_D3E322003EAB()
    {
        await using var f=await F.CreateAsync();
        var a=await f.Store.CreateUserAccountAsync("s1",1);
        var p="s1-"+Guid.NewGuid().ToString("N");
        await f.ExecuteAsync("INSERT INTO projects (id,account_id,name,game_name,game_type_source,template_rule_id,created_utc) VALUES ($p,$a,'s1','s1','legacy','legacy',$t)",("$p",p),("$a",a.AccountId),("$t",DateTimeOffset.UtcNow.ToString("O")));
        await f.ExecuteUnsafeAsync("UPDATE projects SET account_id=$owner WHERE id=$p",("$owner",a.AccountId+"|orphan"),("$p",p));
        _=await f.Store.GetProjectSnapshotAsync(p);
        var correlation=await f.ScalarAsync("SELECT correlation_id FROM project_ownership_lineage WHERE project_id=$p",("$p",p));
        if(correlation is null || string.IsNullOrWhiteSpace(correlation.ToString())) throw new Xunit.Sdk.XunitException("FAILURE-O-D3E322003EAB: correlation was missing");
    }
    private sealed class F:IAsyncDisposable
    { private readonly string db; public string Cs{get;} public PhaseAMetadataStore Store{get;}
      private F(string d,string c,PhaseAMetadataStore s){db=d;Cs=c;Store=s;}
      public static async Task<F>CreateAsync(){var d=Path.Combine(Path.GetTempPath(),$"s1-{Guid.NewGuid():N}.sqlite3");var c=$"Data Source={d}";await SqliteMetadataSchema.InitializeAsync(c);var o=PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string,string?>());return new F(d,c,new PhaseAMetadataStore(c,o));}
      public async Task ExecuteAsync(string sql,params(string,string)[] ps){await using var c=new SqliteConnection(Cs);await c.OpenAsync();await using var x=c.CreateCommand();x.CommandText=sql;foreach(var p in ps)x.Parameters.AddWithValue(p.Item1,p.Item2);await x.ExecuteNonQueryAsync();}
      public async Task ExecuteUnsafeAsync(string sql,params(string,string)[] ps){await using var c=new SqliteConnection(Cs);await c.OpenAsync();await using(var pragma=c.CreateCommand()){pragma.CommandText="PRAGMA foreign_keys=OFF;";await pragma.ExecuteNonQueryAsync();}await using var x=c.CreateCommand();x.CommandText=sql;foreach(var p in ps)x.Parameters.AddWithValue(p.Item1,p.Item2);await x.ExecuteNonQueryAsync();}
      public async Task<object?> ScalarAsync(string sql,params(string,string)[] ps){await using var c=new SqliteConnection(Cs);await c.OpenAsync();await using var x=c.CreateCommand();x.CommandText=sql;foreach(var p in ps)x.Parameters.AddWithValue(p.Item1,p.Item2);return await x.ExecuteScalarAsync();}
      public ValueTask DisposeAsync(){SqliteConnection.ClearAllPools();try{File.Delete(db);}catch{}return ValueTask.CompletedTask;}
    }
}
