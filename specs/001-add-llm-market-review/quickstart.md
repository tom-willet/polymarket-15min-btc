# Quickstart: End-of-Market LLM Review (v1)

## 1) Configure environment

Add the following to the agent `.env` (or deployment env file):

```bash
LLM_REVIEW_ENABLED=true
LLM_REVIEW_PROVIDER=openai
LLM_REVIEW_MODEL=gpt-5.2
LLM_REVIEW_TIMEOUT_SECONDS=20
LLM_REVIEW_MAX_RETRIES=2
LLM_REVIEW_VERSION=v1.0
LLM_REVIEW_MIN_ABS_SCORE=0.25
LLM_REVIEW_REQUIRE_TRADE=false
LLM_REVIEW_SAVE_INPUT_PAYLOAD=true
LLM_REVIEW_PAYLOAD_RETENTION_DAYS=30
```

Keep provider API keys in environment variables and never log them.

## 2) Start services

```bash
source .venv/bin/activate
python -m src.polymarket_agent.service
```

Optional dashboard:

```bash
cd web
npm install
npm run dev
```

## 3) Trigger a review path

Use a market close flow or replay endpoint after a closed market exists.

Replay example:

```bash
curl -X POST "http://127.0.0.1:8080/admin/reviews/replay" \
  -H "content-type: application/json" \
  -d '{
    "market_id": "<market-id>",
    "round_close_ts": "2026-02-18T15:15:00Z",
    "review_version": "v1.0"
  }'
```

## 4) Verify lifecycle and outputs

Latest review:

```bash
curl "http://127.0.0.1:8080/reviews/latest"
```

List reviews:

```bash
curl "http://127.0.0.1:8080/reviews?limit=20&status=succeeded"
```

Detail review:

```bash
curl "http://127.0.0.1:8080/reviews/<review-id>"
```

## 5) Expected behavior checks

- Review generation does not block market loop execution.
- Replays upsert the same logical record for `(market_id, round_close_ts, review_version)`.
- Failed LLM requests persist terminal `failed` state with reason.
- No-trade markets only generate reviews when high-signal criteria are met.
- Review endpoints are exposed only on trusted network surfaces.

## 6) Expected output examples

Replay accepted (`202`):

```json
{
  "accepted": true,
  "review_key": {
    "market_id": "btc-up-15m",
    "round_close_ts": "2026-02-18T15:15:00+00:00",
    "review_version": "v1.0"
  }
}
```

Review list (`200`):

```json
{
  "items": [
    {
      "id": "<uuid>",
      "market_id": "btc-up-15m",
      "market_slug": "btc-up-15m",
      "round_close_ts": "2026-02-18T15:15:00+00:00",
      "review_version": "v1.0",
      "status": "succeeded",
      "provider": "openai",
      "model": "gpt-5.2",
      "created_at": "<timestamp>",
      "updated_at": "<timestamp>"
    }
  ],
  "next_cursor": null
}
```
