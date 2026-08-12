import { FormEvent, useEffect, useRef, useState } from "react";
import { ChatResponse, fetchHealth, sendChat } from "../api";

type Message = {
  role: "user" | "assistant";
  content: string;
  meta?: ChatResponse;
};

const SUGGESTIONS = [
  "What is the data retention period after contract termination?",
  "How quickly must security incidents be reported to the SOC?",
  "How many PTO days can employees carry over?",
  "When is a DPA required for vendors?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => setDemoMode(!!h.demo_mode))
      .catch(() => setDemoMode(true));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await sendChat(q);
      const content = res.escalated
        ? res.draft_answer
          ? `Escalated for human review: ${res.escalation_reason}\n\nDraft held for review:\n${res.draft_answer}`
          : `Escalated for human review: ${res.escalation_reason}`
        : res.answer || "(empty response)";
      setMessages((m) => [...m, { role: "assistant", content, meta: res }]);
      setDemoMode(res.demo_mode);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-layout">
      <section className="hero-panel">
        <p className="eyebrow">Enterprise document intelligence</p>
        <h1 className="hero-title">SentinelAI</h1>
        <p className="hero-sub">
          Ask policy questions through the governance gateway — every answer is routed,
          guarded, evaluated, and auditable.
        </p>
        {demoMode && (
          <p className="demo-banner">
            Demo mode active (mock providers). Add OpenAI / Anthropic / Gemini keys for live
            multi-cloud routing.
          </p>
        )}
      </section>

      <section className="chat-panel">
        <div className="messages">
          {messages.length === 0 && (
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="suggestion" onClick={() => setInput(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <article key={i} className={`bubble ${m.role}`}>
              <p className="bubble-text">{m.content}</p>
              {m.meta && <ResponseMeta meta={m.meta} />}
            </article>
          ))}
          {loading && <div className="bubble assistant thinking">Running planner → router → executor → verifier…</div>}
          <div ref={bottomRef} />
        </div>

        {error && <p className="error">{error}</p>}

        <form className="composer" onSubmit={onSubmit}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about security, PTO, incidents, or vendors…"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </section>
    </div>
  );
}

function ResponseMeta({ meta }: { meta: ChatResponse }) {
  return (
    <div className="meta">
      <div className="meta-row">
        <span className={`badge ${meta.governance_passed ? "ok" : "warn"}`}>
          {meta.governance_passed ? "Passed governance" : "Governance hold"}
        </span>
        <span className="metric">Confidence {(meta.confidence * 100).toFixed(0)}%</span>
        {meta.route && (
          <span className="metric">
            {meta.route.provider}/{meta.route.model}
          </span>
        )}
        {typeof meta.metrics.latency_ms === "number" && (
          <span className="metric">{Math.round(meta.metrics.latency_ms as number)} ms</span>
        )}
      </div>
      {meta.verification && (
        <p className="meta-detail">
          Faithfulness {meta.verification.faithfulness.toFixed(2)} · Relevance{" "}
          {meta.verification.relevance.toFixed(2)}
        </p>
      )}
      {meta.route && <p className="meta-detail route-reason">{meta.route.reason}</p>}
      {meta.citations?.length > 0 && (
        <ul className="citations">
          {meta.citations.map((c, idx) => (
            <li key={idx}>
              <strong>{c.source}</strong> — {c.snippet}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
