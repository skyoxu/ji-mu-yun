using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class LlmBindingServiceTests
{
    [Fact]
    public async Task BindAsync_StoresManualNewApiBindingWithoutProviderKey()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new LlmBindingService(store, options);

        var result = await service.BindAsync(accountId, new LlmBindingRequest(
            GatewayProvider: "new-api",
            GatewayBaseUrl: "https://new-api.example.com/v1",
            ExternalAccountRef: "new-api-user-1",
            TokenRef: "host-secret:new-api-user-1"));

        result.Succeeded.Should().BeTrue();
        result.Binding!.GatewayProvider.Should().Be("new-api");
        result.Binding.TokenRef.Should().Be("host-secret:new-api-user-1");
    }

    [Theory]
    [InlineData("sk-provider")]
    public async Task BindAsync_RejectsUpstreamProviderKeyStorage(string providerKey)
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new LlmBindingService(store, options);

        var result = await service.BindAsync(accountId, new LlmBindingRequest(
            GatewayProvider: "new-api",
            GatewayBaseUrl: "https://new-api.example.com/v1",
            ExternalAccountRef: "new-api-user-1",
            TokenRef: "host-secret:new-api-user-1",
            ProviderKey: providerKey));

        result.Succeeded.Should().BeFalse();
        result.FailureCode.Should().Be("provider_key_not_allowed");
        (await store.GetLlmBindingAsync(accountId)).Should().BeNull();
    }
}
