"""Input/output governance guardrails.

- PII detection via Microsoft Presidio (with regex fallback if spaCy model missing)
- Prompt-injection detection via heuristic scoring (honestly: heuristic, not SOTA)
- Output policy validation + Pydantic structured checks
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

# --- Prompt injection heuristic (rule-based, not a trained classifier) ---
_INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", 0.85),
    (r"disregard\s+(your|the)\s+(system|safety)\s+(prompt|rules)", 0.9),
    (r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)", 0.9),
    (r"reveal\s+(your|the)\s+(system\s+)?prompt", 0.75),
    (r"do\s+not\s+follow\s+(your|any)\s+(rules|policies)", 0.8),
    (r"<\|?\s*system\s*\|?>", 0.7),
    (r"sudo\s+mode", 0.6),
    (r"developer\s+mode\s+enabled", 0.65),
]


@dataclass
class GuardrailResult:
    passed: bool
    findings: list[dict[str, Any]] = field(default_factory=list)
    redacted_text: str = ""
    score: float = 0.0


class CopilotAnswerSchema(BaseModel):
    """Structured output validation for copilot responses."""

    answer: str = Field(min_length=1, max_length=12000)
    confidence: float = Field(ge=0.0, le=1.0)


_presidio_analyzer = None
_presidio_anonymizer = None
_presidio_ready = False


def _init_presidio() -> bool:
    global _presidio_analyzer, _presidio_anonymizer, _presidio_ready
    if _presidio_ready:
        return _presidio_analyzer is not None
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        # Use the small model we bake into the image — never auto-download lg at runtime.
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        _presidio_analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        _presidio_anonymizer = AnonymizerEngine()
        _presidio_ready = True
        return True
    except Exception:  # noqa: BLE001
        _presidio_ready = True
        _presidio_analyzer = None
        _presidio_anonymizer = None
        return False


_PII_REGEX = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
]


def detect_pii(text: str) -> GuardrailResult:
    findings: list[dict[str, Any]] = []
    redacted = text

    if _init_presidio() and _presidio_analyzer and _presidio_anonymizer:
        try:
            results = _presidio_analyzer.analyze(text=text, language="en")
            for r in results:
                findings.append(
                    {
                        "type": r.entity_type,
                        "start": r.start,
                        "end": r.end,
                        "score": r.score,
                        "engine": "presidio",
                    }
                )
            if results:
                from presidio_anonymizer.entities import OperatorConfig

                anon = _presidio_anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})},
                )
                redacted = anon.text
            return GuardrailResult(
                passed=len(findings) == 0,
                findings=findings,
                redacted_text=redacted,
                score=max((f["score"] for f in findings), default=0.0),
            )
        except Exception:  # noqa: BLE001
            pass

    # Regex fallback
    for label, pattern in _PII_REGEX:
        for m in pattern.finditer(text):
            findings.append(
                {
                    "type": label,
                    "start": m.start(),
                    "end": m.end(),
                    "score": 0.8,
                    "engine": "regex",
                }
            )
            redacted = redacted.replace(m.group(0), f"[REDACTED_{label}]")

    return GuardrailResult(
        passed=len(findings) == 0,
        findings=findings,
        redacted_text=redacted,
        score=0.8 if findings else 0.0,
    )


def detect_prompt_injection(text: str) -> GuardrailResult:
    """Heuristic prompt-injection scorer — not state-of-the-art; documented as such."""
    score = 0.0
    findings: list[dict[str, Any]] = []
    lower = text.lower()
    for pattern, weight in _INJECTION_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            score = max(score, weight)
            findings.append({"pattern": pattern, "weight": weight, "engine": "heuristic"})
    from app.config import get_settings

    threshold = get_settings().prompt_injection_threshold
    return GuardrailResult(
        passed=score < threshold,
        findings=findings,
        redacted_text=text,
        score=score,
    )


_DISALLOWED_OUTPUT = [
    (r"\bkill\s+yourself\b", "self_harm"),
    (r"\bhow\s+to\s+make\s+a\s+bomb\b", "weapons"),
    (r"\bra[ck]ist\b", "hate"),
]


def validate_output_policy(text: str) -> GuardrailResult:
    findings: list[dict[str, Any]] = []
    for pattern, category in _DISALLOWED_OUTPUT:
        if re.search(pattern, text, re.IGNORECASE):
            findings.append({"category": category, "pattern": pattern})
    return GuardrailResult(
        passed=len(findings) == 0,
        findings=findings,
        redacted_text=text,
        score=1.0 if findings else 0.0,
    )


def validate_structured_output(answer: str, confidence: float) -> GuardrailResult:
    try:
        CopilotAnswerSchema(answer=answer, confidence=confidence)
        return GuardrailResult(passed=True, redacted_text=answer)
    except ValidationError as exc:
        return GuardrailResult(
            passed=False,
            findings=[{"error": str(exc), "engine": "pydantic"}],
            redacted_text=answer,
            score=1.0,
        )


def run_input_guardrails(text: str) -> dict[str, Any]:
    pii = detect_pii(text)
    injection = detect_prompt_injection(text)
    # Use redacted text for downstream if PII found (still allow query after redaction)
    blocked = not injection.passed
    return {
        "passed": not blocked,
        "blocked": blocked,
        "pii": {
            "passed": pii.passed,
            "findings": pii.findings,
            "redacted_text": pii.redacted_text,
        },
        "prompt_injection": {
            "passed": injection.passed,
            "score": injection.score,
            "findings": injection.findings,
            "note": "Heuristic rule-based scorer, not a trained adversarial classifier",
        },
        "sanitized_query": pii.redacted_text if not pii.passed else text,
    }


def run_output_guardrails(answer: str, confidence: float) -> dict[str, Any]:
    policy = validate_output_policy(answer)
    structured = validate_structured_output(answer, confidence)
    passed = policy.passed and structured.passed
    return {
        "passed": passed,
        "policy": {"passed": policy.passed, "findings": policy.findings},
        "structured": {"passed": structured.passed, "findings": structured.findings},
    }
