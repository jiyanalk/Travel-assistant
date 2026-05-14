export type TransportInfo = {
  mode: string;
  duration_minutes?: number | null;
  distance_km?: number | null;
  estimated_cost?: number | null;
  description?: string | null;
  is_estimated: boolean;
};

export type TripItem = {
  time: string;
  type: string;
  title: string;
  location?: string | null;
  duration_minutes?: number | null;
  estimated_cost?: number | null;
  is_cost_estimated?: boolean;
  reason?: string | null;
  notes?: string | null;
  transport_to_next?: TransportInfo | null;
};

export type DayPlan = {
  day: number;
  date?: string | null;
  theme: string;
  pace: string;
  items: TripItem[];
  estimated_cost: number;
  transport_summary?: string | null;
  backup_plan?: string | null;
};

export type TripBudget = {
  currency: string;
  user_budget?: number | null;
  hotel_budget_per_night?: number | null;
  estimated_total: number;
  hotel_total: number;
  status: string;
  hotel_recommendations: Array<{
    name: string;
    area: string;
    nightly_price: number;
    rating?: number | null;
    reason?: string | null;
    booking_hint?: string | null;
    is_estimated: boolean;
    source: string;
  }>;
  is_estimated: boolean;
};

export type TripPlan = {
  trip_title: string;
  destination: string;
  duration_days: number;
  travel_style: string[];
  summary: string;
  days: DayPlan[];
  budget: TripBudget;
  backup_plans: string[];
  warnings: string[];
  sources: string[];
};

export type TripRequestSnapshot = {
  origin?: string | null;
  destination?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  hotel_budget_per_night?: number | null;
  interests: string[];
  pace: string;
  special_requirements: string[];
};

export type TripPlanResponse = {
  trip_id?: string | null;
  thread_id?: string | null;
  need_clarification: boolean;
  clarification_question?: string | null;
  trip_request?: TripRequestSnapshot | null;
  trip_plan?: TripPlan | null;
  agent_steps: string[];
};

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string;
};

export type WSSessionSnapshot = {
  session_id: string;
  thread_id?: string | null;
  trip_id?: string | null;
  user_id?: string | null;
  awaiting_clarification: boolean;
  latest_trip_plan?: TripPlan | null;
  last_plan_response?: TripPlanResponse | null;
  message_history: ConversationMessage[];
};

export type WSServerMessage = {
  type:
    | "connected"
    | "snapshot"
    | "step_start"
    | "plan_result"
    | "plan_revised"
    | "assistant_message"
    | "error"
    | "pong";
  payload?: unknown;
};

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
