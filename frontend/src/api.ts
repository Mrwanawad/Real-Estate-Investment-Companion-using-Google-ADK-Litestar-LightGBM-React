import { parseSse } from "./sse";

export const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type ApiLanguage = "en" | "ar";

export interface Unit {
  code: string;
  project_name: string;
  area_name: string;
  type: string;
  bedrooms: number;
  bua_m2: number;
  price_egp: number | string;
  delivery_year: number;
  developer_tier: string;
  score: number;
  reasons: string[];
}
export interface FinancingOption {
  label: string;
  kind: string;
  upfront: string;
  avg_monthly_outflow: string;
  total_nominal: string;
  present_value: string;
}
export interface Quantiles {
  p10: number | string;
  p50: number | string;
  p90: number | string;
}
export interface Projection {
  unit_code: string;
  horizon_years: number;
  value: Quantiles;
  value_path: { year: number; p10: number; p50: number; p90: number }[];
  rent: { monthly_p50: number | string; gross_yield: number | string };
  irr: Quantiles;
  prob_loss: number | string;
  break_even_year: number | null;
}
export interface RiskItem {
  kind: string;
  level: "low" | "medium" | "high";
  explanation_en: string;
  explanation_ar: string;
}
export interface Citation {
  doc_id: string;
  title: string;
  snippet: string;
}

export type Artifact =
  | { kind: "shortlist"; data: { units: Unit[] } }
  | {
      kind: "financing";
      data: { unit_code: string; price_egp: string; cheapest_label: string; options: FinancingOption[] };
    }
  | { kind: "projection"; data: Projection }
  | { kind: "risks"; data: { items: RiskItem[] } }
  | { kind: "citations"; data: { items: Citation[] } }
  | { kind: "handoff"; data: { lead_id: string | number; status: string } }
  | { kind: "report"; data: { url_html: string; url_pdf: string | null } };

export type StreamEvent =
  | { type: "tool"; name: string; status: "started" | "finished" }
  | { type: "delta"; text: string }
  | { type: "artifact"; artifact: Artifact }
  | { type: "done" }
  | { type: "error"; message: string };

export async function createSession(language: ApiLanguage): Promise<string> {
  const res = await fetch(`${API_BASE}/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return ((await res.json()) as { session_id: string }).session_id;
}

function toStreamEvent(event: string, raw: string): StreamEvent | null {
  let data: Record<string, unknown>;
  try {
    data = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    return null;
  }
  switch (event) {
    case "tool":
      return { type: "tool", name: String(data.name), status: data.status === "finished" ? "finished" : "started" };
    case "delta":
      return { type: "delta", text: String(data.text ?? "") };
    case "artifact":
      return { type: "artifact", artifact: data as unknown as Artifact };
    case "done":
      return { type: "done" };
    case "error":
      return { type: "error", message: String(data.message ?? "") };
    default:
      return null;
  }
}

export async function streamMessage(
  sessionId: string,
  message: string,
  language: ApiLanguage,
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ message, language }),
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const emit = (text: string) => {
    const { events, rest } = parseSse(text);
    buffer = rest;
    for (const ev of events) {
      const parsed = toStreamEvent(ev.event, ev.data);
      if (parsed) onEvent(parsed);
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    emit(buffer + decoder.decode(value, { stream: true }));
  }
  emit(buffer + "\n\n");
}

export interface Lead {
  id: string | number;
  created_at: string;
  name: string | null;
  phone: string | null;
  email: string | null;
  goal: string | null;
  budget_egp: number | null;
  status: string;
  summary: string | null;
}

export class BrokerError extends Error {
  status: number;
  constructor(status: number) {
    super(`HTTP ${status}`);
    this.status = status;
  }
}

export const LEAD_STATUSES = ["new", "contacted", "qualified", "closed"] as const;

export async function listLeads(apiKey: string, status: string): Promise<Lead[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(`${API_BASE}/broker/leads${qs}`, { headers: { "X-API-Key": apiKey } });
  if (!res.ok) throw new BrokerError(res.status);
  const body = (await res.json()) as Lead[] | { items: Lead[] };
  return Array.isArray(body) ? body : body.items;
}

export async function updateLeadStatus(apiKey: string, id: string | number, status: string): Promise<void> {
  const res = await fetch(`${API_BASE}/broker/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new BrokerError(res.status);
}
