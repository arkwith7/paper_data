from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import Settings

log = logging.getLogger(__name__)


class PatentsViewClient:
    """
    PatentsView PatentSearch API (선택 기능)

    - PTAB(USPTO ODP) 수집에는 필요 없으며, 추후 prior art/특허 메타데이터 보강을 위해 사용합니다.
    - 키는 Settings.patentsview_api_key (환경 변수 PATENTSVIEW_API_KEY)로 주입합니다.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": self.settings.user_agent,
            }
        )
        if self.settings.patentsview_api_key:
            # 실제 헤더 키 이름은 PatentsView 문서에 따라 달라질 수 있어,
            # 기본은 Authorization Bearer로 두고 필요 시 변경하도록 합니다.
            self.session.headers.update({"Authorization": f"Bearer {self.settings.patentsview_api_key}"})

    @retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(5))
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.settings.patentsview_base_url:
            raise ValueError("patentsview_base_url이 비어 있습니다.")
        url = f"{self.settings.patentsview_base_url.rstrip('/')}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=self.settings.timeout, verify=self.settings.verify_tls)
        if resp.status_code >= 400:
            log.warning("PatentsView API 오류 status=%s url=%s body=%s", resp.status_code, url, resp.text[:500])
        resp.raise_for_status()
        return resp.json()

    def health(self) -> Dict[str, Any]:
        """
        간단 연결 테스트용(엔드포인트는 실제 운영에 맞춰 조정 가능).
        """
        return self.get("health")

