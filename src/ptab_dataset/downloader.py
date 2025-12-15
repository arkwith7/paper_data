from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings

log = logging.getLogger(__name__)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DecisionDownloader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})
        Path(settings.raw_dir).mkdir(parents=True, exist_ok=True)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(5))
    def download_one(self, url: str) -> Dict[str, str]:
        resp = self.session.get(url, timeout=self.settings.timeout, verify=self.settings.verify_tls)
        resp.raise_for_status()
        content = resp.content
        digest = sha256_bytes(content)
        return {"url": url, "sha256": digest, "content": content}

    def batch_download(self, urls: Iterable[str]) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as ex:
            future_map = {ex.submit(self.download_one, url): url for url in urls}
            for fut in as_completed(future_map):
                url = future_map[fut]
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    log.warning("다운로드 실패 url=%s err=%s", url, exc)
        return results

    def persist(self, item: Dict[str, str], *, ext: str = ".pdf") -> Path:
        digest = item["sha256"]
        path = Path(self.settings.raw_dir) / f"{digest}{ext}"
        if not path.exists():
            path.write_bytes(item["content"])
        return path

