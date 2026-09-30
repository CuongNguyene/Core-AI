#!/usr/bin/env python3
"""Export unresolved locator claims for human semantic grounding review."""

import argparse
import json
from pathlib import Path

from app.extraction.review_queue import build_semantic_grounding_review_queue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(corpus, dict) or not isinstance(manifest, list):
        raise SystemExit("corpus must be an object and manifest must be an array")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            build_semantic_grounding_review_queue(corpus, manifest),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
