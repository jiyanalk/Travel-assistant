export interface LightTripRequest {
  origin?: string | null;
  destination?: string | null;
  days?: number | null;
  people?: number;
  budget?: number | null;
  interests: string[];
  travel_style?: string | null;
  constraints: string[];
}

export interface LightTripPlan {
  destination?: string | null;
  days?: number | null;
  summary: string;
  daily_plan: string[];
  budget_summary?: string | null;
  tips: string[];
}

export interface LightAssistantMessage {
  type: "assistant_message";
  session_id: string;
  message: string;
  request?: LightTripRequest | null;
  plan?: LightTripPlan | null;
  metadata: {
    intent?: string;
    used_tools?: string[];
  };
}

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

export type WSSessionSnapshot = {
  session_id: string;
  user_id?: string | null;
  latest_request?: LightTripRequest | null;
  latest_plan?: LightTripPlan | null;
  message_history: ConversationMessage[];
  preference_memory?: Record<string, unknown>;
  light_latest_request?: LightTripRequest | null;
  light_latest_plan?: LightTripPlan | null;
  light_message_history?: ConversationMessage[];
  light_preference_memory?: Record<string, unknown>;
};

export type WSServerMessage =
  | LightAssistantMessage
  | { type: "connected"; payload?: WSSessionSnapshot }
  | { type: "snapshot"; payload?: WSSessionSnapshot }
  | { type: "error"; payload?: { message?: string }; message?: string }
  | { type: "pong"; payload?: { session_id?: string } };

export type WSClientMessage =
  | { type: "user_message"; message: string; user_id?: string | null }
  | { type: "revise_plan"; message: string; user_id?: string | null }
  | { type: "request_snapshot" }
  | { type: "ping" };

const CONFIGURED_WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL?.trim();
const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

export function getTripWebSocketUrl(sessionId: string): string {
  const baseUrl = resolveWebSocketBaseUrl();
  return `${baseUrl}/ws/trips/${encodeURIComponent(sessionId)}`;
}

function resolveWebSocketBaseUrl(): string {
  if (CONFIGURED_WS_BASE_URL) {
    return CONFIGURED_WS_BASE_URL.replace(/\/+$/, "");
  }

  if (CONFIGURED_API_BASE_URL) {
    return CONFIGURED_API_BASE_URL.replace(/^http/i, "ws").replace(/\/+$/, "");
  }

  if (typeof window !== "undefined" && window.location.hostname) {
    return `ws://${window.location.hostname}:8000`;
  }

  return "ws://127.0.0.1:8000";
}
