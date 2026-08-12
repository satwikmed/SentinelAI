"""Module 4 — eval gate fails when thresholds are impossible."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evals" / "run_eval.py"


def test_eval_gate_passes_offline():
    proc = subprocess.run(
        [sys.executable, str(EVAL)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "EVAL GATE PASSED" in proc.stdout


def test_eval_gate_fails_when_thresholds_raised(tmp_path):
    """Deliberately make thresholds impossible — gate must fail (proves CI gating works)."""
    script = tmp_path / "fail_eval.py"
    script.write_text(
        f"""
import importlib.util, sys, json
spec = importlib.util.spec_from_file_location("run_eval", {str(EVAL)!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.THRESHOLDS = {{
    "min_avg_faithfulness": 0.99,
    "min_avg_relevance": 0.99,
    "min_pass_rate": 0.99,
}}
report = mod.run_offline()
print(json.dumps(report))
sys.exit(0 if report["gate_ok"] else 1)
""",
        encoding="utf-8",
    )
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert proc.returncode == 1, f"Gate should fail.\\nstdout={proc.stdout}\\nstderr={proc.stderr}"
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["gate_ok"] is False


def test_tracing_span_context_manager():
    from app.observability.tracing import init_tracing, span

    init_tracing()
    with span("planner", run_id="trace-test"):
        with span("router"):
            with span("executor"):
                with span("verifier"):
                    pass
    # If we got here without exception, OTEL pipeline accepted the waterfall spans
    assert True
