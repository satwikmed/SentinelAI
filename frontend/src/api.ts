export type ChatResponse = {
  run_id: string;
  answer: string | null;
  draft_answer: string | null;
  escalated: boolean;
  escalation_reason: string | null;
  governance_passed: boolean;
  confidence: number;
  citations: { source: string; snippet: string; score: number }[];
  plan: string[];
  route: {
    provider: string;
    model: string;
    task_type: string;
    reason: string;
  } | null;
  verification: {
    pass: boolean;
    faithfulness: number;
    relevance: number;
    issues: string[];
  } | null;
  metrics: Record<string, unknown>;
  node_trace: string[];
  demo_mode: boolean;
  input_guardrails?: Record<string, unknown>;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function sendChat(query: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchReviewQueue() {
  const res = await fetch(`${API_BASE}/api/review`);
  if (!res.ok) throw new Error("Failed to load review queue");
  return res.json();
}

export async function resolveReview(id: number, status: "approved" | "rejected", notes = "") {
  const res = await fetch(`${API_BASE}/api/review/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  if (!res.ok) throw new Error("Failed to resolve review");
  return res.json();
}

export async function fetchRoutingDecisions() {
  const res = await fetch(`${API_BASE}/api/routing/decisions`);
  if (!res.ok) throw new Error("Failed to load routing decisions");
  return res.json();
}

export async function fetchMetrics() {
  const res = await fetch(`${API_BASE}/api/metrics`);
  if (!res.ok) throw new Error("Failed to load metrics");
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("API unreachable");
  return res.json();
}
