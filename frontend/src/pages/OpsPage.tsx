import { useEffect, useState } from "react";
import { fetchMetrics, fetchRoutingDecisions } from "../api";

export default function OpsPage() {
  const [decisions, setDecisions] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRoutingDecisions(), fetchMetrics()])
      .then(([d, m]) => {
        setDecisions(d.decisions || []);
        setMetrics(m.metrics || []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Load failed"));
  }, []);

  return (
    <div className="page">
      <h1 className="page-title">Ops dashboard</h1>
      <p className="page-sub">Routing decisions with reasons, plus per-request LLMOps metrics.</p>
      {error && <p className="error">{error}</p>}

      <h2 className="section-title">Why this model?</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>Model</th>
              <th>Task</th>
              <th>Reason</th>
              <th>Fallback</th>
            </tr>
          </thead>
          <tbody>
            {decisions.map((d) => (
              <tr key={d.id}>
                <td>{d.selected_provider}</td>
                <td>{d.selected_model}</td>
                <td>{d.task_type}</td>
                <td className="reason-cell">{d.reason}</td>
                <td>{d.fallback_used ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="section-title">Request metrics</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Latency</th>
              <th>Cost</th>
              <th>Faithfulness</th>
              <th>Relevance</th>
              <th>Guardrail</th>
              <th>Provider</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m) => (
              <tr key={m.run_id}>
                <td>{Math.round(m.latency_ms)} ms</td>
                <td>${Number(m.token_cost_usd).toFixed(5)}</td>
                <td>{Number(m.faithfulness).toFixed(2)}</td>
                <td>{Number(m.relevance).toFixed(2)}</td>
                <td>{m.guardrail_pass ? "pass" : "fail"}</td>
                <td>
                  {m.provider}/{m.model}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
