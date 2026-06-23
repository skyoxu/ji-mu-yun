from scripts.python import smoke_headless


def test_compact_build_failure_excerpt_keeps_csharp_error_details():
    stdout = """
    Determining projects to restore...
    Build FAILED.
    """
    stderr = r"""
    C:\test\Towerdemo-v0.1\Game.Core\Prototypes\TowerdemoPrototypeLoop.cs(275,17): error CS7036: There is no argument given that corresponds to the required parameter 'HealAmount'
    Some unrelated warning line.
    """

    excerpt = smoke_headless._compact_build_failure_excerpt(stdout, stderr)

    assert "CS7036" in excerpt
    assert "TowerdemoPrototypeLoop.cs(275,17)" in excerpt
    assert "HealAmount" in excerpt
