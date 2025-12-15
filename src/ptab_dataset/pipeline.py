from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Dict, List

from rich import print  # noqa: T201
from tqdm import trange

from .api import PTABClient
from .config import Settings
from .downloader import DecisionDownloader
from .parser import parse_decision
from .storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)


def run_pipeline(
    *,
    since: str,
    until: str | None,
    max_pages: int,
    rows: int,
    dry_run: bool,
    override_api_key: str | None,
) -> None:
    settings = Settings.from_env(override_api_key=override_api_key)
    storage = Storage(settings)
    client = PTABClient(settings)
    downloader = DecisionDownloader(settings)

    start_page = storage.load_checkpoint() + 1
    retry_queue: List[Dict] = []

    for page in trange(start_page, start_page + max_pages, desc="pages"):
        resp = client.search_decisions(since=since, until=until, page=page, rows=rows)
        docs = resp.get("results", [])
        if not docs:
            log.info("더 이상 결과가 없습니다. page=%s", page)
            break

        decision_urls = []
        for doc in docs:
            bag = doc.get("patentTrialDocumentDataBag", [])
            for item in bag:
                if item.get("documentTypeDescriptionText") == "Final Written Decision":
                    decision_urls.append(item.get("documentLinkText"))
                    break

        if dry_run:
            log.info("page=%s decisions=%s (dry-run)", page, len(decision_urls))
            storage.save_checkpoint(page)
            continue

        downloaded = downloader.batch_download(decision_urls)
        processed_records = []
        for dl in downloaded:
            try:
                file_path = downloader.persist(dl, ext=".pdf")
                parsed = parse_decision(file_path)
                processed_records.append(
                    {
                        "url": dl["url"],
                        "sha256": dl["sha256"],
                        "statute_basis": parsed.statute_basis,
                        "token_count": parsed.token_count,
                        "text": parsed.text,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("파싱 실패 url=%s err=%s", dl["url"], exc)
                retry_queue.append({"url": dl["url"], "reason": str(exc)})

        out_path = Path(settings.processed_dir) / f"decisions_page_{page}.jsonl"
        storage.save_jsonl(processed_records, out_path)
        storage.save_checkpoint(page)

    if retry_queue:
        storage.save_retry_queue(retry_queue)
        print(f"[yellow]재시도 큐 {len(retry_queue)}건이 기록되었습니다.[/yellow]")
    print("[green]파이프라인이 완료되었습니다.[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="PTAB 무효 심판 데이터셋 구축 파이프라인")
    parser.add_argument("--since", required=True, help="YYYY-MM-DD 형식의 시작일")
    parser.add_argument("--until", help="YYYY-MM-DD 형식의 종료일")
    parser.add_argument("--max-pages", type=int, default=1, help="조회할 최대 페이지 수")
    parser.add_argument("--rows", type=int, default=100, help="페이지당 행 수")
    parser.add_argument("--dry-run", action="store_true", help="다운로드/저장을 수행하지 않고 요약만 출력")
    parser.add_argument("--api-key", help="USPTO API 키(환경 변수 대신 인자로 주입)")
    args = parser.parse_args()

    run_pipeline(
        since=args.since,
        until=args.until,
        max_pages=args.max_pages,
        rows=args.rows,
        dry_run=args.dry_run,
        override_api_key=args.api_key,
    )


if __name__ == "__main__":
    main()

