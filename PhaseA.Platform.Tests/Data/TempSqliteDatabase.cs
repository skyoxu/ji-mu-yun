using Microsoft.Data.Sqlite;

namespace PhaseA.Platform.Tests.Data;

internal sealed class TempSqliteDatabase : IDisposable
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

    public void Dispose()
    {
        if (File.Exists(_path))
        {
            File.Delete(_path);
        }
    }
}
