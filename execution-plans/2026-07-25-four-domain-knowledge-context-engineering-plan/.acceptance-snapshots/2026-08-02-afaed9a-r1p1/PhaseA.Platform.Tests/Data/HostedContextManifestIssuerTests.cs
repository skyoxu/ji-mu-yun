using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using System.Text.Json;
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
        var (accountId, projectId) = await CreateProjectAsync(store);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);
        var validator = new HostedContextManifestValidator(store, signer);

        var envelope = await issuer.IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "llm:project-chat", new string('1', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt"));

        envelope.SignatureKeyId.Should().Be("key-1");
        envelope.SchemaVersion.Should().Be(HostedContextSignedPayloadV1.Schema);
        envelope.SignedPayloadSha256.Should().MatchRegex("^[0-9a-f]{64}$");
        DateTimeOffset.Parse(envelope.ExpiresUtc!).Should().BeAfter(DateTimeOffset.UtcNow);
        (await validator.ValidateAndConsumeAsync(envelope, "llm:project-chat")).Should().BeTrue();
        (await validator.ValidateAndConsumeAsync(envelope, "llm:project-chat")).Should().BeFalse();
    }

    [Fact]
    public async Task IssueAsync_ShouldBindServerProjectAuthorityWithoutSyntheticEvidence()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        }));
        var (accountId, projectId) = await CreateProjectAsync(store);
        var project = await store.GetProjectSnapshotAsync(projectId);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var envelope = await new HostedContextManifestIssuer(store, signer).IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "codex:prototype-quick-fix", new string('2', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt",
            RunId: "run-1", Sandbox: "workspace-write", AllowedWritePaths: [project!.RepoPath],
            OutputTargets: [Path.Combine(project.RepoPath, "output", "result.json")]));

        var record = await store.GetHostedContextManifestAsync(envelope.ManifestId);
        record.Should().NotBeNull();
        record!.SignedPayloadJson.Should().NotContain("hosted-context://");
        using var document = JsonDocument.Parse(record.SignedPayloadJson!);
        var root = document.RootElement;
        root.GetProperty("workspace_id").GetString().Should().Be(project.WorkspaceId);
        root.GetProperty("allowed_write_paths")[0].GetString().Should().Be("project://");
        root.GetProperty("output_targets")[0].GetString().Should().Be("project://output/result.json");
        root.GetProperty("hosted_route_contracts").EnumerateObject().Select(item => item.Name).Should().BeEquivalentTo(
            ["mode", "applicability_policy_revision", "reason_code"]);
        root.GetProperty("allowed_read_artifact_manifest_sha256").GetString().Should().MatchRegex("^[0-9a-f]{64}$");
        root.GetProperty("context_assembly_result_sha256").GetString().Should().MatchRegex("^[0-9a-f]{64}$");
    }

    [Fact]
    public async Task IssueAsync_ShouldRejectUnknownRouteCrossAccountAndEscapingPath()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        }));
        var (accountId, projectId) = await CreateProjectAsync(store);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);

        Func<Task> unknownRoute = () => issuer.IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "llm:unregistered", new string('3', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt"));
        Func<Task> crossAccount = () => issuer.IssueAsync(new HostedContextManifestIssue(
            "another-account", projectId, "llm:project-chat", new string('3', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt"));
        Func<Task> escapingPath = () => issuer.IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "codex:prototype-quick-fix", new string('3', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt",
            Sandbox: "workspace-write", AllowedWritePaths: [Path.GetTempPath()]));

        await unknownRoute.Should().ThrowAsync<InvalidOperationException>();
        await crossAccount.Should().ThrowAsync<InvalidOperationException>();
        await escapingPath.Should().ThrowAsync<ArgumentException>();
    }

    [Fact]
    public async Task Validator_ShouldRejectClientPayloadIdentityDriftWithoutConsumingNonce()
    {
        using var database = TempSqliteDatabase.Create();
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["HOSTED_WORKSPACE_ROOT"] = Path.GetTempPath()
        });
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var (accountId, projectId) = await CreateProjectAsync(store);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);
        var validator = new HostedContextManifestValidator(store, signer);
        var envelope = await issuer.IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "llm:project-chat", new string('1', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt"));

        (await validator.ValidateAndConsumeAsync(
            envelope with { SignedPayloadSha256 = new string('0', 64) },
            "llm:project-chat")).Should().BeFalse();
        (await validator.ValidateAndConsumeAsync(envelope, "llm:project-chat")).Should().BeTrue();
    }

    [Fact]
    public async Task Validator_ShouldRejectLegacyCompactRecordForE2()
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
            "manifest-legacy", "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", "", "", "nonce-legacy",
            now.AddMinutes(5).ToString("O"), now.ToString("O")));
        (await store.SaveHostedContextManifestAsync(record)).Should().BeTrue();
        var envelope = new PhaseA.Platform.Llm.HostedContextEnvelope(
            record.ManifestId, record.SnapshotId, record.PolicyRevision, record.Signature,
            SignatureKeyId: record.KeyId, AccountId: record.AccountId, ProjectId: record.ProjectId,
            OperationKey: record.OperationKey, Nonce: record.Nonce, ExpiresUtc: record.ExpiresUtc, CreatedUtc: record.CreatedUtc);

        var validator = new HostedContextManifestValidator(store, signer);
        (await validator.ValidateAndConsumeAsync(envelope, record.OperationKey)).Should().BeFalse();
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
            "account-1", "project-1", "llm:operation-1", "snapshot-1", "policy-1", TimeSpan.FromMinutes(16), "prompt"));

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
        var (accountId, projectId) = await CreateProjectAsync(store);
        var signer = new HostedContextManifestSignatureService("key-1", new Dictionary<string, string>
        {
            ["key-1"] = "test-hosted-context-signing-secret"
        });
        var issuer = new HostedContextManifestIssuer(store, signer);
        var validator = new HostedContextManifestValidator(store, signer);
        var envelope = await issuer.IssueAsync(new HostedContextManifestIssue(
            accountId, projectId, "llm:project-chat", new string('1', 64), "policy-1", TimeSpan.FromMinutes(5), "prompt"));

        var results = await Task.WhenAll(Enumerable.Range(0, 16)
            .Select(_ => validator.ValidateAndConsumeAsync(envelope, "llm:project-chat")));

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

    private static async Task<(string AccountId, string ProjectId)> CreateProjectAsync(PhaseAMetadataStore store)
    {
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = Guid.NewGuid().ToString("N");
        var root = Path.Combine(Path.GetTempPath(), "hosted-context-tests", projectId);
        var result = await store.CreateProjectAsync(new ProjectCreationCommand(
            projectId,
            accountId,
            "Hosted Context Test",
            "Hosted Context Test",
            "test",
            "godot-prototype-default",
            false,
            ["test"],
            root,
            Path.Combine(root, "repo"),
            Path.Combine(root, "runtime"),
            Path.Combine(root, "meta")));
        result.Succeeded.Should().BeTrue();
        return (accountId, projectId);
    }
}
