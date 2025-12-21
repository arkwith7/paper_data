from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# 기본은 `.env`를 찾되, 이 프로젝트에서는 `env` 파일을 쓰는 경우가 많아 fallback을 둡니다.
if not load_dotenv():
    load_dotenv("env")


@dataclass
class Settings:
    api_key: str
    base_url: str = "https://data.uspto.gov/apis/ptab-trials"
    patentsview_api_key: str = ""
    patentsview_base_url: str = "https://search.patentsview.org/api/v1"
    user_agent: str = "ptab-dataset-builder/0.1"
    data_dir: str = "data"
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    timeout: int = 30
    max_workers: int = 4
    verify_tls: bool = True

    @classmethod
    def from_env(cls, *, override_api_key: Optional[str] = None) -> "Settings":
        api_key = override_api_key or os.getenv("USPTO_API_KEY", "")
        if not api_key:
            raise ValueError("환경 변수 USPTO_API_KEY가 설정되지 않았습니다.")
        return cls(
            api_key=api_key,
            patentsview_api_key=os.getenv("PATENTSVIEW_API_KEY", ""),
            patentsview_base_url=os.getenv("PATENTSVIEW_BASE_URL", "https://search.patentsview.org/api/v1"),
        )

