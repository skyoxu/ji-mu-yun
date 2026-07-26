using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class HostedContextManifestIssuerTests
{
    [Fact]
    public async Task IssueAsync_ShouldPersistSignedSingleUseEnvelope()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);
        var validator = new HostedContextManifestValidator(store, signer);

        var envelope = await issuer.IssueAsync(new HostedContextManifestIssue(
            "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", TimeSpan.FromMinutes(5)));

        envelope.SignatureKeyId.Should().Be("key-1");
        DateTimeOffset.Parse(envelope.ExpiresUtc!).Should().BeAfter(DateTimeOffset.UtcNow);
        (await validator.ValidateAndConsumeAsync(envelope, "llm:operation-1")).Should().BeTrue();
        (await validator.ValidateAndConsumeAsync(envelope, "llm:operation-1")).Should().BeFalse();
    }

    [Fact]
    public async Task IssueAsync_ShouldRejectLifetimeOutsideServerLimit()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(new PhaseAMetadataStore(database.ConnectionString, options), signer);

        var act = () => issuer.IssueAsync(new HostedContextManifestIssue(
            "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", TimeSpan.FromMinutes(16)));

        await act.Should().ThrowAsync<ArgumentOutOfRangeException>();
    }

    [Fact]
    public async Task Validator_ShouldConsumeIssuedNonceExactlyOnceUnderConcurrency()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);
        var validator = new HostedContextManifestValidator(store, signer);
        var envelope = await issuer.IssueAsync(new HostedContextManifestIssue(
            "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", TimeSpan.FromMinutes(5)));

        var results = await Task.WhenAll(Enumerable.Range(0, 16)
            .Select(_ => validator.ValidateAndConsumeAsync(envelope, "llm:operation-1")));

        results.Count(result => result).Should().Be(1);
    }

    [Fact]
    public async Task Validator_ShouldRejectExpiredSignedEnvelope()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var now = DateTimeOffset.UtcNow;
        var record = signer.Sign(new HostedContextManifestRecord(
            "manifest-expired", "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", "", "", "nonce-expired",
            now.AddMinutes(-1).ToString("O"), now.AddMinutes(-6).ToString("O")));
        var validator = new HostedContextManifestValidator(store, signer);
        var envelope = new PhaseA.Platform.Llm.HostedContextEnvelope(
            record.ManifestId, record.SnapshotId, record.PolicyRevision, record.Signature,
            SignatureKeyId: record.KeyId, AccountId: record.AccountId, ProjectId: record.ProjectId, OperationKey: record.OperationKey,
            Nonce: record.Nonce, ExpiresUtc: record.ExpiresUtc, CreatedUtc: record.CreatedUtc);

        (await store.SaveHostedContextManifestAsync(record)).Should().BeTrue();
        (await validator.ValidateAndConsumeAsync(envelope, record.OperationKey)).Should().BeFalse();
    }
}
