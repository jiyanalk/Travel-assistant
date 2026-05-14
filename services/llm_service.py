from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.config import ROOT_DIR, get_settings
from services.debug_trace import append_debug_trace, to_debug_value


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when a model-backed step cannot be completed."""


class LLMServiceTimeoutError(LLMServiceError):
    """Raised when the model service does not respond before the configured timeout."""


def ensure_llm_configured() -> None:
    settings = get_settings()
    if not settings.zai_api_key:
        raise LLMServiceError("ZAI_API_KEY 未配置，当前服务无法通过模型生成回复。")
    if not settings.zhipu_model:
        raise LLMServiceError("ZHIPU_MODEL 未配置，当前服务无法通过模型生成回复。")
    if not settings.zhipu_base_url:
        raise LLMServiceError("ZHIPU_BASE_URL 未配置，当前服务无法通过模型生成回复。")


@lru_cache(maxsize=32)
def load_prompt(prompt_name: str) -> str:
    prompt_path = ROOT_DIR / "prompts" / prompt_name
    return prompt_path.read_text(encoding="utf-8")


def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    json_mode: bool = False,
    debug_trace: list[dict[str, Any]] | None = None,
    trace_step: str = "llm",
    trace_label: str | None = None,
) -> str:
    ensure_llm_configured()
    settings = get_settings()

    endpoint = f"{settings.zhipu_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zai_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(
        model=settings.zhipu_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        json_mode=json_mode,
    )

    try:
        data = _request_chat_completion(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
            debug_trace=debug_trace,
            trace_step=trace_step,
            trace_label=trace_label,
            attempt="primary",
        )
    except LLMServiceTimeoutError:
        raise
    except LLMServiceError as first_error:
        append_debug_trace(
            debug_trace,
            step=trace_step,
            stage="llm_error",
            label=trace_label,
            payload={"attempt": "primary", "message": str(first_error)},
        )
        if not json_mode:
            raise

        fallback_payload = _build_payload(
            model=settings.zhipu_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            json_mode=False,
        )
        append_debug_trace(
            debug_trace,
            step=trace_step,
            stage="llm_retry",
            label=trace_label,
            payload={
                "reason": str(first_error),
                "fallback_json_mode": False,
            },
        )
        try:
            data = _request_chat_completion(
                endpoint=endpoint,
                headers=headers,
                payload=fallback_payload,
                debug_trace=debug_trace,
                trace_step=trace_step,
                trace_label=trace_label,
                attempt="fallback_text_json",
            )
        except LLMServiceError as second_error:
            append_debug_trace(
                debug_trace,
                step=trace_step,
                stage="llm_error",
                label=trace_label,
                payload={
                    "attempt": "fallback_text_json",
                    "message": str(second_error),
                },
            )
            raise first_error

    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMServiceError(f"模型返回结构异常：{data}") from exc

    if isinstance(message, list):
        text = "".join(
            chunk.get("text", "")
            for chunk in message
            if isinstance(chunk, dict)
        )
    elif isinstance(message, str):
        text = message
    else:
        raise LLMServiceError(f"模型返回内容类型异常：{type(message)}")

    append_debug_trace(
        debug_trace,
        step=trace_step,
        stage="llm_content",
        label=trace_label,
        payload=text,
    )
    return text


def _build_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    json_mode: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _post_chat_completion(
    *,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> httpx.Response:
    try:
        client = _get_http_client()
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise LLMServiceError(f"模型服务返回异常状态码：{status}") from exc
    except httpx.TimeoutException as exc:
        raise LLMServiceTimeoutError("调用模型服务超时，请稍后重试，或检查网络/防火墙是否允许访问智谱接口。") from exc
    except httpx.HTTPError as exc:
        raise LLMServiceError(f"调用模型服务失败：{exc}") from exc


def _request_chat_completion(
    *,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    debug_trace: list[dict[str, Any]] | None,
    trace_step: str,
    trace_label: str | None,
    attempt: str,
) -> dict[str, Any]:
    append_debug_trace(
        debug_trace,
        step=trace_step,
        stage="llm_request",
        label=trace_label,
        payload={
            "attempt": attempt,
            "endpoint": endpoint,
            "payload": to_debug_value(payload),
        },
    )
    started_at = time.monotonic()
    logger.info(
        "LLM request started: step=%s label=%s attempt=%s model=%s json_mode=%s",
        trace_step,
        trace_label,
        attempt,
        payload.get("model"),
        bool(payload.get("response_format")),
    )
    try:
        response = _post_chat_completion(endpoint=endpoint, headers=headers, payload=payload)
    finally:
        elapsed = time.monotonic() - started_at
        logger.info(
            "LLM request finished: step=%s label=%s attempt=%s elapsed=%.2fs",
            trace_step,
            trace_label,
            attempt,
            elapsed,
        )
    data = response.json()
    append_debug_trace(
        debug_trace,
        step=trace_step,
        stage="llm_response",
        label=trace_label,
        payload={
            "attempt": attempt,
            "response": to_debug_value(data),
        },
    )
    return data


@lru_cache(maxsize=1)
def _get_http_client() -> httpx.Client:
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
    return httpx.Client(timeout=timeout, trust_env=False)


def generate_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    debug_trace: list[dict[str, Any]] | None = None,
    trace_step: str = "llm",
    trace_label: str | None = None,
) -> str:
    return chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        json_mode=False,
        debug_trace=debug_trace,
        trace_step=trace_step,
        trace_label=trace_label,
    ).strip()


def generate_structured_output(
    *,
    model_class: type[T],
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    debug_trace: list[dict[str, Any]] | None = None,
    trace_step: str = "llm",
    trace_label: str | None = None,
) -> T:
    schema = json.dumps(model_class.model_json_schema(), ensure_ascii=False, indent=2)
    full_system_prompt = (
        f"{system_prompt}\n\n"
        "你必须只返回一个合法 JSON 对象，不要返回解释、Markdown、代码块或多余文本。\n"
        f"输出 JSON 必须满足这个 Schema：\n{schema}"
    )
    raw_content = chat_completion(
        system_prompt=full_system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        json_mode=True,
        debug_trace=debug_trace,
        trace_step=trace_step,
        trace_label=trace_label,
    )
    payload = extract_json_object(raw_content)
    append_debug_trace(
        debug_trace,
        step=trace_step,
        stage="structured_payload",
        label=trace_label,
        payload=payload,
    )
    try:
        validated = model_class.model_validate(payload)
    except Exception as exc:
        append_debug_trace(
            debug_trace,
            step=trace_step,
            stage="structured_validation_error",
            label=trace_label,
            payload={"message": str(exc), "payload": payload},
        )
        raise LLMServiceError(f"模型输出无法通过结构校验：{exc}") from exc

    append_debug_trace(
        debug_trace,
        step=trace_step,
        stage="structured_validated",
        label=trace_label,
        payload=validated,
    )
    return validated


def extract_json_object(raw_content: str) -> dict[str, Any]:
    text = raw_content.strip()

    fenced_match = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return json.loads(text[first_brace : last_brace + 1])

    raise LLMServiceError(f"无法从模型响应中提取 JSON：{raw_content[:200]}")
