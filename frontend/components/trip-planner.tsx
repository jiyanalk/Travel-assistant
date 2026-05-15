"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ConversationMessage,
  getTripWebSocketUrl,
  WSClientMessage,
} from "../lib/api";

type ConnectionStatus = "idle" | "connecting" | "connected" | "reconnecting" | "closed";
type JsonObject = Record<string, unknown>;
type AnyServerMessage = {
  type: string;
  payload?: unknown;
  session_id?: string;
  message?: string;
  request?: JsonObject | null;
  plan?: JsonObject | null;
  metadata?: JsonObject | null;
};

export function TravelChatApp() {
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [tripId, setTripId] = useState<string | null>(null);
  const [request, setRequest] = useState<JsonObject | null>(null);
  const [plan, setPlan] = useState<JsonObject | null>(null);
  const [metadata, setMetadata] = useState<JsonObject | null>(null);
  const [agentSteps, setAgentSteps] = useState<string[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const budgetSummary = useMemo(() => findBudgetSummary(plan), [plan]);

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
          handleServerMessage(JSON.parse(event.data) as AnyServerMessage);
        } catch {
          setError("后端返回了无法解析的 WebSocket 消息。");
          setBusy(false);
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

  function handleServerMessage(serverMessage: AnyServerMessage) {
    switch (serverMessage.type) {
      case "connected":
      case "snapshot":
        applySnapshot(asObject(serverMessage.payload));
        return;
      case "step_start": {
        const payload = asObject(serverMessage.payload);
        const step = typeof payload?.step === "string" ? payload.step : null;
        if (step) {
          setAgentSteps((current) => (current.includes(step) ? current : [...current, step]));
        }
        return;
      }
      case "plan_result":
        applyLegacyPlanResponse(asObject(serverMessage.payload));
        setBusy(false);
        return;
      case "plan_revised": {
        const payload = asObject(serverMessage.payload);
        const revisedPlan = asObject(payload?.trip_plan);
        if (revisedPlan) {
          setPlan(revisedPlan);
        }
        setBusy(false);
        return;
      }
      case "assistant_message":
        applyAssistantMessage(serverMessage);
        setBusy(false);
        return;
      case "error":
        setError(readErrorMessage(serverMessage));
        setBusy(false);
        return;
      default:
        return;
    }
  }

  function applyAssistantMessage(serverMessage: AnyServerMessage) {
    const payload = asObject(serverMessage.payload);
    const assistantText = serverMessage.message ?? readString(payload?.message);
    const nextRequest = asObject(serverMessage.request) ?? asObject(payload?.request);
    const nextPlan = asObject(serverMessage.plan) ?? asObject(payload?.plan);
    const nextMetadata = asObject(serverMessage.metadata) ?? asObject(payload?.metadata);

    if (assistantText) {
      setMessages((current) => [...current, { role: "assistant", content: assistantText }]);
    }
    if (nextRequest) {
      setRequest(nextRequest);
    }
    if (nextPlan) {
      setPlan(nextPlan);
    }
    if (nextMetadata) {
      setMetadata(nextMetadata);
    }
  }

  function applySnapshot(snapshot: JsonObject | null) {
    if (!snapshot) {
      return;
    }

    setThreadId(readString(snapshot.thread_id));
    setTripId(readString(snapshot.trip_id));

    const latestRequest = asObject(snapshot.latest_request) ?? asObject(snapshot.light_latest_request);
    const latestPlan = asObject(snapshot.latest_plan) ?? asObject(snapshot.light_latest_plan);

    setRequest(latestRequest);
    setPlan(latestPlan);
    setAgentSteps([]);

    const history = readConversation(snapshot.message_history);
    const lightHistory = readConversation(snapshot.light_message_history);
    setMessages(history.length > 0 ? history : lightHistory);
  }

  function applyLegacyPlanResponse(response: JsonObject | null) {
    if (!response) {
      return;
    }
    setThreadId(readString(response.thread_id));
    setTripId(readString(response.trip_id));
    setRequest(asObject(response.trip_request));
    setPlan(asObject(response.trip_plan));
    setAgentSteps(readStringArray(response.agent_steps));
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
      setError("请输入旅行需求或继续追问。");
      return;
    }

    if (!sendSocketMessage({ type: "user_message", message: trimmed })) {
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
            <p className="eyebrow">Travel Assistant</p>
            <span className={`status-pill status-${connectionStatus}`}>
              {connectionStatusLabel(connectionStatus)}
            </span>
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
              <div className="conversation-empty">新的对话会在这里保留上下文。</div>
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
              {busy ? "Agent 处理中..." : "发送"}
            </button>
          </form>

          <div className="session-meta">
            <span>session: {sessionId ?? "建立中"}</span>
            {threadId ? <span>thread: {threadId}</span> : null}
            {tripId ? <span>trip: {tripId}</span> : null}
          </div>

          {error ? <div className="error-box">{error}</div> : null}
        </section>

        <section className="panel panel-dark">
          <div className="result-header">
            <div>
              <p className="subtle-tag">Current State</p>
              <h2>旅行需求与轻量行程草案</h2>
            </div>
          </div>

          <StateCard title="当前解析出的旅行需求" value={request} emptyText="还没有解析到旅行需求。" />

          <div className="result-block">
            <p className="subtle-tag">Plan</p>
            <h3>当前轻量行程草案</h3>
            {plan ? <PlanView plan={plan} /> : <p className="muted-line">还没有生成行程草案。</p>}
          </div>

          {budgetSummary ? (
            <div className="result-block">
              <p className="subtle-tag">Budget</p>
              <h3>预算摘要</h3>
              <p>{budgetSummary}</p>
            </div>
          ) : null}

          {agentSteps.length > 0 ? (
            <details className="result-block">
              <summary>旧 Agent 执行轨迹</summary>
              <div className="steps-list">
                {agentSteps.map((step, index) => (
                  <div key={`${step}-${index}`} className="step-card">
                    {step}
                  </div>
                ))}
              </div>
            </details>
          ) : null}

          <details className="result-block">
            <summary>Dev metadata</summary>
            <pre>{JSON.stringify(metadata ?? {}, null, 2)}</pre>
          </details>
        </section>
      </div>
    </main>
  );
}

function StateCard({
  title,
  value,
  emptyText,
}: {
  title: string;
  value: JsonObject | null;
  emptyText: string;
}) {
  return (
    <div className="result-block">
      <p className="subtle-tag">Request</p>
      <h3>{title}</h3>
      {value ? <pre>{JSON.stringify(value, null, 2)}</pre> : <p className="muted-line">{emptyText}</p>}
    </div>
  );
}

function PlanView({ plan }: { plan: JsonObject }) {
  const title = readString(plan.title) ?? readString(plan.trip_title);
  const summary = readString(plan.summary);
  const destination = readString(plan.destination);
  const days = readNumber(plan.days) ?? readNumber(plan.duration_days);
  const dailyPlan = readStringArray(plan.daily_plan);
  const legacyDays = Array.isArray(plan.days) ? plan.days : [];
  const tips = readStringArray(plan.tips);
  const warnings = readStringArray(plan.warnings);

  return (
    <div className="trip-plan">
      {title ? <h3>{title}</h3> : null}
      {destination || days ? (
        <div className="chip-row">
          {destination ? <span className="chip chip-soft">{destination}</span> : null}
          {days ? <span className="chip chip-soft">{days} 天</span> : null}
        </div>
      ) : null}
      {summary ? <p>{summary}</p> : null}

      {dailyPlan.length > 0 ? (
        <ul className="plain-list">
          {dailyPlan.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : null}

      {dailyPlan.length === 0 && legacyDays.length > 0 ? (
        <div className="day-list">
          {legacyDays.map((day, index) => (
            <LegacyDayCard key={index} day={asObject(day)} index={index} />
          ))}
        </div>
      ) : null}

      {tips.length > 0 ? <StringList title="提示" items={tips} /> : null}
      {warnings.length > 0 ? <StringList title="注意事项" items={warnings} /> : null}
    </div>
  );
}

function LegacyDayCard({ day, index }: { day: JsonObject | null; index: number }) {
  if (!day) {
    return null;
  }

  const title = readString(day.theme) ?? `Day ${index + 1}`;
  const items = Array.isArray(day.items) ? day.items : [];

  return (
    <article className="day-card">
      <div className="day-header">
        <strong>Day {readNumber(day.day) ?? index + 1}</strong>
        <span>{title}</span>
      </div>
      {items.length > 0 ? (
        <ul className="plain-list">
          {items.map((rawItem, itemIndex) => {
            const item = asObject(rawItem);
            const itemTitle = readString(item?.title) ?? "未命名安排";
            const time = readString(item?.time);
            return (
              <li key={`${itemTitle}-${itemIndex}`}>
                {time ? `${time} ` : ""}
                {itemTitle}
              </li>
            );
          })}
        </ul>
      ) : null}
    </article>
  );
}

function StringList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4>{title}</h4>
      <ul className="plain-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function findBudgetSummary(plan: JsonObject | null): string | null {
  if (!plan) {
    return null;
  }
  const direct = readString(plan.budget_summary);
  if (direct) {
    return direct;
  }
  const budget = asObject(plan.budget);
  const estimatedTotal = budget ? readNumber(budget.estimated_total) : null;
  const currency = budget ? readString(budget.currency) ?? "CNY" : "CNY";
  return estimatedTotal !== null ? `总预算估算：${currency} ${estimatedTotal}` : null;
}

function readErrorMessage(serverMessage: AnyServerMessage): string {
  const payload = asObject(serverMessage.payload);
  return serverMessage.message ?? readString(payload?.message) ?? "后端处理失败。";
}

function asObject(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function readConversation(value: unknown): ConversationMessage[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    const entry = asObject(item);
    const role = readString(entry?.role);
    const content = readString(entry?.content);
    if ((role === "user" || role === "assistant") && content) {
      return [{ role, content }];
    }
    return [];
  });
}

function createSessionId() {
  return `trip_${Date.now()}_${Math.random().toString(16).slice(2, 10)}`;
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
