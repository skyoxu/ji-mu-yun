using PhaseA.Platform.Workflow;
using Xunit;
namespace PhaseA.Platform.Tests.PhaseB.Repair;
public sealed class S45BoundaryTests
{
 [Fact] public void O_F7E24EE2DFB2(){var raw="operation correlation=s45 C:\\host private\\evidence.json";var retained=SecretRedactionPolicy.RedactForPersistence(raw);if(retained.Contains("host private",StringComparison.OrdinalIgnoreCase))throw new Xunit.Sdk.XunitException("FAILURE-O-F7E24EE2DFB2: raw host path retained");}
}
