from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any

import websockets


DEFAULT_MESSAGE = "我想去成都玩三天，两个人，预算3000，喜欢美食和city walk"
VALID_INTENTS = {"draft_plan", "collect_info", "chat", "budget_estimate", "revise_plan"}
FALLBACK_MESSAGE = "我刚刚理解得不够稳定，可以请你换个方式描述一下你的旅行需求吗？"


async def run_check(base_url: str, timeout_seconds: float) -> tuple[bool, str]:
    session_id = f"e2e_light_{int(time.time())}"
    url = f"{base_url.rstrip('/')}/ws/trips/{session_id}"

    try:
        async with websockets.connect(url, open_timeout=timeout_seconds) as websocket:
            await _receive_until(websocket, {"connected"}, timeout_seconds)
            await websocket.send(
                json.dumps(
                    {
                        "type": "user_message",
                        "message": DEFAULT_MESSAGE,
                    },
                    ensure_ascii=False,
                )
            )
            response = await _receive_until(websocket, {"assistant_message", "error"}, timeout_seconds)
    except Exception as exc:
        return False, f"连接或等待 WebSocket 消息失败：{exc}"

    if response.get("type") == "error":
        return False, f"后端返回 error：{response}"

    ok, reason = _validate_assistant_message(response)
    if not ok:
        return False, reason
    return True, "轻量 Agent WebSocket 端到端检查通过。"


async def _receive_until(
    websocket: websockets.WebSocketClientProtocol,
    accepted_types: set[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"等待 {sorted(accepted_types)} 超时")
        raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        payload = json.loads(raw)
        if payload.get("type") in accepted_types:
            return payload


def _validate_assistant_message(response: dict[str, Any]) -> tuple[bool, str]:
    checks = {
        'type == "assistant_message"': response.get("type") == "assistant_message",
        "message 不为空": bool(response.get("message")),
        "message 不是 fallback": response.get("message") != FALLBACK_MESSAGE,
        'request.destination == "成都"': _read_path(response, "request", "destination") == "成都",
        "request.days == 3": _read_path(response, "request", "days") == 3,
        "request.people == 2": _read_path(response, "request", "people") == 2,
        "request.budget == 3000": _read_path(response, "request", "budget") == 3000,
        "plan 不为空": bool(response.get("plan")),
        "metadata.intent 合法": _read_path(response, "metadata", "intent") in VALID_INTENTS,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        return False, f"校验失败：{', '.join(failed)}\n返回内容：{json.dumps(response, ensure_ascii=False, indent=2)}"
    return True, "ok"


def _read_path(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the lightweight travel agent WebSocket flow.")
    parser.add_argument(
        "--ws-base-url",
        default=os.getenv("LIGHT_AGENT_WS_BASE_URL", "ws://127.0.0.1:8000"),
        help="WebSocket base URL, e.g. ws://127.0.0.1:8000",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("LIGHT_AGENT_E2E_TIMEOUT", "60")),
        help="Timeout in seconds.",
    )
    args = parser.parse_args()

    passed, message = asyncio.run(run_check(args.ws_base_url, args.timeout))
    if passed:
        print(f"PASS: {message}")
        return 0
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
