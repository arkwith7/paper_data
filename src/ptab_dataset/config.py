from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    api_key: str
    base_url: str = "https://data.uspto.gov/apis/ptab-trials"
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
        return cls(api_key=api_key)

