namespace PhaseA.Platform.Configuration;

public sealed class PhaseAPlatformConfigException : InvalidOperationException
{
    public PhaseAPlatformConfigException(string message)
        : base(message)
    {
    }
}
