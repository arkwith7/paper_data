from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    section: str
    chunk_index: int
    text: str
    source_path: Optional[str] = None


_SECTION_HEADER_RE = re.compile(r"^##\s+([A-Z0-9 ()_-]+)\s*$")


def parse_repo_txt(text: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parse repo TXT format into (header, sections).

    Header keys are best-effort extracted from the first block:
    - Document Number
    - Source
    - Title
    - KIPRIS Operation (optional)

    Sections are extracted by "## <NAME>" markers.
    """

    header: Dict[str, str] = {}
    sections: Dict[str, str] = {}

    lines = text.splitlines()

    # Header (until the separator line of '=' or until first section header)
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if line.strip().startswith("=="):
            i += 1
            break
        if line.startswith("## "):
            break
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k and v:
                header[k] = v
        i += 1

    # Sections
    current_name: Optional[str] = None
    current_buf: List[str] = []

    def flush() -> None:
        nonlocal current_name, current_buf
        if current_name is None:
            return
        content = "\n".join(current_buf).strip()
        sections[current_name] = content
        current_name = None
        current_buf = []

    for line in lines[i:]:
        m = _SECTION_HEADER_RE.match(line)
        if m:
            flush()
            current_name = m.group(1).strip()
            continue
        if current_name is not None:
            current_buf.append(line)

    flush()
    return header, sections


def guess_doc_lang(doc_id: str) -> str:
    up = str(doc_id).strip().upper()
    if up.startswith("JP"):
        return "ja"
    if up.startswith("CN"):
        return "zh"
    if up.startswith("KR"):
        return "ko"
    return "en"


def _normalize_whitespace_for_chunking(text: str) -> str:
    # Keep newlines, but collapse excessive blank lines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def add_subsection_markers(description: str, lang: str) -> str:
    """Best-effort: inject '### <HEADING>' markers inside DESCRIPTION.

    This does not guarantee perfect legal/official sectioning; it only aims to
    make chunk boundaries more meaningful for retrieval.

    Strategy:
    - If JP/CN have bracket headings (【...】), turn them into '### ...'.
    - For EN (and machine-translated CN pages), inject markers for common
      patent headings (FIELD, BACKGROUND, SUMMARY, etc.), even if they are
      concatenated without newlines.
    """

    text = _normalize_whitespace_for_chunking(description)

    if not text:
        return text

    # JP: 【発明の詳細な説明】, 【課題】, 【解決手段】, etc.
    if lang == "ja":
        text = re.sub(r"(^|\n)(【[^】]{1,60}】)", r"\n### \2\n", text)
        return text.strip()

    # CN: sometimes has 【技术领域】 etc; sometimes fully translated EN.
    if lang == "zh":
        text = re.sub(r"(^|\n)(【[^】]{1,60}】)", r"\n### \2\n", text)
        # Also handle translated headings that frequently appear without spacing.

    # EN headings (also apply to zh fallback because CN pages can be translated)
    # Insert markers even if the heading is glued to adjacent words.
    heading_patterns = [
        (r"CROSS[- ]REFERENCE TO RELATED APPLICATIONS", "CROSS-REFERENCE TO RELATED APPLICATIONS"),
        (r"FIELD OF THE INVENTION", "FIELD OF THE INVENTION"),
        (r"TECHNICAL FIELD", "TECHNICAL FIELD"),
        (r"BACKGROUND( OF THE (INVENTION|PRESENT INVENTION))?", "BACKGROUND"),
        (r"BACKGROUND TECHNOLOGY", "BACKGROUND TECHNOLOGY"),
        (r"SUMMARY( OF THE (INVENTION|PRESENT INVENTION))?", "SUMMARY"),
        (r"BRIEF DESCRIPTION OF THE DRAWINGS", "BRIEF DESCRIPTION OF THE DRAWINGS"),
        (r"DESCRIPTION OF THE DRAWINGS", "DESCRIPTION OF THE DRAWINGS"),
        (r"DETAILED DESCRIPTION( OF (THE )?INVENTION)?", "DETAILED DESCRIPTION"),
        (r"THE CONTENT OF THE INVENTION", "THE CONTENT OF THE INVENTION"),
        (r"DESCRIPTION OF EMBODIMENTS", "DESCRIPTION OF EMBODIMENTS"),
    ]

    for pat, label in heading_patterns:
        # If it's already a standalone heading line, don't duplicate.
        # Otherwise inject markers before the first occurrence.
        marker = f"\n### {label}\n"
        # Replace occurrences that are not already preceded by a newline+### marker.
        text = re.sub(
            rf"(?i)(?<!\n###\s)({pat})\b",
            lambda m: marker + m.group(0).strip(),
            text,
            count=1,
        )

    # Clean up accidental "Description" label duplication sometimes present.
    text = re.sub(r"^Description\s*", "", text, flags=re.IGNORECASE)

    return text.strip()


def iter_subsections(text: str) -> Iterator[Tuple[str, str]]:
    """Yield (subsection_title, subsection_text) from text with '###' markers.

    If no markers exist, yields a single ('BODY', text).
    """

    text = _normalize_whitespace_for_chunking(text)
    if not text:
        return

    parts = re.split(r"\n###\s+", "\n" + text)
    # parts[0] is before the first marker (maybe empty)
    if len(parts) == 1:
        yield "BODY", text
        return

    # parts like: ['', 'TITLE\ncontent...', 'TITLE2\ncontent...']
    first = parts[0].strip()
    if first:
        yield "BODY", first

    for part in parts[1:]:
        part = part.strip("\n")
        if not part:
            continue
        title, _, body = part.partition("\n")
        title = title.strip() or "SUBSECTION"
        body = body.strip()
        if body:
            yield title, body


def chunk_text(text: str, max_chars: int = 1400, overlap: int = 200) -> List[str]:
    """Simple char-based chunking with overlap.

    - Prefers splitting on paragraph boundaries.
    - Falls back to hard splits.
    """

    text = _normalize_whitespace_for_chunking(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks: List[str] = []
    buf = ""

    def push_buf() -> None:
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for p in paragraphs:
        if not buf:
            buf = p
            continue

        if len(buf) + 2 + len(p) <= max_chars:
            buf = buf + "\n\n" + p
        else:
            push_buf()
            buf = p

    push_buf()

    # Add overlap by prefixing each chunk with tail of previous
    if overlap > 0 and len(chunks) > 1:
        out: List[str] = [chunks[0]]
        for prev, cur in zip(chunks, chunks[1:]):
            tail = prev[-overlap:]
            out.append((tail + "\n\n" + cur).strip())
        chunks = out

    return chunks


def chunk_repo_patent_txt(path: Path, *, max_chars: int = 1400, overlap: int = 200) -> List[Chunk]:
    """Convert a saved TXT file into chunks, using inferred subsection markers."""

    raw = path.read_text(encoding="utf-8")
    header, sections = parse_repo_txt(raw)

    doc_id = header.get("Document Number") or path.stem
    lang = guess_doc_lang(doc_id)

    results: List[Chunk] = []

    for section_name, section_text in sections.items():
        section_text = _normalize_whitespace_for_chunking(section_text)
        if not section_text:
            continue

        if section_name == "DESCRIPTION":
            section_text = add_subsection_markers(section_text, lang)
            for sub_title, sub_body in iter_subsections(section_text):
                pieces = chunk_text(sub_body, max_chars=max_chars, overlap=overlap)
                for idx, piece in enumerate(pieces):
                    results.append(
                        Chunk(
                            doc_id=doc_id,
                            section=f"DESCRIPTION::{sub_title}",
                            chunk_index=idx,
                            text=piece,
                            source_path=str(path),
                        )
                    )
        else:
            pieces = chunk_text(section_text, max_chars=max_chars, overlap=overlap)
            for idx, piece in enumerate(pieces):
                results.append(
                    Chunk(
                        doc_id=doc_id,
                        section=section_name,
                        chunk_index=idx,
                        text=piece,
                        source_path=str(path),
                    )
                )

    return results
