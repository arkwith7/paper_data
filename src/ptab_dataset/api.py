from __future__ import annotations

import logging
import json
from typing import Any, Dict, Iterable, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings

log = logging.getLogger(__name__)


class PTABClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-KEY": self.settings.api_key,
                "Accept": "application/json",
                "User-Agent": self.settings.user_agent,
            }
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(5))
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.settings.base_url}/{path.lstrip('/')}"
        resp = self.session.get(
            url,
            params=params,
            timeout=self.settings.timeout,
            verify=self.settings.verify_tls,
        )
        if resp.status_code >= 400:
            log.warning("API 오류 status=%s url=%s body=%s", resp.status_code, url, resp.text[:500])
        resp.raise_for_status()
        return resp.json()

    def search_decisions(
        self,
        *,
        since: Optional[str] = None,
        until: Optional[str] = None,
        page: int = 1,
        rows: int = 100,
        extra_filters: Optional[Iterable[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        filters = [
            {"fieldName": "decisionTypeCategory", "fieldValue": "Final Written Decision"},
            {"fieldName": "trialStatus", "fieldValue": "Final Written Decision"},
            {"fieldName": "trialStatus", "fieldValue": "Terminated"},
            {"fieldName": "subdecisionTypeCategory", "fieldValue": "Unpatentable"},
            {"fieldName": "subdecisionTypeCategory", "fieldValue": "Claims Unpatentable"},
            {"fieldName": "prosecutionStatus", "fieldValue": "Certificate Issued"},
        ]
        if since:
            filters.append({"fieldName": "decisionDate", "fieldValue": f"[{since} TO *]"})
        if until:
            filters.append({"fieldName": "decisionDate", "fieldValue": f"[* TO {until}]"})
        if extra_filters:
            filters.extend(extra_filters)

        params = {
            # requests는 list/dict를 쿼리스트링으로 보낼 때 반복 파라미터로 인코딩할 수 있어
            # API가 기대하는 JSON 문자열 형식으로 명시적으로 직렬화합니다.
            "filters": json.dumps(filters, ensure_ascii=False),
            "page": page,
            "rows": rows,
        }
        return self.get("search-decisions", params=params)

