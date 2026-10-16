using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Tests.Data;

internal sealed class TempSqliteDatabase : IDisposable, IAsyncDisposable
{
    private readonly string _path;

    private TempSqliteDatabase(string path)
    {
        _path = path;
        ConnectionString = new SqliteConnectionStringBuilder
        {
            DataSource = path,
            Pooling = false
        }.ToString();
    }

    public string ConnectionString { get; }

    public static TempSqliteDatabase Create()
    {
        var path = Path.Combine(Path.GetTempPath(), $"phase-a-{Guid.NewGuid():N}.db");
        return new TempSqliteDatabase(path);
    }

    public async Task<HashSet<string>> ReadTableNamesAsync()
    {
        var tables = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        await using var connection = new SqliteConnection(ConnectionString);
        await connection.OpenAsync();

        await using var command = connection.CreateCommand();
        command.CommandText = "SELECT name FROM sqlite_master WHERE type = 'table';";
        await using var reader = await command.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            tables.Add(reader.GetString(0));
        }

        return tables;
    }

    // ADR-0061: terminal run readback can precede final background audit writes.
    // Yield while those connections close; synchronous sleeps block test continuations.
    public async ValueTask DisposeAsync()
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (File.Exists(_path))
        {
            try
            {
                File.Delete(_path);
                return;
            }
            catch (IOException) when (DateTimeOffset.UtcNow < deadline)
            {
                await Task.Delay(25).ConfigureAwait(false);
            }
        }
    }

    public void Dispose()
    {
        if (File.Exists(_path))
        {
            for (var attempt = 0; attempt < 10; attempt++)
            {
                try
                {
                    File.Delete(_path);
                    break;
                }
                catch (IOException) when (attempt < 9)
                {
                    Thread.Sleep(100);
                }
            }
        }
    }
}
