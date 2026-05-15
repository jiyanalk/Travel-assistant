from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from agents.light_travel_chat_agent import LightTravelChatAgent
from schemas.light_trip import ChatAgentResult
from schemas.ws import WSClientMessage, WSServerMessage
from services.ws_session_manager import ws_session_manager


router = APIRouter()


async def _send(websocket: WebSocket, message_type: str, payload: Any = None) -> None:
    message = WSServerMessage(type=message_type, payload=payload)
    await websocket.send_json(message.model_dump(mode="json"))


async def _send_assistant_message(
    websocket: WebSocket,
    *,
    session_id: str,
    result: ChatAgentResult,
) -> None:
    await websocket.send_json(
        {
            "type": "assistant_message",
            "session_id": session_id,
            "message": result.assistant_message,
            "request": result.updated_request.model_dump(mode="json")
            if result.updated_request
            else None,
            "plan": result.updated_plan.model_dump(mode="json")
            if result.updated_plan
            else None,
            "metadata": {
                "intent": result.intent,
                "used_tools": result.used_tools,
            },
        }
    )


@router.websocket("/ws/trips/{session_id}")
async def trip_session_socket(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = ws_session_manager.get_or_create(session_id)
    await _send(websocket, "connected", ws_session_manager.to_snapshot(session))

    try:
        while True:
            try:
                payload = WSClientMessage.model_validate(await websocket.receive_json())
            except ValidationError as exc:
                await _send(websocket, "error", {"message": "消息格式不正确。", "details": exc.errors()})
                continue

            if payload.type == "ping":
                await _send(websocket, "pong", {"session_id": session.session_id})
                continue

            if payload.type == "request_snapshot":
                await _send(websocket, "snapshot", ws_session_manager.to_snapshot(session))
                continue

            user_message = (payload.message or "").strip()
            if not user_message:
                await _send(websocket, "error", {"message": "请输入有效的旅行需求或追问。"})
                continue

            if payload.user_id:
                session = ws_session_manager.get_or_create(session_id, user_id=payload.user_id)

            try:
                result = await LightTravelChatAgent().chat(
                    session_id=session_id,
                    user_id=payload.user_id or session.user_id,
                    user_message=user_message,
                )
            except Exception as exc:
                await _send(websocket, "error", {"message": f"轻量旅行助手处理失败：{exc}"})
                continue

            await _send_assistant_message(
                websocket,
                session_id=session_id,
                result=result,
            )
    except WebSocketDisconnect:
        return
