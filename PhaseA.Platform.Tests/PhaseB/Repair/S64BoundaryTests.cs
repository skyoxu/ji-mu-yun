using PhaseA.Platform.Security;
using Xunit;
namespace PhaseA.Platform.Tests.PhaseB.Repair;
public sealed class S64BoundaryTests
{
 [Fact] public void O_E7279108688A(){var c=RequestContext.FromIdentity(new AccountIdentity("s64-account","s64-owner",PhaseAAuth.UserRole),"s64-principal","s64-credential","s64-correlation");if(c.AccountId!="s64-account"||c.PrincipalId!="s64-principal"||c.CorrelationId!="s64-correlation")throw new Xunit.Sdk.XunitException("FAILURE-O-E7279108688A: identity event fields were not retained");}
}
