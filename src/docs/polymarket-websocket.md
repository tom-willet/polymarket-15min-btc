# BTC 15-Minute WebSocket Integration Setup

## Goal

Stream Polymarket CLOB updates (price, orderbook, trades) for the active 15-minute BTC up/down market.

## Prerequisites

- Node 22+
- `pnpm install` completed in repo root
- Extension built (`pnpm build`) or running in dev mode (`pnpm dev`)

## Environment

No extra environment variables are required for the Polymarket WebSocket.
The client connects to the default CLOB WS endpoint:

```
wss://ws-subscriptions-clob.polymarket.com/ws/market
```

## Start the Stream

From `extensions/polymarket`:

```bash
pnpm start
```

Expected log markers:

```
[Polymarket WS] Connected
[Agent] WebSocket connected
[Polymarket WS] Subscribed to 2 token(s)
```

## Verify Data Flow

The WebSocket streams market updates for the current 15m BTC up/down market. You should see price/orderbook activity in debug logs:

```
POLYMARKET_LOG_LEVEL=debug pnpm start
```

## Market Detection Flow

The agent automatically finds the active 15-minute BTC market and subscribes to its token IDs:

1. Detects the current 15m market slug via the Gamma API
2. Extracts the YES/NO token IDs
3. Subscribes to those token IDs on the CLOB WebSocket

Gamma API endpoint:

```
https://gamma-api.polymarket.com/markets/slug/{slug}
```

Slug format (15-minute windows):

```
btc-updown-15m-{unix_timestamp}
```

Expected log flow:

```
[BTC Tracker] Searching for BTC updown 15m markets...
[BTC Tracker] Found active market: ...
[Polymarket WS] Connected
[Polymarket WS] Subscribed to 2 token(s)
```

## Common Issues

### No WebSocket connection

- Check outbound network access.
- Verify the CLOB WS endpoint is reachable.

### No market updates

- Confirm the agent found an active 15m BTC market.
- Make sure the WebSocket subscribed to token IDs (see logs).

## Operational Notes

- The WebSocket streams Polymarket market data (not Binance BTC spot price).
- The agent continues trading even if the WebSocket is unavailable, but signal quality is reduced.

## Troubleshooting Checklist

- Confirm the process logs show `Connected` and `Subscribed`.
- Restart the agent after any configuration change.
