"""Inspect persisted Chroma chunks and embeddings from the terminal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from retrieval.retrievers import ChromaVectorStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local Chroma chunks for NW Copilot.")
    parser.add_argument(
        "--path",
        default="/tmp/nw_copilot_ui/chroma",
        help="Directory where the Chroma PersistentClient stores data.",
    )
    parser.add_argument(
        "--collection",
        default="nw_copilot_chunks",
        help="Chroma collection name to inspect.",
    )
    parser.add_argument("--limit", type=int, default=10, help="Number of records to return.")
    parser.add_argument("--offset", type=int, default=0, help="Number of records to skip.")
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Include full embedding vectors in the output.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    store = ChromaVectorStore(
        persist_directory=args.path,
        collection_name=args.collection,
    )
    payload = store.peek_records(
        limit=max(1, args.limit),
        offset=max(0, args.offset),
        include_embeddings=args.include_embeddings,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
