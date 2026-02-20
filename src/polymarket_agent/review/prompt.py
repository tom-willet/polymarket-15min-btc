from __future__ import annotations

import hashlib
import json

SYSTEM_PROMPT_TEMPLATE = (
    "You are a trading performance reviewer. Return strict JSON analysis plus concise markdown. "
    "Advice only. Never suggest direct autonomous execution."
)

USER_PROMPT_TEMPLATE = """
Review version: {review_version}
Market: {market_slug} ({market_id})
Round close: {round_close_ts}

Payload:
{payload_json}

Return:
1) A JSON object with keys: summary, decision_assessment, risk_findings, parameter_suggestions, next_experiments
2) A markdown section titled 'Analysis' explaining findings.
""".strip()


def build_prompts(*, review_version: str, market_id: str, market_slug: str, round_close_ts: str, payload: dict) -> tuple[str, str]:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    user_prompt = USER_PROMPT_TEMPLATE.format(
        review_version=review_version,
        market_id=market_id,
        market_slug=market_slug,
        round_close_ts=round_close_ts,
        payload_json=payload_json,
    )
    return SYSTEM_PROMPT_TEMPLATE, user_prompt


def prompt_hash(system_prompt: str, user_prompt: str) -> str:
    digest = hashlib.sha256()
    digest.update(system_prompt.encode("utf-8"))
    digest.update(b"\n---\n")
    digest.update(user_prompt.encode("utf-8"))
    return digest.hexdigest()
