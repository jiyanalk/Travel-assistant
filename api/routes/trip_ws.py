from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from agents.travel_planning_agent import TravelPlanningAgent
from db.session import SessionLocal
from schemas.ws import WSClientMessage, WSServerMessage
from services.llm_service import LLMServiceError
from services.ws_session_manager import SessionState, ws_session_manager


router = APIRouter()


async def _send(websocket: WebSocket, message_type: str, payload: Any = None) -> None:
    message = WSServerMessage(type=message_type, payload=payload)
    await websocket.send_json(message.model_dump(mode="json"))


def _event_payload(event: dict[str, Any]) -> dict[str, Any] | Any:
    payload = {key: value for key, value in event.items() if key != "type"}
    if set(payload) == {"payload"}:
        return payload["payload"]
    return payload if payload else None


def _assistant_summary(session: SessionState) -> str:
    response = session.last_plan_response
    if response is None:
        return "Agent 已完成处理。"
    if response.need_clarification and response.clarification_question:
        return response.clarification_question
    if response.trip_plan is not None:
        return response.trip_plan.summary
    return "Agent 已完成处理。"


async def _run_agent_job(
    *,
    websocket: WebSocket,
    session: SessionState,
    job: Callable[[Callable[[dict[str, Any]], None]], Any],
) -> Any:
    event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    async def stream_events() -> None:
        while True:
            event = await event_queue.get()
            if event is None:
                return
            await _send(websocket, event["type"], _event_payload(event))

    stream_task = asyncio.create_task(stream_events())

    async def invoke_job() -> Any:
        try:
            return await asyncio.to_thread(job, emit)
        finally:
            loop.call_soon_threadsafe(event_queue.put_nowait, None)

    result = await invoke_job()
    await stream_task
    return result


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

            message = (payload.message or "").strip()
            if not message:
                await _send(websocket, "error", {"message": "请输入有效的旅行需求或追问。"})
                continue

            if payload.user_id:
                session = ws_session_manager.get_or_create(session_id, user_id=payload.user_id)
            ws_session_manager.append_user_message(session, message)

            if payload.type == "user_message":
                with SessionLocal() as db:
                    agent = TravelPlanningAgent(db=db)

                    def plan_job(emit: Callable[[dict[str, Any]], None]):
                        return agent.plan_trip(
                            message=message,
                            user_id=session.user_id,
                            thread_id=session.thread_id if session.awaiting_clarification else None,
                            event_emitter=emit,
                        )

                    try:
                        response = await _run_agent_job(
                            websocket=websocket,
                            session=session,
                            job=plan_job,
                        )
                    except LLMServiceError as exc:
                        await _send(websocket, "error", {"message": str(exc)})
                        continue
                    except Exception as exc:
                        await _send(
                            websocket,
                            "error",
                            {"message": f"行程生成失败：{exc}"},
                        )
                        continue

                ws_session_manager.update_plan_response(session, response)
                assistant_message = _assistant_summary(session)
                ws_session_manager.append_assistant_message(session, assistant_message)
                await _send(websocket, "assistant_message", {"message": assistant_message})
                await _send(websocket, "snapshot", ws_session_manager.to_snapshot(session))
                continue

            if session.latest_trip_plan is None:
                await _send(websocket, "error", {"message": "当前还没有可修改的行程，请先生成行程。"})
                continue

            with SessionLocal() as db:
                agent = TravelPlanningAgent(db=db)

                def revise_job(emit: Callable[[dict[str, Any]], None]):
                    return agent.revise_trip_plan(
                        trip_plan=session.latest_trip_plan,
                        message=message,
                        trip_id=session.trip_id,
                        event_emitter=emit,
                    )

                try:
                    updated_plan, changes = await _run_agent_job(
                        websocket=websocket,
                        session=session,
                        job=revise_job,
                    )
                except LLMServiceError as exc:
                    await _send(websocket, "error", {"message": str(exc)})
                    continue
                except Exception as exc:
                    await _send(
                        websocket,
                        "error",
                        {"message": f"行程修改失败：{exc}"},
                    )
                    continue

            ws_session_manager.update_revised_plan(session, updated_plan)
            revision_message = "行程已更新。" if not changes else "；".join(changes)
            ws_session_manager.append_assistant_message(session, revision_message)
            await _send(
                websocket,
                "plan_revised",
                {
                    "trip_plan": updated_plan.model_dump(mode="json"),
                    "changes": changes,
                },
            )
            await _send(websocket, "assistant_message", {"message": revision_message})
            await _send(websocket, "snapshot", ws_session_manager.to_snapshot(session))
    except WebSocketDisconnect:
        return
