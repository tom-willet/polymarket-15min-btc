import json
import urllib.request

latest_path = open("logs/latest_next_market_run_path.txt", encoding="utf-8").read().strip()
outer = json.load(open(latest_path, encoding="utf-8"))
run = json.loads(outer["runner_stdout"])
slug = run["opened_full"]["polymarket_slug"]
url = f"https://gamma-api.polymarket.com/markets/slug/{slug}"

with urllib.request.urlopen(url, timeout=15) as response:
    payload = json.load(response)

market = payload[0] if isinstance(payload, list) and payload else payload

wanted_keys = [
    "slug",
    "question",
    "description",
    "marketType",
    "startDate",
    "startDateIso",
    "endDate",
    "endDateIso",
    "resolutionSource",
    "resolutionData",
    "outcomePrices",
    "bestBid",
    "bestAsk",
    "clobTokenIds",
    "conditionId",
]

summary = {k: market.get(k) for k in wanted_keys if k in market}
print(json.dumps(summary, indent=2))

for event in (market.get("events") or [])[:2]:
    if isinstance(event, dict):
        keep = {
            k: event.get(k)
            for k in ["id", "slug", "title", "description", "startDate", "endDate", "resolutionSource", "ticker"]
            if k in event
        }
        print("event:", json.dumps(keep, indent=2))
