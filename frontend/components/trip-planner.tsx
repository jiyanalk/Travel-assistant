"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import {
  ConversationMessage,
  getTripWebSocketUrl,
  TripPlan,
  TripPlanResponse,
  TripRequestSnapshot,
  WSClientMessage,
  WSServerMessage,
  WSSessionSnapshot,
} from "../lib/api";

const defaultMessage = "";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";

export function TripPlanner() {
  const [message, setMessage] = useState(defaultMessage);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [tripId, setTripId] = useState<string | null>(null);
  const [tripPlan, setTripPlan] = useState<TripPlan | null>(null);
  const [tripRequest, setTripRequest] = useState<TripRequestSnapshot | null>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);
  const [agentSteps, setAgentSteps] = useState<string[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const nextSessionId = createSessionId();
    window.localStorage.setItem("travel-assistant-session-id", nextSessionId);
    setSessionId(nextSessionId);
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    const connect = () => {
      setConnectionStatus(socketRef.current ? "reconnecting" : "connecting");
      const socket = new WebSocket(getTripWebSocketUrl(sessionId));
      socketRef.current = socket;

      socket.onopen = () => {
        setConnectionStatus("connected");
        setError(null);
        sendSocketMessage({ type: "request_snapshot" });
      };

      socket.onmessage = (event) => {
        try {
          handleServerMessage(JSON.parse(event.data) as WSServerMessage);
        } catch {
          setError("后端返回了无法解析的 WebSocket 消息。");
        }
      };

      socket.onerror = () => {
        setError("WebSocket 连接异常，请确认后端服务仍在运行。");
      };

      socket.onclose = () => {
        socketRef.current = null;
        setBusy(false);
        if (disposed) {
          setConnectionStatus("closed");
          return;
        }
        setConnectionStatus("reconnecting");
        reconnectTimer = setTimeout(connect, 1500);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [sessionId]);

  function handleServerMessage(serverMessage: WSServerMessage) {
    switch (serverMessage.type) {
      case "connected":
      case "snapshot":
        applySnapshot(serverMessage.payload as WSSessionSnapshot);
        return;
      case "step_start": {
        const payload = serverMessage.payload as { step?: string } | undefined;
        if (payload?.step) {
          setAgentSteps((current) =>
            current.includes(payload.step as string) ? current : [...current, payload.step as string],
          );
        }
        return;
      }
      case "plan_result":
        applyPlanResponse(serverMessage.payload as TripPlanResponse);
        setBusy(false);
        return;
      case "plan_revised": {
        const payload = serverMessage.payload as
          | { trip_plan?: TripPlan }
          | undefined;
        if (payload?.trip_plan) {
          setTripPlan(payload.trip_plan);
          setClarificationQuestion(null);
        }
        setBusy(false);
        return;
      }
      case "assistant_message": {
        const payload = serverMessage.payload as { message?: string } | undefined;
        if (payload?.message) {
          setMessages((current) => [...current, { role: "assistant", content: payload.message as string }]);
        }
        setBusy(false);
        return;
      }
      case "error": {
        const payload = serverMessage.payload as { message?: string } | undefined;
        setError(payload?.message || "后端处理失败。");
        setBusy(false);
        return;
      }
      default:
        return;
    }
  }

  function applySnapshot(snapshot: WSSessionSnapshot) {
    setThreadId(snapshot.thread_id ?? null);
    setTripId(snapshot.trip_id ?? null);
    setTripPlan(snapshot.latest_trip_plan ?? snapshot.last_plan_response?.trip_plan ?? null);
    setTripRequest(snapshot.last_plan_response?.trip_request ?? null);
    setAgentSteps(snapshot.last_plan_response?.agent_steps ?? []);
    setMessages(snapshot.message_history ?? []);
    setClarificationQuestion(
      snapshot.last_plan_response?.need_clarification
        ? snapshot.last_plan_response.clarification_question ?? null
        : null,
    );
  }

  function applyPlanResponse(response: TripPlanResponse) {
    setThreadId(response.thread_id ?? null);
    setTripId(response.trip_id ?? null);
    setTripRequest(response.trip_request ?? null);
    setAgentSteps(response.agent_steps);
    setClarificationQuestion(
      response.need_clarification ? response.clarification_question ?? null : null,
    );
    setTripPlan(response.trip_plan ?? null);
  }

  function sendSocketMessage(payload: WSClientMessage) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError("WebSocket 尚未连接，请稍后再试。");
      return false;
    }
    socket.send(JSON.stringify(payload));
    return true;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      setError("请输入旅行需求或补充说明。");
      return;
    }

    const payload: WSClientMessage =
      tripPlan && !clarificationQuestion
        ? { type: "revise_plan", message: trimmed }
        : { type: "user_message", message: trimmed };

    if (!sendSocketMessage(payload)) {
      return;
    }

    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    setBusy(true);
    setError(null);
    setMessage("");
  }

  return (
    <main className="page-shell">
      <div className="page-grid">
        <section className="panel panel-light">
          <div className="connection-row">
            <p className="eyebrow">Travel Planning Agent</p>
            <span className={`status-pill status-${connectionStatus}`}>{connectionStatusLabel(connectionStatus)}</span>
          </div>

          <div className="conversation-panel">
            {messages.length > 0 ? (
              messages.map((entry, index) => (
                <article key={`${entry.role}-${index}`} className={`message-bubble message-${entry.role}`}>
                  <strong>{entry.role === "user" ? "你" : "Agent"}</strong>
                  <p>{entry.content}</p>
                </article>
              ))
            ) : (
              <div className="conversation-empty">新的会话会在这里保留上下文。</div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="stack">
            <textarea
              id="trip-message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              className="textarea"
              placeholder="输入旅行需求，或继续追问并调整行程"
            />
            <button className="primary-button" type="submit" disabled={busy || connectionStatus !== "connected"}>
              {busy ? "Agent 处理中..." : submitLabel(Boolean(tripPlan), Boolean(clarificationQuestion))}
            </button>
          </form>

          {tripRequest ? (
            <div className="callout">
              <h3>当前解析到的旅行需求</h3>
              <pre>{JSON.stringify(tripRequest, null, 2)}</pre>
            </div>
          ) : null}

          {clarificationQuestion ? (
            <div className="callout">
              <h3>需要补充的信息</h3>
              <pre>{clarificationQuestion}</pre>
            </div>
          ) : null}

          <div className="session-meta">
            <span>session: {sessionId ?? "建立中"}</span>
            {threadId ? <span>thread: {threadId}</span> : null}
          </div>

          {error ? <div className="error-box">{error}</div> : null}
        </section>

        <section className="panel panel-dark">
          <div className="result-header">
            <div>
              <p className="subtle-tag">Agent Trace</p>
              <h2>执行轨迹与模型调试输出</h2>
            </div>
            {tripId ? <span className="chip">trip_id: {tripId}</span> : null}
          </div>

          <div className="steps-list">
            {agentSteps.length > 0 ? (
              agentSteps.map((step, index) => (
                <div key={`${step}-${index}`} className="step-card">
                  {step}
                </div>
              ))
            ) : (
              <div className="empty-box">发送一次需求后，这里会实时显示 Agent 节点推进。</div>
            )}
          </div>

          {tripPlan ? <TripPlanView tripPlan={tripPlan} /> : <EmptyPlanState />}
        </section>
      </div>
    </main>
  );
}

function EmptyPlanState() {
  return (
    <div className="empty-plan">
      <h3>还没有生成结果</h3>
      <p>先发起一次会话，后端返回的 TripPlan 会在这里实时渲染。</p>
    </div>
  );
}

function TripPlanView({ tripPlan }: { tripPlan: TripPlan }) {
  return (
    <div className="trip-plan">
      <div className="result-block">
        <p className="subtle-tag">TripPlan</p>
        <h3>{tripPlan.trip_title}</h3>
        <p>{tripPlan.summary}</p>
        <div className="chip-row">
          {tripPlan.travel_style.map((style) => (
            <span key={style} className="chip chip-soft">
              {style}
            </span>
          ))}
        </div>
      </div>

      <div className="result-block">
        <h3>预算与住宿</h3>
        <p>
          总计：{tripPlan.budget.currency} {tripPlan.budget.estimated_total}
        </p>
        <p>
          住宿：{tripPlan.budget.currency} {tripPlan.budget.hotel_total}
          {tripPlan.budget.hotel_budget_per_night
            ? ` · 目标每晚 ${tripPlan.budget.hotel_budget_per_night}`
            : ""}
        </p>
        {tripPlan.budget.hotel_recommendations.length > 0 ? (
          <div className="day-list">
            {tripPlan.budget.hotel_recommendations.map((hotel) => (
              <article key={`${hotel.name}-${hotel.area}`} className="day-card">
                <div className="day-header">
                  <div>
                    <strong>{hotel.name}</strong>
                    <p>{hotel.area}</p>
                  </div>
                  <span className="chip chip-soft">
                    {tripPlan.budget.currency} {hotel.nightly_price}/晚
                  </span>
                </div>
                {hotel.rating ? <p>评分：{hotel.rating}</p> : null}
                {hotel.reason ? <p>{hotel.reason}</p> : null}
                {hotel.booking_hint ? <p className="backup-line">提示：{hotel.booking_hint}</p> : null}
              </article>
            ))}
          </div>
        ) : null}
      </div>

      <div className="result-block">
        <h3>每日日程</h3>
        <div className="day-list">
          {tripPlan.days.map((day) => (
            <article key={day.day} className="day-card">
              <div className="day-header">
                <div>
                  <strong>Day {day.day}</strong>
                  <p>{day.theme}</p>
                </div>
                <span className="chip chip-soft">
                  {day.pace} · {tripPlan.budget.currency} {day.estimated_cost}
                </span>
              </div>
              <ul className="plain-list">
                {day.items.map((item) => (
                  <li key={`${day.day}-${item.time}-${item.title}`}>
                    <div>
                      <strong>{item.time}</strong> {item.title}
                      {item.location ? ` · ${item.location}` : ""}
                    </div>
                    {item.estimated_cost ? (
                      <div>
                        {_costLabel(item.type)}：{tripPlan.budget.currency} {item.estimated_cost}
                      </div>
                    ) : null}
                    {item.notes ? <div>{item.notes}</div> : null}
                    {item.transport_to_next ? (
                      <div>
                        前往下一站：{item.transport_to_next.mode} · {tripPlan.budget.currency}{" "}
                        {item.transport_to_next.estimated_cost ?? 0}
                        {item.transport_to_next.duration_minutes
                          ? ` · ${item.transport_to_next.duration_minutes} 分钟`
                          : ""}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
              {day.backup_plan ? <p className="backup-line">备选：{day.backup_plan}</p> : null}
            </article>
          ))}
        </div>
      </div>

      <div className="result-block">
        <h3>注意事项</h3>
        <ul className="plain-list">
          {tripPlan.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function _costLabel(type: string) {
  if (type === "attraction") {
    return "门票/体验费";
  }
  if (type === "food") {
    return "餐饮预算";
  }
  if (type === "rest") {
    return "休息消费";
  }
  return "预计花费";
}

function createSessionId() {
  return `trip_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
}

function submitLabel(hasTripPlan: boolean, needsClarification: boolean) {
  if (needsClarification) {
    return "补充信息并继续";
  }
  if (hasTripPlan) {
    return "发送追问并改计划";
  }
  return "生成行程";
}

function connectionStatusLabel(status: ConnectionStatus) {
  if (status === "connected") {
    return "已连接";
  }
  if (status === "connecting") {
    return "连接中";
  }
  if (status === "reconnecting") {
    return "重连中";
  }
  if (status === "closed") {
    return "已关闭";
  }
  return "准备中";
}
