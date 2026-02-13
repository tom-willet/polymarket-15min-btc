from __future__ import annotations

import asyncio
import logging
import time
from uuid import uuid4

from .candles import CandleBuilder, parse_window_seconds
from .config import load_config
from .decision import DecisionRouter
from .executor import ActionExecutor
from .paper_trading import PaperTradeLogger, evaluate_paper_trade
from .polymarket import PolymarketOddsTracker
from .risk import RiskGuard, RiskLimits
from .scheduler import RoundScheduler
from .state import agent_state
from .ticker import TickerClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_live_price_feed(ticker: TickerClient) -> None:
    async for tick in ticker.stream_ticks():
        agent_state.set_tick(tick.price, tick.ts)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def should_log_material_event(
    current: dict,
    previous: dict | None,
    *,
    threshold_pct: float = 3.0,
    identity_keys: tuple[str, ...] = ("round_id", "action"),
    metric_keys: tuple[str, ...] = ("price", "polymarket_yes_price", "polymarket_no_price"),
) -> bool:
    if previous is None:
        return True

    for key in identity_keys:
        if current.get(key) != previous.get(key):
            return True

    threshold_ratio = threshold_pct / 100.0

    for key in metric_keys:
        current_value = _as_float(current.get(key))
        previous_value = _as_float(previous.get(key))

        if current_value is None:
            continue

        if previous_value is None:
            return True

        if previous_value == 0:
            if current_value != 0:
                return True
            continue

        if abs(current_value - previous_value) / abs(previous_value) >= threshold_ratio:
            return True

    return False


def should_log_discrete_event(
    current: dict,
    previous: dict | None,
    *,
    identity_keys: tuple[str, ...],
) -> bool:
    if previous is None:
        return True

    for key in identity_keys:
        if current.get(key) != previous.get(key):
            return True

    return False


async def run() -> None:
    config = load_config()

    scheduler = RoundScheduler(
        round_seconds=config.round_seconds,
        activation_lead_seconds=config.activation_lead_seconds,
    )
    decision_ticker = TickerClient(
        symbol=config.btc_symbol,
        stream=config.btc_stream,
        ws_url=config.poly_ws_url,
        ping_interval_seconds=config.ws_ping_interval_seconds,
        chainlink_login=config.chainlink_candlestick_login,
        chainlink_password=config.chainlink_candlestick_password,
        chainlink_base_url=config.chainlink_candlestick_base_url,
    )
    live_price_ticker = TickerClient(
        symbol=config.btc_symbol,
        stream=config.btc_stream,
        ws_url=config.poly_ws_url,
        ping_interval_seconds=config.ws_ping_interval_seconds,
        chainlink_login=config.chainlink_candlestick_login,
        chainlink_password=config.chainlink_candlestick_password,
        chainlink_base_url=config.chainlink_candlestick_base_url,
    )
    candle_builder = CandleBuilder(
        symbol=config.btc_symbol,
        window=config.btc_window,
        window_seconds=parse_window_seconds(config.btc_window),
    )
    decider = DecisionRouter()
    executor = ActionExecutor(dry_run=config.dry_run)
    risk_guard = RiskGuard(
        RiskLimits(
            max_trades_per_round=config.max_trades_per_round,
            trade_cooldown_seconds=config.trade_cooldown_seconds,
        )
    )

    last_round_executed: int | None = None
    agent_state.add_event(
        "info",
        "agent_started",
        {
            "symbol": config.market_symbol,
            "btc_stream": config.btc_stream,
            "btc_symbol": config.btc_symbol,
            "btc_window": config.btc_window,
        },
    )
    logger.info("[BTC WS] Window=%s", config.btc_window)

    if config.polymarket_ws_enabled:
        polymarket_tracker = PolymarketOddsTracker(
            ws_url=config.polymarket_ws_url,
            market_refresh_seconds=config.polymarket_market_refresh_seconds,
            move_threshold_pct=config.polymarket_move_threshold_pct,
            move_min_abs_delta=config.polymarket_move_min_abs_delta,
            move_log_cooldown_seconds=config.polymarket_move_log_cooldown_seconds,
        )
        asyncio.create_task(polymarket_tracker.run(agent_state))

    asyncio.create_task(run_live_price_feed(live_price_ticker))

    paper_logger = (
        PaperTradeLogger(config.paper_trade_log_path)
        if config.paper_trade_logging_enabled
        else None
    )
    open_paper_trades: list[dict] = []
    price_change_anchor: float | None = None
    last_logged_opportunity: dict | None = None
    last_logged_odds_filter_blocked: dict | None = None
    last_logged_risk_blocked: dict | None = None

    def log_paper_entry(entry: dict) -> None:
        agent_state.add_paper_trade_entry(entry)
        if paper_logger is not None:
            paper_logger.append(entry)

    def settle_round(round_id: int, close_price: float, close_ts: float) -> None:
        remaining: list[dict] = []
        for trade in open_paper_trades:
            if trade["round_id"] != round_id:
                remaining.append(trade)
                continue

            result = evaluate_paper_trade(
                action=trade["action"],
                entry_price=float(trade["entry_price"]),
                exit_price=close_price,
            )
            closing = {
                "type": "paper_trade_closed",
                "id": trade["id"],
                "round_id": round_id,
                "action": trade["action"],
                "strategy": trade.get("strategy"),
                "entry_price": trade["entry_price"],
                "exit_price": close_price,
                "entry_ts": trade["entry_ts"],
                "exit_ts": close_ts,
                "confidence": trade.get("confidence"),
                "edge_strength": trade.get("edge_strength"),
                "odds_alignment": trade.get("odds_alignment"),
                "polymarket_yes_price": trade.get("polymarket_yes_price"),
                "polymarket_no_price": trade.get("polymarket_no_price"),
                "outcome": result.outcome,
                "return_pct": round(result.return_pct, 4),
                "risk_assessment": trade.get("risk_assessment"),
            }
            log_paper_entry(closing)
            agent_state.add_event("info", "paper_trade_closed", closing)

        open_paper_trades.clear()
        open_paper_trades.extend(remaining)

    while True:
        window = await scheduler.wait_until_activation()
        if last_round_executed == window.round_id:
            await asyncio.sleep(0.2)
            continue

        agent_state.set_round(window.round_id, window.close_ts)
        agent_state.add_event("info", "round_activated", {"round_id": window.round_id})
        logger.info(
            "Round %s activated (now=%s, close=%s)",
            window.round_id,
            int(time.time()),
            int(window.close_ts),
        )

        async for tick in decision_ticker.stream_ticks():
            now_ts = time.time()
            agent_state.set_tick(tick.price, tick.ts)

            if price_change_anchor is None:
                price_change_anchor = tick.price
            elif price_change_anchor > 0:
                pct_change = ((tick.price - price_change_anchor) / price_change_anchor) * 100
                if abs(pct_change) >= 3.0:
                    entry = {
                        "type": "price_move_3pct",
                        "ts": now_ts,
                        "round_id": window.round_id,
                        "from_price": price_change_anchor,
                        "to_price": tick.price,
                        "pct_change": round(pct_change, 4),
                    }
                    log_paper_entry(entry)
                    agent_state.add_event("warning", "price_move_3pct", entry)
                    price_change_anchor = tick.price

            closed_candle = candle_builder.add_tick(tick)
            if closed_candle is not None:
                logger.info(
                    "[BTC WS] Candle %s: O=%.2f H=%.2f L=%.2f C=%.2f V=%.6f",
                    closed_candle.window,
                    closed_candle.open,
                    closed_candle.high,
                    closed_candle.low,
                    closed_candle.close,
                    closed_candle.volume,
                )
                agent_state.add_event(
                    "info",
                    "btc_candle_closed",
                    {
                        "symbol": closed_candle.symbol,
                        "window": closed_candle.window,
                        "start_ts": closed_candle.start_ts,
                        "end_ts": closed_candle.end_ts,
                        "open": closed_candle.open,
                        "high": closed_candle.high,
                        "low": closed_candle.low,
                        "close": closed_candle.close,
                        "volume": closed_candle.volume,
                    },
                )

            if now_ts >= window.close_ts:
                logger.info("Round %s closed; waiting for next window", window.round_id)
                settle_round(window.round_id, tick.price, tick.ts)
                agent_state.add_event("info", "round_closed", {"round_id": window.round_id})
                last_round_executed = window.round_id
                break

            decision = decider.on_tick(tick)
            if decision is None:
                continue

            action, context = decision
            odds_snapshot = agent_state.get_polymarket_odds_snapshot()
            yes_price = odds_snapshot.get("yes_price")
            no_price = odds_snapshot.get("no_price")
            confidence = float(context.get("confidence", 0.0))

            if isinstance(yes_price, (float, int)) and isinstance(no_price, (float, int)):
                supports_action = (
                    (action == "BUY_YES" and yes_price > no_price)
                    or (action == "BUY_NO" and no_price > yes_price)
                )

                if supports_action:
                    confidence = min(1.0, confidence + 0.05)
                    context["odds_alignment"] = "supportive"
                else:
                    confidence = max(0.0, confidence - 0.08)
                    context["odds_alignment"] = "against"

                context["confidence"] = round(confidence, 4)
                context["polymarket_yes_price"] = float(yes_price)
                context["polymarket_no_price"] = float(no_price)
                context["polymarket_slug"] = odds_snapshot.get("slug")

                if confidence < 0.55:
                    odds_filter_event = {
                        "action": action,
                        "round_id": window.round_id,
                        "confidence": round(confidence, 4),
                        "yes_price": float(yes_price),
                        "no_price": float(no_price),
                        "price": tick.price,
                    }
                    if should_log_material_event(
                        odds_filter_event,
                        last_logged_odds_filter_blocked,
                        metric_keys=("price", "yes_price", "no_price"),
                    ):
                        agent_state.add_event(
                            "warning",
                            "odds_filter_blocked",
                            odds_filter_event,
                        )
                        last_logged_odds_filter_blocked = odds_filter_event
                    continue

            opportunity_entry = {
                "type": "opportunity_detected",
                "ts": now_ts,
                "round_id": window.round_id,
                "action": action,
                "strategy": context.get("strategy"),
                "confidence": context.get("confidence"),
                "price": tick.price,
                "odds_alignment": context.get("odds_alignment", "unknown"),
                "polymarket_yes_price": context.get("polymarket_yes_price"),
                "polymarket_no_price": context.get("polymarket_no_price"),
                "edge_strength": (
                    abs(float(yes_price) - float(no_price))
                    if isinstance(yes_price, (float, int)) and isinstance(no_price, (float, int))
                    else None
                ),
            }
            if should_log_material_event(opportunity_entry, last_logged_opportunity):
                log_paper_entry(opportunity_entry)
                agent_state.add_event("info", "opportunity_detected", opportunity_entry)
                last_logged_opportunity = opportunity_entry

            context.update(
                {
                    "round_id": window.round_id,
                    "market_symbol": config.market_symbol,
                    "seconds_to_close": int(max(0, window.close_ts - now_ts)),
                }
            )

            if agent_state.is_kill_switch_enabled():
                risk_blocked_event = {
                    "action": action,
                    "round_id": window.round_id,
                    "reason": "kill_switch_enabled",
                }
                if should_log_discrete_event(
                    risk_blocked_event,
                    last_logged_risk_blocked,
                    identity_keys=("round_id", "action", "reason"),
                ):
                    agent_state.add_event(
                        "warning",
                        "risk_blocked",
                        risk_blocked_event,
                    )
                    last_logged_risk_blocked = risk_blocked_event
                continue

            risk_check = risk_guard.evaluate(round_id=window.round_id, now_ts=now_ts)
            if not risk_check.allowed:
                risk_blocked_event = {
                    "action": action,
                    "round_id": window.round_id,
                    "reason": risk_check.reason,
                }
                if should_log_discrete_event(
                    risk_blocked_event,
                    last_logged_risk_blocked,
                    identity_keys=("round_id", "action", "reason"),
                ):
                    agent_state.add_event(
                        "warning",
                        "risk_blocked",
                        risk_blocked_event,
                    )
                    last_logged_risk_blocked = risk_blocked_event
                continue

            agent_state.set_decision({"action": action, **context})
            agent_state.add_event("info", "decision", {"action": action, **context})
            await executor.execute(action, context)
            risk_guard.record_execution(round_id=window.round_id, now_ts=now_ts)

            trade_entry = {
                "type": "paper_trade_opened",
                "id": str(uuid4()),
                "ts": now_ts,
                "entry_ts": tick.ts,
                "round_id": window.round_id,
                "action": action,
                "strategy": context.get("strategy"),
                "confidence": context.get("confidence"),
                "entry_price": tick.price,
                "edge_strength": (
                    abs(float(yes_price) - float(no_price))
                    if isinstance(yes_price, (float, int)) and isinstance(no_price, (float, int))
                    else None
                ),
                "odds_alignment": context.get("odds_alignment", "unknown"),
                "polymarket_yes_price": context.get("polymarket_yes_price"),
                "polymarket_no_price": context.get("polymarket_no_price"),
                "risk_assessment": {
                    "kill_switch": False,
                    "risk_check": "ok",
                    "risk_reason": risk_check.reason,
                },
            }
            open_paper_trades.append(trade_entry)
            log_paper_entry(trade_entry)
            agent_state.add_event("info", "paper_trade_opened", trade_entry)


if __name__ == "__main__":
    asyncio.run(run())
