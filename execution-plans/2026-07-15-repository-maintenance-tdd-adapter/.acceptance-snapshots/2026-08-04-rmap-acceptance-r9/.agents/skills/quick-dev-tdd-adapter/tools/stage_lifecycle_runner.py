from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from stage_observation_runner import freeze, record_observation, run
from stage_artifact_composer import compose
from adapter import persist_protocol_bundle


class LifecycleRunner:
    """Caller-owned, append-only capture state for one future TDD lifecycle."""

    def __init__(self, workspace: Path, run_dir: Path, paths: list[str]) -> None:
        self.workspace = workspace
        self.run_dir = run_dir
        self.paths = list(paths)
        self.snapshots = freeze(workspace, paths)
        self.stages: list[str] = []

    def observe(self, stage: str, command: dict[str, Any], summary: str) -> dict[str, Any]:
        expected = ("red", "green", "refactor")
        if stage not in expected or self.stages != list(expected[:len(self.stages)]):
            raise ValueError("lifecycle stage order is invalid")
        if stage != expected[len(self.stages)]:
            raise ValueError("lifecycle stage is not next")
        observation = run(self.workspace, stage, command, self.paths, summary, before_snapshots=self.snapshots)
        record_observation(self.run_dir, observation)
        self.snapshots = {item["path"]: item["after_bytes_base64"] for item in observation["changed_files"]}
        self.stages.append(stage)
        return observation

    def close(self, run_context: dict[str, Any], artifact_store: dict[tuple[str, str], bytes]) -> dict[str, Any]:
        """Close only a complete captured lifecycle; no stage is synthesized here."""
        if self.stages != ["red", "green", "refactor"]:
            raise ValueError("complete RED/GREEN/REFACTOR observations are required")
        observations = []
        for stage in self.stages:
            path = self.run_dir / "observations" / f"{stage}-observed.json"
            import json
            observations.append(json.loads(path.read_text(encoding="utf-8")))
        bundle, store, _ = compose(run_context, observations, artifact_store)
        persist_protocol_bundle(self.run_dir, bundle, store)
        return bundle
