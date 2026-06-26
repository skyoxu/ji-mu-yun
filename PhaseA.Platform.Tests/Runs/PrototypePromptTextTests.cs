using FluentAssertions;
using PhaseA.Platform.Runs;
using Xunit;

namespace PhaseA.Platform.Tests.Runs;

public sealed class PrototypePromptTextTests
{
    [Theory]
    [InlineData(1)]
    [InlineData(5)]
    [InlineData(20)]
    [InlineData(80)]
    public void TrimHeadAndTail_ShouldNeverExceedMaxLength(int maxLength)
    {
        var text = string.Concat(Enumerable.Repeat("0123456789", 50));

        var result = PrototypePromptText.TrimHeadAndTail(text, maxLength);

        result.Length.Should().BeLessThanOrEqualTo(maxLength);
    }

    [Fact]
    public void TrimHeadAndTail_ShouldKeepHeadAndTail_WhenLimitAllowsMarker()
    {
        var text = "HEAD-" + string.Concat(Enumerable.Repeat("middle-", 40)) + "TAIL";

        var result = PrototypePromptText.TrimHeadAndTail(text, 80);

        result.Should().StartWith("HEAD-");
        result.Should().Contain("[truncated ");
        result.Should().EndWith("TAIL");
        result.Length.Should().BeLessThanOrEqualTo(80);
    }

    [Fact]
    public void TrimHeadAndTail_ShouldLimitEmptyValue()
    {
        var result = PrototypePromptText.TrimHeadAndTail("", 5, "EMPTY_VALUE");

        result.Should().Be("EMPTY");
    }

    [Fact]
    public void TrimHeadAndTail_ShouldReturnEmpty_WhenMaxLengthIsZero()
    {
        var result = PrototypePromptText.TrimHeadAndTail("", 0, "EMPTY_VALUE");

        result.Should().BeEmpty();
    }
}
