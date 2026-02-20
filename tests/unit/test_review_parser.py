import pytest

from src.polymarket_agent.review.parser import parse_review_output


def test_parser_accepts_json_block_and_markdown() -> None:
    raw = """
```json
{
  "summary": {"market_outcome": "yes", "pnl_usd": 1.2, "overall_grade": "A"},
  "decision_assessment": [],
  "risk_findings": ["none"],
  "parameter_suggestions": [],
  "next_experiments": ["x"]
}
```

Analysis

All good.
"""
    parsed = parse_review_output(raw)
    assert parsed.analysis_json.summary.market_outcome == "yes"
    assert "Analysis" in parsed.analysis_markdown


def test_parser_coerces_minimal_schema() -> None:
    raw = '{"summary": {"market_outcome": "yes"}}'
    parsed = parse_review_output(raw)
    assert parsed.analysis_json.summary.market_outcome == "yes"
    assert parsed.analysis_json.summary.overall_grade == "C"


def test_parser_fallback_uses_last_json_object() -> None:
    raw = """
Some preface text with a JSON-like object first:
{"aggregates":{"total_trades":0}}

And now the actual answer object:
{"summary":{"market_outcome":"no","pnl_usd":-1.1,"overall_grade":"C"},"decision_assessment":[],"risk_findings":[],"parameter_suggestions":[],"next_experiments":["tighten trigger thresholds"]}
"""
    parsed = parse_review_output(raw)
    assert parsed.analysis_json.summary.market_outcome == "no"


def test_parser_coerces_nonstandard_schema_shape() -> None:
        raw = """
{
    "summary": {"closed_trades": 0, "event_count": 12, "realized_pnl_usd": -1.1, "total_trades": 1},
    "decisions": [],
    "risk_events": {"assessment": "No critical risk events were identified."},
    "trade_parameters": "Reduce max position size by 10%.",
    "suggestions": ["Test tighter cooldown rules next session."]
}
"""
        parsed = parse_review_output(raw)
        assert parsed.analysis_json.summary.market_outcome == "unknown"
        assert parsed.analysis_json.summary.pnl_usd == -1.1
        assert parsed.analysis_json.summary.overall_grade == "C"
        assert parsed.analysis_json.parameter_suggestions
        assert parsed.analysis_json.next_experiments


def test_parser_coerces_object_list_schema_shape() -> None:
        raw = """
{
    "summary": {"market_outcome": "unknown", "pnl_usd": 0.0, "overall_grade": "C"},
    "decision_assessment": [],
    "risk_findings": [
        {"severity": "high", "category": "timing", "note": "late signal"}
    ],
    "parameter_suggestions": [
        {"area": "cooldown", "recommendation": "set to 10", "reason": "reduce missed entries"}
    ],
    "next_experiments": [
        {"name": "window study", "hypothesis": "better timing"}
    ]
}
"""
        parsed = parse_review_output(raw)
        assert parsed.analysis_json.risk_findings
        assert parsed.analysis_json.parameter_suggestions[0].name == "cooldown"
        assert parsed.analysis_json.next_experiments[0].startswith("window study")
