using PhaseA.Platform.Data;

namespace PhaseA.Platform.Llm;

public sealed record LlmBindingResult(
    bool Succeeded,
    string? FailureCode,
    LlmBindingSnapshot? Binding)
{
    public static LlmBindingResult Ok(LlmBindingSnapshot binding)
    {
        return new LlmBindingResult(true, null, binding);
    }

    public static LlmBindingResult Failure(string failureCode)
    {
        return new LlmBindingResult(false, failureCode, null);
    }
}
