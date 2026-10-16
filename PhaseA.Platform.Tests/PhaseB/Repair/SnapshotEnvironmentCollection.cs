using Xunit;

namespace PhaseA.Platform.Tests.PhaseB.Repair;

// ADR-0061: process-wide snapshot configuration must not change under other tests.
[CollectionDefinition("PhaseA snapshot environment", DisableParallelization = true)]
public sealed class SnapshotEnvironmentCollection
{
}
