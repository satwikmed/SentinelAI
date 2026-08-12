import { useEffect, useState } from "react";
import { fetchReviewQueue, resolveReview } from "../api";

type Item = {
  id: number;
  run_id: string;
  query: string;
  draft_response: string;
  reason: string;
  status: string;
  created_at: string | null;
};

export default function ReviewPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    try {
      const data = await fetchReviewQueue();
      setItems(data.items || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(id: number, status: "approved" | "rejected") {
    setBusy(id);
    try {
      await resolveReview(id, status);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resolve failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">Human review queue</h1>
      <p className="page-sub">
        Guardrail failures and low-confidence answers land here instead of silent pass/fail.
      </p>
      {error && <p className="error">{error}</p>}
      {items.length === 0 ? (
        <p className="empty">No pending items.</p>
      ) : (
        <ul className="review-list">
          {items.map((item) => (
            <li key={item.id} className="review-item">
              <p className="review-reason">{item.reason}</p>
              <p className="review-query">{item.query}</p>
              {item.draft_response && (
                <pre className="review-draft">{item.draft_response}</pre>
              )}
              <div className="review-actions">
                <button disabled={busy === item.id} onClick={() => act(item.id, "approved")}>
                  Approve
                </button>
                <button
                  className="secondary"
                  disabled={busy === item.id}
                  onClick={() => act(item.id, "rejected")}
                >
                  Reject
                </button>
                <span className="metric">run {item.run_id.slice(0, 8)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
