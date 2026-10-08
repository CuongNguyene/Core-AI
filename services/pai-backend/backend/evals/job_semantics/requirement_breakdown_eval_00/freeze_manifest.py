"""Create or verify the local synthetic corpus freeze manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from evals.job_semantics.requirement_breakdown_eval_00.validate_and_freeze import (
    build_freeze_manifest,
    verify_freeze_manifest,
)

EVAL_DIR = Path(__file__).parent
MANIFEST_PATH = EVAL_DIR / "manifest.synthetic.v1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify", action="store_true", help="verify existing manifest without writing"
    )
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        print(json.dumps(verify_freeze_manifest(EVAL_DIR, manifest), sort_keys=True))
        return
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=EVAL_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = build_freeze_manifest(EVAL_DIR, code_head=head)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verify_freeze_manifest(EVAL_DIR, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
