using System.Net;
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Llm;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class AiCodeMirrorBillingClientTests
{
    [Fact]
    public async Task CaptureAsync_ReturnsDisabled_WhenNotConfigured()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        var client = new AiCodeMirrorBillingClient(new HttpClient(new FakeHandler()), options);

        var result = await client.CaptureAsync();

        result.Enabled.Should().BeFalse();
        result.FailureCode.Should().Be("billing_disabled");
    }

    [Fact]
    public async Task CaptureAsync_ReadsWalletAndSelectedApiKeyConsumption()
    {
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["AICODEMIRROR_BILLING_ENABLED"] = "true",
            ["AICODEMIRROR_BASE_URL"] = "https://www.aicodemirror.com",
            ["AICODEMIRROR_COOKIE"] = "session=test",
            ["AICODEMIRROR_API_KEY_NAME"] = "phase-a"
        });
        var handler = new FakeHandler
        {
            WalletJson = """{"data":{"balance":123450,"bonusBalance":6000}}""",
            ApiKeysJson = """{"data":{"list":[{"name":"other","totalConsumed":1000},{"name":"phase-a","totalConsumed":23450}]}}"""
        };
        var client = new AiCodeMirrorBillingClient(new HttpClient(handler), options);

        var result = await client.CaptureAsync();

        result.Enabled.Should().BeTrue();
        result.Status.Should().Be("ok");
        result.WalletBalanceCny.Should().Be(123.45m);
        result.WalletBonusBalanceCny.Should().Be(6.00m);
        result.ApiKeyName.Should().Be("phase-a");
        result.RawApiKeyTotalConsumed.Should().Be(23450);
        result.ApiKeyTotalConsumedCny.Should().Be(23.45m);
        handler.LastCookie.Should().Be("session=test");
    }

    private sealed class FakeHandler : HttpMessageHandler
    {
        public string WalletJson { get; init; } = "{}";
        public string ApiKeysJson { get; init; } = "{}";
        public string? LastCookie { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            LastCookie = request.Headers.TryGetValues("Cookie", out var values) ? values.SingleOrDefault() : null;
            var json = request.RequestUri?.AbsolutePath switch
            {
                "/api/wallet" => WalletJson,
                "/api/apikeys" => ApiKeysJson,
                _ => "{}"
            };
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json)
            });
        }
    }
}
