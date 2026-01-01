from __future__ import annotations

import json
from pathlib import Path

from ptab_dataset.chunking import chunk_repo_patent_txt


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    prior_art_dir = repo_root / "data" / "processed" / "fulltext" / "prior_arts"
    out_path = repo_root / "data" / "processed" / "fulltext" / "prior_art_chunks.jsonl"

    paths = sorted(prior_art_dir.glob("*.txt"))
    if not paths:
        raise SystemExit(f"No .txt files found in: {prior_art_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_docs = 0
    n_chunks = 0
    with out_path.open("w", encoding="utf-8") as f:
        for p in paths:
            chunks = chunk_repo_patent_txt(p)
            if not chunks:
                continue
            n_docs += 1
            for c in chunks:
                rec = {
                    "doc_id": c.doc_id,
                    "section": c.section,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "source_path": c.source_path,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_chunks += 1

    print(f"Wrote: {out_path}")
    print(f"Docs: {n_docs}")
    print(f"Chunks: {n_chunks}")


if __name__ == "__main__":
    main()
