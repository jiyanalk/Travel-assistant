from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from app.config import ROOT_DIR
from services.city_alias_service import CITY_ALIASES, normalize_city_name


DEFAULT_CITY_GUIDE_DIR = ROOT_DIR / "data" / "knowledge" / "city_guide"

CITY_FILE_MAP: dict[str, str] = {
    "成都": "chengdu.md",
    "重庆": "chongqing.md",
    "上海": "shanghai.md",
    "北京": "beijing.md",
    "广州": "guangzhou.md",
    "深圳": "shenzhen.md",
}

COMMON_TERMS = [
    "美食",
    "夜景",
    "city walk",
    "亲子",
    "文化",
    "自然",
    "海边",
    "茶馆",
    "熊猫",
    "胡同",
    "博物馆",
    "早茶",
    "慢节奏",
    "轻松",
    "经典",
]


def load_city_documents(base_dir: str | Path = DEFAULT_CITY_GUIDE_DIR) -> dict[str, str]:
    """Load local Markdown city guides keyed by canonical city name."""

    root = Path(base_dir)
    documents: dict[str, str] = {}
    for city, filename in CITY_FILE_MAP.items():
        path = root / filename
        if not path.exists():
            continue
        documents[city] = path.read_text(encoding="utf-8")
    return documents


def split_markdown_sections(markdown_text: str) -> list[dict]:
    """Split a city guide into level-2 Markdown sections."""

    city = _extract_city(markdown_text)
    sections: list[dict] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current_title:
                sections.append(
                    {
                        "city": city,
                        "title": current_title,
                        "content": "\n".join(current_lines).strip(),
                    }
                )
            current_title = line[3:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    if current_title:
        sections.append(
            {
                "city": city,
                "title": current_title,
                "content": "\n".join(current_lines).strip(),
            }
        )
    return sections


def score_section(
    section: dict,
    query_terms: list[str],
    destination: Optional[str],
    interests: list[str],
) -> float:
    """Score a Markdown section using transparent keyword matching."""

    title = str(section.get("title") or "")
    content = str(section.get("content") or "")
    city = str(section.get("city") or "")
    haystack = f"{city}\n{title}\n{content}".lower()

    score = 0.0
    if destination and city == destination:
        score += 2.0
    for interest in interests:
        term = interest.strip().lower()
        if not term:
            continue
        if term in title.lower():
            score += 2.0
        if term in content.lower():
            score += 1.5
    for term in query_terms:
        normalized = term.strip().lower()
        if not normalized:
            continue
        if normalized in title.lower():
            score += 1.5
        if normalized in haystack:
            score += 0.8
    return score


def retrieve_city_context(
    destination: Optional[str],
    interests: list[str],
    user_message: str,
    top_k: int = 3,
) -> list[dict]:
    """Retrieve top city-guide sections without LLMs, vectors, or network calls."""

    normalized_destination = _resolve_destination(destination, user_message)
    documents = load_city_documents()
    if not documents:
        return []

    target_documents = (
        {normalized_destination: documents[normalized_destination]}
        if normalized_destination in documents
        else documents
    )
    query_terms = _build_query_terms(normalized_destination, interests, user_message)

    scored: list[dict] = []
    for markdown_text in target_documents.values():
        for section in split_markdown_sections(markdown_text):
            score = score_section(
                section=section,
                query_terms=query_terms,
                destination=normalized_destination,
                interests=interests,
            )
            if score <= 0:
                continue
            scored.append(
                {
                    "city": section.get("city"),
                    "title": section.get("title"),
                    "content": section.get("content"),
                    "score": round(score, 2),
                }
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(top_k, 0)]


def _extract_city(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _resolve_destination(destination: Optional[str], user_message: str) -> Optional[str]:
    normalized_destination, _ = normalize_city_name(destination)
    if normalized_destination in CITY_FILE_MAP:
        return normalized_destination

    for alias, city in CITY_ALIASES.items():
        if alias in user_message:
            return city
    for city in CITY_FILE_MAP:
        if city in user_message:
            return city
    return normalized_destination


def _build_query_terms(
    destination: Optional[str],
    interests: list[str],
    user_message: str,
) -> list[str]:
    terms: list[str] = []
    if destination:
        terms.append(destination)
    terms.extend(interests or [])
    terms.extend(term for term in COMMON_TERMS if term.lower() in user_message.lower())
    terms.extend(re.findall(r"[A-Za-z][A-Za-z ]{1,24}", user_message))
    return _dedupe([term.strip() for term in terms if term and term.strip()])


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
