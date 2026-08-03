using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class HostedContextManifestStoreTests
{
    [Fact]
    public async Task NonceConsumption_ShouldBeScopedAndSingleUse()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var now = DateTimeOffset.UtcNow;
        var record = new HostedContextManifestRecord(
            "manifest-1", "account-1", "project-1", "llm:draft-analysis", "snapshot-1", "policy-1", "key-1", "signature-1", "nonce-1",
            now.AddMinutes(5).ToString("O"), now.ToString("O"));

        (await store.SaveHostedContextManifestAsync(record)).Should().BeTrue();
        (await store.TryConsumeHostedContextNonceAsync("manifest-1", "account-2", "project-1", "llm:draft-analysis", "nonce-1")).Should().BeFalse();
        (await store.TryConsumeHostedContextNonceAsync("manifest-1", "account-1", "project-2", "llm:draft-analysis", "nonce-1")).Should().BeFalse();
        (await store.TryConsumeHostedContextNonceAsync("manifest-1", "account-1", "project-1", "llm:draft-analysis", "nonce-1")).Should().BeTrue();
        (await store.TryConsumeHostedContextNonceAsync("manifest-1", "account-1", "project-1", "llm:draft-analysis", "nonce-1")).Should().BeFalse();
    }

    [Fact]
    public async Task ValidateAndConsume_ShouldRequireExactPersistedManifestBeforeUsingNonce()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var now = DateTimeOffset.UtcNow;
        var record = new HostedContextManifestRecord(
            "manifest-2", "account-1", "project-1", "llm:draft-analysis", "snapshot-1", "policy-1", "key-1", "signature-1", "nonce-2",
            now.AddMinutes(5).ToString("O"), now.ToString("O"));

        (await store.SaveHostedContextManifestAsync(record)).Should().BeTrue();

        var changedSignature = record with { Signature = "signature-2" };
        (await store.ValidateAndConsumeHostedContextAsync(changedSignature)).Should().BeFalse();
        (await store.ValidateAndConsumeHostedContextAsync(record with { SnapshotId = "snapshot-2" })).Should().BeFalse();
        (await store.ValidateAndConsumeHostedContextAsync(record with { PolicyRevision = "policy-2" })).Should().BeFalse();

        (await store.ValidateAndConsumeHostedContextAsync(record)).Should().BeTrue();
        (await store.ValidateAndConsumeHostedContextAsync(record)).Should().BeFalse();
    }

    [Fact]
    public async Task ManifestValidator_ShouldBindEnvelopeOperationBeforeConsumingNonce()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var now = DateTimeOffset.UtcNow;
        var record = new HostedContextManifestRecord(
            "manifest-3", "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", "key-1", "", "nonce-3",
            now.AddMinutes(5).ToString("O"), now.ToString("O"));
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        record = signer.Sign(record);
        var validator = new HostedContextManifestValidator(store, signer);
        var envelope = new HostedContextEnvelope(
            record.ManifestId, record.SnapshotId, record.PolicyRevision, record.Signature,
            SignatureKeyId: record.KeyId, AccountId: record.AccountId, ProjectId: record.ProjectId, OperationKey: record.OperationKey, Nonce: record.Nonce,
            ExpiresUtc: record.ExpiresUtc, CreatedUtc: record.CreatedUtc);

        (await store.SaveHostedContextManifestAsync(record)).Should().BeTrue();
        (await validator.ValidateAndConsumeAsync(envelope, "llm:operation-2")).Should().BeFalse();
        (await validator.ValidateAndConsumeAsync(envelope with { Signature = "tampered" }, record.OperationKey)).Should().BeFalse();
        (await validator.ValidateAndConsumeAsync(envelope, record.OperationKey)).Should().BeTrue();
        (await validator.ValidateAndConsumeAsync(envelope, record.OperationKey)).Should().BeFalse();
    }
}
