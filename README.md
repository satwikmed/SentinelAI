# SentinelAI

Enterprise GenAI governance and orchestration gateway — multi-agent routing across **OpenAI, Anthropic, and Gemini** with guardrails, evaluation gates, and a document intelligence copilot.

| | |
|---|---|
| **GitHub** | https://github.com/satwikmed/SentinelAI |
| **Fly (API + UI, permanent)** | https://sentinelai-satwik.fly.dev |
| **Vercel (UI)** | https://sentinelai-ochre-six.vercel.app |
| **Actions (CI gate)** | https://github.com/satwikmed/SentinelAI/actions/runs/31558066220 |
| **Local (UI+API)** | http://127.0.0.1:8000 |

---

## Architecture

```
React Copilot ──► FastAPI Gateway ──► Input Guardrails (PII / injection)
                                  ──► LangGraph
                                        Planner → Router → Executor ⇄ Verifier
                                  ──► Output Guardrails → Response | Human Review
Router → OpenAI | Anthropic | Gemini | Mock(demo)
Executor → ChromaDB RAG (seed enterprise policies)
+ OpenTelemetry spans across every node
+ Audit log + routing decision log + request metrics
```

**Orchestration patterns (explicit in code):**
1. **Planner–executor** — Planner decomposes; Executor runs RAG + generation  
2. **Reflection** — Verifier can send work back to Executor (capped retries)

Inspect any run: `GET /api/runs/{id}`

---

## What's built vs designed

| Capability | Status |
|------------|--------|
| Multi-agent LangGraph orchestration | **Built** |
| Multi-cloud routing (OpenAI / Anthropic / Gemini) | **Built** |
| Guardrails + audit + human review queue | **Built** |
| Eval suite + GitHub Actions CI gate + OTEL | **Built** |
| Document intelligence copilot (RAG + React) | **Built** |
| Conversational support copilot | Designed, not fully implemented |
| Workflow automation agent | Designed, not fully implemented |
| OCR / multimodal / LoRA fine-tuning | Out of scope |

---

## Quick start

```bash
# Backend
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # optional: add OPENAI/ANTHROPIC/GOOGLE keys
uvicorn app.main:app --reload --port 8000

# Frontend (optional separate; API also serves built UI from frontend/dist)
cd frontend && npm install && npm run build
# then restart API — open http://127.0.0.1:8000
```

Docker Compose:

```bash
docker compose up --build
# UI http://localhost:8080  API http://localhost:8000
```

Try: *“What is the data retention period after contract termination?”*

---

## Testing

```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v

# Eval CI gate (must pass)
python ../evals/run_eval.py

# Prove the gate can fail (deliberate)
PYTHONPATH=. pytest tests/test_eval_gate.py::test_eval_gate_fails_when_thresholds_raised -v

# Light load test
python ../scripts/load_test.py --base http://127.0.0.1:8000 --concurrency 5 --total 20
```

Coverage mapped to modules:
- `tests/test_orchestration.py` — node shapes, full graph, reflection retry cap  
- `tests/test_routing.py` — task/cost/fallback  
- `tests/test_guardrails.py` — PII, injection, review queue  
- `tests/test_eval_gate.py` — gate pass + deliberate fail + OTEL spans  
- `tests/test_document_copilot.py` — grounded Q&A + citations  

Prompt-injection defense is a **heuristic scorer**, not an adversarial-trained classifier (documented in API responses too).

---

## API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat` | Full gateway path |
| `GET /api/runs/{id}` | Checkpoint + audit inspection |
| `GET /api/routing/decisions` | Why each model was selected |
| `GET /api/audit` | Governance audit log |
| `GET /api/review` | Human-in-the-loop queue |
| `GET /api/metrics` | Latency, cost, faithfulness, relevance |

---

## Deploy

### GitHub
```bash
gh auth login
./scripts/push-github.sh
```

### Vercel (frontend)
Point `VITE_API_BASE` at a public API origin (Fly / Railway / Render / tunnel):

```bash
cd frontend
npx vercel login
VITE_API_BASE=https://YOUR_API_ORIGIN npx vercel --prod --yes
```

### Fly.io (API + UI all-in-one)
```bash
fly auth login
./scripts/deploy-fly.sh
```

### Infra artifacts
- Docker: `infra/docker/`
- Kubernetes (kind/minikube): `infra/k8s/deployment.yaml`
- Terraform (provider secrets): `infra/terraform/main.tf`

---

## Demo mode

If no provider keys are set, deterministic mock providers run the full pipeline end-to-end so reviewers can click around without accounts.

---

## Framework breadth

See `experiments/framework_comparison.py` — LangGraph chosen for typed state + checkpointing + reflection edges; CrewAI kept as an honest breadth comparison only.

---

## Resume bullets (only when true of this repo)

- Built a multi-agent AI gateway routing requests across OpenAI, Anthropic, and Gemini using LangGraph planner-executor and reflection patterns
- Implemented governance guardrails including PII detection (Presidio), prompt-injection defense, structured output validation, and human-in-the-loop escalation with full audit logging
- Built an evaluation and CI/CD pipeline with GitHub Actions gating deployments on faithfulness and relevance thresholds, with OpenTelemetry tracing across the agent pipeline
- Delivered a RAG-based enterprise document copilot with a React chat interface showing citations, confidence scores, and governance status per response

## License

MIT
