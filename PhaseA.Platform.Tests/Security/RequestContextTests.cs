using FluentAssertions;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.PhaseB;

public sealed class IdentityContextTests
{
    [Fact]
    public void FromIdentity_PreservesServerOwnedIdentityAndRole()
    {
        var identity = new AccountIdentity("account-1", "owner", PhaseAAuth.UserRole);

        var context = RequestContext.FromIdentity(identity, "principal-1", "credential-1", "correlation-1");

        context.PrincipalId.Should().Be("principal-1");
        context.AccountId.Should().Be("account-1");
        context.Roles.Should().ContainSingle().Which.Should().Be(PhaseAAuth.UserRole);
        context.CredentialId.Should().Be("credential-1");
        context.CorrelationId.Should().Be("correlation-1");
        context.IsAdmin.Should().BeFalse();
    }

    [Fact]
    public void FromIdentity_DoesNotTrustAClientAccountValue()
    {
        var identity = new AccountIdentity("server-account", "owner", PhaseAAuth.UserRole);

        var context = RequestContext.FromIdentity(identity, "principal-1", "credential-1", "correlation-1");

        context.AccountId.Should().Be("server-account");
    }
}
