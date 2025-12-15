from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader
from rapidfuzz import fuzz

log = logging.getLogger(__name__)

STATUTE_PATTERNS = [
    (re.compile(r"\b35\s+U\.?S\.?C\.?\s*§?\s*102\b", re.IGNORECASE), "102"),
    (re.compile(r"\b35\s+U\.?S\.?C\.?\s*§?\s*103\b", re.IGNORECASE), "103"),
    (re.compile(r"\b35\s+U\.?S\.?C\.?\s*§?\s*112\b", re.IGNORECASE), "112"),
]


@dataclass
class ParsedDecision:
    text: str
    statute_basis: List[str]
    token_count: int


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            log.warning("PDF 추출 실패 page=%s err=%s", page, exc)
    return "\n".join(texts)


def detect_statutes(text: str) -> List[str]:
    found: List[str] = []
    for pattern, label in STATUTE_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found


def fuzzy_claims(text: str) -> List[str]:
    claims = []
    claim_match = re.findall(r"claim[s]?\s+(\d+(?:-\d+)?)\s+unpatentable", text, flags=re.IGNORECASE)
    for c in claim_match:
        claims.append(c)
    # 보정: "all challenged claims" 등 표현을 감지하면 ALL 표시
    if any(fuzz.partial_ratio(line.lower(), "all challenged claims") > 80 for line in text.splitlines()):
        claims.append("ALL_CHALLENGED")
    return list(dict.fromkeys(claims))  # 중복 제거


def parse_decision(path: Path) -> ParsedDecision:
    text = extract_text_from_pdf(path)
    statutes = detect_statutes(text)
    claims = fuzzy_claims(text)
    tokens = len(text.split())
    if claims:
        statutes = statutes or ["103"]  # 클레임 언급만 있을 경우 기본값 가정
    return ParsedDecision(text=text, statute_basis=statutes, token_count=tokens)

