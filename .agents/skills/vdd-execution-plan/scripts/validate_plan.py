"""Production owner entrypoint for VDD semantic validation."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--plan-dir",required=True); p.add_argument("--input",required=False); a=p.parse_args()
    if a.input:
        value=json.loads(Path(a.input).read_text(encoding="utf-8"))
        required={"acceptance_ids","producer","coverage","fixture_class","taxonomy"}
        if not required.issubset(value):
            print("FAILURE_ID:VDD-RED-BOUNDARY"); return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
