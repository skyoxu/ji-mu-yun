from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_s0_result_publishes_bundle_owned_authority_projection(tmp_path: Path) -> None:
    import json
    import acceptance_cli
    from acceptance_core import canonical_hash

    binding = "sha256:" + "0" * 64
    bundle = {"schemaVersion": "compact-vdd-acceptance-prerequisite-bundle.v1", "candidateBindingHash": binding}
    bundle["bundleHash"] = canonical_hash(bundle)
    request = {"schemaVersion": "acceptance-coordinator-request.v2", "candidateBindingHash": binding, "bundle": bundle, "evidence": {"candidateBindingHash": binding, "deterministicSourceSufficient": True, "semanticReviewRequired": False}, "authorizes": []}
    source, output = tmp_path / "request.json", tmp_path / "result.json"
    source.write_text(json.dumps(request), encoding="utf-8")
    result = acceptance_cli.run_coordinator(str(source), str(output))
    assert result["authority"]["bundlePath"] == "bundle/compact-vdd-acceptance-prerequisite-bundle.v1.json"
