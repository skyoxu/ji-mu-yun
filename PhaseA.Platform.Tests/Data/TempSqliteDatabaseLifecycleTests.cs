using Microsoft.Data.Sqlite;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class TempSqliteDatabaseLifecycleTests
{
    // ADR-0061: cleanup must yield to the owning background connection's completion.
    [Fact]
    public async Task DisposeAsync_RemovesDatabaseAfterActiveConnectionCloses()
    {
        var database = TempSqliteDatabase.Create();
        var path = new SqliteConnectionStringBuilder(database.ConnectionString).DataSource;
        await using var connection = new SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        var cleanup = database.DisposeAsync().AsTask();
        try
        {
            if (OperatingSystem.IsWindows())
            {
                await Task.Delay(50);
                Assert.False(cleanup.IsCompleted);
            }
        }
        finally
        {
            await connection.DisposeAsync();
            await cleanup.WaitAsync(TimeSpan.FromSeconds(6));
        }
        Assert.False(File.Exists(path));
    }
}
