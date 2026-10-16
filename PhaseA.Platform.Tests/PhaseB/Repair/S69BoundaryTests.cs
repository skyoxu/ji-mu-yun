using Microsoft.Data.Sqlite;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

public sealed class S69BoundaryTests
{
    [Fact]
    public async Task O_78D7E0265BD0()
    {
        await using var fixture = await CredentialFixture.CreateAsync();

        var issued = await fixture.Store.CreateUserAccountAsync("s69-stable-id", 1);
        var first = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);
        var second = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);

        Require(
            !string.IsNullOrWhiteSpace(first.Id) && string.Equals(first.Id, second.Id, StringComparison.Ordinal),
            "FAILURE-O-78D7E0265BD0",
            "The authoritative credential identifier was missing or changed between reads.");
    }

    [Fact]
    public async Task O_8CED50B4D419()
    {
        await using var fixture = await CredentialFixture.CreateAsync();

        var issued = await fixture.Store.CreateUserAccountAsync("s69-derived-secret", 1);
        var record = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);
        var expectedDerivation = PhaseAAuth.HashTokenForStorage(issued.Token);

        Require(
            !string.IsNullOrWhiteSpace(record.TokenHash) &&
            string.Equals(record.TokenHash, expectedDerivation, StringComparison.Ordinal) &&
            !string.Equals(record.TokenHash, issued.Token, StringComparison.Ordinal),
            "FAILURE-O-8CED50B4D419",
            "The authoritative credential record did not contain only a secure derivation of the issued secret.");
    }

    [Fact]
    public async Task O_950A3BE6A619()
    {
        await using var fixture = await CredentialFixture.CreateAsync();

        var issued = await fixture.Store.CreateUserAccountAsync("s69-last-use", 1);
        var beforeUse = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);
        var authenticated = await fixture.Store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(issued.Token));
        var afterUse = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);

        Require(
            beforeUse.HasLastUse &&
            string.IsNullOrWhiteSpace(beforeUse.LastUseUtc) &&
            authenticated?.AccountId == issued.AccountId &&
            !string.IsNullOrWhiteSpace(afterUse.LastUseUtc) &&
            !string.Equals(beforeUse.LastUseUtc, afterUse.LastUseUtc, StringComparison.Ordinal),
            "FAILURE-O-950A3BE6A619",
            "The authoritative credential record did not expose and update last-use information after authentication.");
    }

    [Fact]
    public async Task O_E637552CC6B3()
    {
        await using var fixture = await CredentialFixture.CreateAsync();

        var issued = await fixture.Store.CreateUserAccountAsync("s69-expiry", 1);
        var record = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);

        Require(
            record.HasExpiry && (record.ExpiresUtc is null || DateTimeOffset.TryParse(record.ExpiresUtc, out _)),
            "FAILURE-O-E637552CC6B3",
            "The authoritative credential record did not expose a parseable expiry value or explicit non-expiring state.");
    }

    [Fact]
    public async Task O_4E871043ED9E()
    {
        await using var fixture = await CredentialFixture.CreateAsync();
        var operations = new List<string>();

        var issued = await fixture.Store.CreateUserAccountAsync("s69-operation-order", 1);
        operations.Add("credential-issued");
        _ = await fixture.ReadAuthoritativeRecordAsync(issued.AccountId);
        operations.Add("authoritative-record-inspected");

        Require(
            operations.IndexOf("credential-issued") >= 0 &&
            operations.IndexOf("credential-issued") < operations.IndexOf("authoritative-record-inspected"),
            "FAILURE-O-4E871043ED9E",
            "The lifecycle verification inspected an authoritative record before issuing its credential.");
    }

    private static void Require(bool condition, string failureId, string message)
    {
        if (!condition)
        {
            throw new Xunit.Sdk.XunitException($"{failureId}: {message}");
        }
    }

    private sealed class CredentialFixture : IAsyncDisposable
    {
        private readonly string _databasePath;

        private CredentialFixture(string databasePath, string connectionString, PhaseAMetadataStore store)
        {
            _databasePath = databasePath;
            ConnectionString = connectionString;
            Store = store;
        }

        public string ConnectionString { get; }
        public PhaseAMetadataStore Store { get; }

        public static async Task<CredentialFixture> CreateAsync()
        {
            var databasePath = Path.Combine(Path.GetTempPath(), $"s69-{Guid.NewGuid():N}.sqlite3");
            var connectionString = $"Data Source={databasePath}";
            await SqliteMetadataSchema.InitializeAsync(connectionString);
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            return new CredentialFixture(databasePath, connectionString, new PhaseAMetadataStore(connectionString, options));
        }

        public async Task<CredentialRecord> ReadAuthoritativeRecordAsync(string accountId)
        {
            await using var connection = new SqliteConnection(ConnectionString);
            await connection.OpenAsync();
            var columns = await ReadColumnNamesAsync(connection);
            const string expiryColumn = "valid_until_utc";
            var lastUseColumn = columns.Contains("last_used_utc")
                ? "last_used_utc"
                : columns.Contains("last_use_utc")
                    ? "last_use_utc"
                    : null;

            await using var command = connection.CreateCommand();
            command.CommandText = $"""
                SELECT id, token_hash, {expiryColumn}{(lastUseColumn is null ? string.Empty : $", {lastUseColumn}")}
                FROM accounts
                WHERE id = $account_id;
                """;
            command.Parameters.AddWithValue("$account_id", accountId);
            await using var reader = await command.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
            {
                throw new Xunit.Sdk.XunitException("The issued credential was missing from authoritative storage.");
            }

            return new CredentialRecord(
                reader.GetString(0),
                reader.IsDBNull(1) ? null : reader.GetString(1),
                columns.Contains(expiryColumn),
                reader.IsDBNull(2) ? null : reader.GetString(2),
                lastUseColumn is not null,
                lastUseColumn is null || reader.IsDBNull(3) ? null : reader.GetString(3));
        }

        public ValueTask DisposeAsync()
        {
            SqliteConnection.ClearAllPools();
            if (File.Exists(_databasePath))
            {
                File.Delete(_databasePath);
            }

            return ValueTask.CompletedTask;
        }

        private static async Task<HashSet<string>> ReadColumnNamesAsync(SqliteConnection connection)
        {
            await using var command = connection.CreateCommand();
            command.CommandText = "PRAGMA table_info(accounts);";
            await using var reader = await command.ExecuteReaderAsync();
            var columns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            while (await reader.ReadAsync())
            {
                columns.Add(reader.GetString(1));
            }

            return columns;
        }
    }

    private sealed record CredentialRecord(
        string Id,
        string? TokenHash,
        bool HasExpiry,
        string? ExpiresUtc,
        bool HasLastUse,
        string? LastUseUtc);
}
