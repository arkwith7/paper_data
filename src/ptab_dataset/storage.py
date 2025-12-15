from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

from .config import Settings


class Storage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Path(settings.raw_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.processed_dir).mkdir(parents=True, exist_ok=True)

    def save_jsonl(self, records: Iterable[Dict], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def save_checkpoint(self, page: int) -> None:
        ckpt = Path(self.settings.processed_dir) / "checkpoint.json"
        ckpt.write_text(json.dumps({"last_page": page}), encoding="utf-8")

    def load_checkpoint(self) -> int:
        ckpt = Path(self.settings.processed_dir) / "checkpoint.json"
        if ckpt.exists():
            return json.loads(ckpt.read_text(encoding="utf-8")).get("last_page", 0)
        return 0

    def save_retry_queue(self, items: List[Dict]) -> None:
        path = Path(self.settings.raw_dir) / "retry_queue.jsonl"
        self.save_jsonl(items, path)

