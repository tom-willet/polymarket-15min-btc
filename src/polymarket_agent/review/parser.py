from __future__ import annotations

import json
import re

from .models import ParsedReviewOutput, ReviewAnalysisJson

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_last_json_object(raw_text: str) -> dict:
    # Walk backwards to find the last balanced JSON object.
    end = raw_text.rfind("}")
    while end != -1:
        depth = 0
        in_string = False
        escape = False
        start = -1

        for idx in range(end, -1, -1):
            ch = raw_text[idx]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "}":
                depth += 1
                continue

            if ch == "{":
                depth -= 1
                if depth == 0:
                    start = idx
                    break

        if start != -1:
            candidate = raw_text[start : end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        end = raw_text.rfind("}", 0, end)

    raise ValueError("missing JSON object in LLM response")


def _extract_json(raw_text: str) -> dict:
    match = _JSON_BLOCK_RE.search(raw_text)
    if match:
        return json.loads(match.group(1))
    return _extract_last_json_object(raw_text)


def _flatten_string_values(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_string_values(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_flatten_string_values(item))
        return out
    return []


def _coerce_analysis_schema(parsed: dict) -> dict:
    data = dict(parsed)

    summary_raw = data.get("summary")
    if not isinstance(summary_raw, dict):
        summary_raw = {}
    market_outcome = summary_raw.get("market_outcome")
    if market_outcome not in {"yes", "no", "unknown"}:
        market_outcome = "unknown"

    pnl_usd = summary_raw.get("pnl_usd")
    if not isinstance(pnl_usd, (int, float)):
        pnl_usd = summary_raw.get("realized_pnl_usd", 0.0)
    if not isinstance(pnl_usd, (int, float)):
        pnl_usd = 0.0

    overall_grade = summary_raw.get("overall_grade")
    if overall_grade not in {"A", "B", "C", "D", "F"}:
        overall_grade = "C"

    decision_assessment = data.get("decision_assessment")
    if not isinstance(decision_assessment, list):
        alt = data.get("decisions")
        if isinstance(alt, list):
            decision_assessment = [
                {
                    "decision_id": str(item.get("decision_id", f"decision-{idx+1}")) if isinstance(item, dict) else f"decision-{idx+1}",
                    "verdict": str(item.get("verdict", "review")) if isinstance(item, dict) else "review",
                    "reason": str(item.get("reason", "No reason provided.")) if isinstance(item, dict) else "No reason provided.",
                    "counterfactual": str(item.get("counterfactual", "N/A")) if isinstance(item, dict) else "N/A",
                }
                for idx, item in enumerate(alt)
            ]
        else:
            decision_assessment = []

    risk_findings = data.get("risk_findings")
    if isinstance(risk_findings, list):
        normalized_risks: list[str] = []
        for item in risk_findings:
            if isinstance(item, str):
                if item.strip():
                    normalized_risks.append(item.strip())
                continue
            if isinstance(item, dict):
                parts = _flatten_string_values(item)
                if parts:
                    normalized_risks.append(" | ".join(parts[:3]))
        risk_findings = normalized_risks
    if not isinstance(risk_findings, list):
        risk_findings = _flatten_string_values(data.get("risk_findings") or data.get("risk") or data.get("risk_events"))

    parameter_suggestions = data.get("parameter_suggestions")
    if isinstance(parameter_suggestions, list):
        normalized_suggestions: list[dict] = []
        for idx, item in enumerate(parameter_suggestions):
            if isinstance(item, dict):
                name = item.get("name")
                if not isinstance(name, str) or not name.strip():
                    name = item.get("area") if isinstance(item.get("area"), str) else f"suggestion_{idx+1}"

                suggested_value = item.get("suggested_value")
                if not isinstance(suggested_value, str) or not suggested_value.strip():
                    suggested_value = item.get("recommendation") if isinstance(item.get("recommendation"), str) else "Review recommendation"

                rationale = item.get("rationale")
                if not isinstance(rationale, str) or not rationale.strip():
                    rationale = item.get("reason") if isinstance(item.get("reason"), str) else "Coerced from non-standard model output."

                confidence = item.get("confidence")
                if not isinstance(confidence, (int, float)):
                    confidence = 0.5

                normalized_suggestions.append(
                    {
                        "name": str(name).strip(),
                        "suggested_value": str(suggested_value).strip(),
                        "rationale": str(rationale).strip(),
                        "confidence": max(0.0, min(1.0, float(confidence))),
                    }
                )
            elif isinstance(item, str) and item.strip():
                normalized_suggestions.append(
                    {
                        "name": f"suggestion_{idx+1}",
                        "suggested_value": item.strip(),
                        "rationale": "Coerced from non-standard model output.",
                        "confidence": 0.5,
                    }
                )
        parameter_suggestions = normalized_suggestions
    if not isinstance(parameter_suggestions, list):
        raw = data.get("parameter_suggestions") or data.get("trade_parameters") or data.get("suggestions")
        strings = _flatten_string_values(raw)
        parameter_suggestions = [
            {
                "name": f"suggestion_{idx+1}",
                "suggested_value": text,
                "rationale": "Coerced from non-standard model output.",
                "confidence": 0.5,
            }
            for idx, text in enumerate(strings)
        ]

    next_experiments = data.get("next_experiments")
    if isinstance(next_experiments, list):
        normalized_experiments: list[str] = []
        for item in next_experiments:
            if isinstance(item, str) and item.strip():
                normalized_experiments.append(item.strip())
                continue
            if isinstance(item, dict):
                name = item.get("name") if isinstance(item.get("name"), str) else None
                hypothesis = item.get("hypothesis") if isinstance(item.get("hypothesis"), str) else None
                combined = " - ".join([p for p in [name, hypothesis] if p])
                if combined:
                    normalized_experiments.append(combined)
                    continue
                parts = _flatten_string_values(item)
                if parts:
                    normalized_experiments.append(" | ".join(parts[:3]))
        next_experiments = normalized_experiments
    if not isinstance(next_experiments, list):
        next_experiments = _flatten_string_values(data.get("next_experiments") or data.get("experiments") or data.get("suggestions"))

    return {
        "summary": {
            "market_outcome": market_outcome,
            "pnl_usd": float(pnl_usd),
            "overall_grade": overall_grade,
        },
        "decision_assessment": decision_assessment,
        "risk_findings": risk_findings,
        "parameter_suggestions": parameter_suggestions,
        "next_experiments": next_experiments,
    }


def parse_review_output(raw_text: str) -> ParsedReviewOutput:
    parsed = _extract_json(raw_text)
    analysis = ReviewAnalysisJson.model_validate(_coerce_analysis_schema(parsed))

    markdown = ""
    if "```" in raw_text:
        markdown = raw_text.split("```")[-1].strip()
    if not markdown:
        markdown = "Analysis\n\nStructured review generated."

    return ParsedReviewOutput(
        analysis_json=analysis,
        analysis_markdown=markdown,
    )
