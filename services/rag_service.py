from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import ROOT_DIR
from services.debug_trace import append_debug_trace
from services.llm_service import generate_structured_output


GUIDES_DIR = ROOT_DIR / "data" / "guides"
SLUG_MAP = {"大阪": "osaka", "东京": "tokyo", "曼谷": "bangkok"}


class GuideContextResult(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)


def retrieve_guide_context(
    destination: str,
    interests: list[str],
    pace: str,
    debug_trace: list[dict[str, Any]] | None = None,
) -> list[str]:
    slug = SLUG_MAP.get(destination)
    if slug is not None:
        guide_path = GUIDES_DIR / f"{slug}.md"
        if guide_path.exists():
            paragraphs = _read_local_guide(guide_path, interests, pace)
            append_debug_trace(
                debug_trace,
                step="retrieve_travel_guide_context",
                stage="guide_source",
                label="local_guide",
                payload={
                    "destination": destination,
                    "guide_file": guide_path.name,
                    "paragraphs": paragraphs,
                },
            )
            return paragraphs

    generated = _generate_guide_context(
        destination=destination,
        interests=interests,
        pace=pace,
        debug_trace=debug_trace,
    )
    append_debug_trace(
        debug_trace,
        step="retrieve_travel_guide_context",
        stage="guide_source",
        label="model_generated",
        payload={
            "destination": destination,
            "paragraphs": generated,
        },
    )
    return generated


def _read_local_guide(guide_path: Path, interests: list[str], pace: str) -> list[str]:
    text = guide_path.read_text(encoding="utf-8")
    paragraphs = [segment.strip() for segment in text.split("\n\n") if segment.strip()]
    filtered = []

    for paragraph in paragraphs:
        if any(interest in paragraph for interest in interests) or pace in paragraph:
            filtered.append(paragraph)

    return filtered[:3] or paragraphs[:3]


def _generate_guide_context(
    *,
    destination: str,
    interests: list[str],
    pace: str,
    debug_trace: list[dict[str, Any]] | None,
) -> list[str]:
    result = generate_structured_output(
        model_class=GuideContextResult,
        system_prompt=(
            "你是旅行攻略摘要助手。\n"
            "请为指定目的地生成简短、实用、可用于行程规划的攻略片段。\n"
            "内容要尽量具体，但不要伪造精确营业时间或票价。"
        ),
        user_prompt=(
            f"目的地：{destination}\n"
            f"兴趣：{json.dumps(interests, ensure_ascii=False)}\n"
            f"节奏：{pace}\n"
            "请返回 3 段攻略摘要，每段 1 到 3 句话，分别覆盖：\n"
            "1. 适合这个目的地的游玩区域或路线组织方式。\n"
            "2. 与用户兴趣相关的推荐方向。\n"
            "3. 节奏、交通或避坑提醒。"
        ),
        temperature=0.25,
        debug_trace=debug_trace,
        trace_step="retrieve_travel_guide_context",
        trace_label="generate_guide_context",
    )
    return result.paragraphs[:3]
