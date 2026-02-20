from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
import time
from uuid import uuid4

import httpx

from .candles import CandleBuilder, parse_window_seconds
from .config import load_config
from .decision import DecisionRouter
from .executor import ActionExecutor
from .paper_trading import (
    PaperTradeLogger,
    PaperTradeSimulationConfig,
    apply_entry_execution,
    compute_effective_entry_slippage_bps,
    estimate_expected_edge_bps,
    estimate_total_cost_bps,
    evaluate_paper_trade,
)
from .polymarket import PolymarketOddsTracker
from .review.runtime import enqueue_market_close_review
from .risk import RiskGuard, RiskLimits
from .scheduler import RoundScheduler
from .state import agent_state
from .strategies import BTCUpdownConfig
from .ticker import TickerClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"


async def run_live_price_feed(ticker: TickerClient) -> None:
    async for tick in ticker.stream_ticks():
        agent_state.set_tick(tick.price, tick.ts)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_iso_utc(ts_value: float | None) -> str | None:
    if not isinstance(ts_value, (int, float)):
        return None
    return datetime.fromtimestamp(float(ts_value), tz=timezone.utc).isoformat()


def _normalize_chainlink_price(value: float) -> float:
    if abs(value) >= 1e12:
        return value / 1e18
    return value


def _model_prob_yes_from_action(action: str, confidence: float | None) -> float | None:
    if not isinstance(confidence, (int, float)):
        return None
    bounded_confidence = _clamp(float(confidence), 0.0, 1.0)
    if action == "BUY_YES":
        return bounded_confidence
    if action == "BUY_NO":
        return 1.0 - bounded_confidence
    return None


def _expected_outcome_from_reference(
    current_btc_price: float,
    price_to_beat_btc: float | None,
) -> str:
    if not isinstance(price_to_beat_btc, (int, float)):
        return "unknown"
    if current_btc_price > float(price_to_beat_btc):
        return "yes"
    if current_btc_price < float(price_to_beat_btc):
        return "no"
    return "push"


def _market_outcome_from_btc_prices(
    round_open_price: float,
    round_close_price: float,
) -> str:
    if round_close_price > round_open_price:
        return "yes"
    if round_close_price < round_open_price:
        return "no"
    return "push"


async def _fetch_round_open_price(symbol: str, round_start_ts: float, round_seconds: int) -> float | None:
    interval_map = {
        60: "1m",
        300: "5m",
        900: "15m",
        1800: "30m",
        3600: "1h",
    }
    interval = interval_map.get(round_seconds)
    if interval is None:
        return None

    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": int(round_start_ts * 1000),
        "limit": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(BINANCE_KLINE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or not payload:
                return None
            first = payload[0]
            if not isinstance(first, list) or len(first) < 2:
                return None
            return float(first[1])
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def _fetch_chainlink_round_open_price(
    *,
    symbol: str,
    round_start_ts: float,
    chainlink_base_url: str | None,
    chainlink_login: str | None,
    chainlink_password: str | None,
) -> float | None:
    if not chainlink_base_url or not chainlink_login or not chainlink_password:
        return None

    authorize_url = f"{chainlink_base_url.rstrip('/')}/api/v1/authorize"
    history_url = f"{chainlink_base_url.rstrip('/')}/api/v1/history/rows"
    start_epoch = int(round_start_ts)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            auth_response = await client.post(
                authorize_url,
                data={"login": chainlink_login, "password": chainlink_password},
            )
            auth_response.raise_for_status()
            auth_payload = auth_response.json()
            token = auth_payload.get("d", {}).get("access_token")
            if not isinstance(token, str) or not token:
                return None

            history_response = await client.get(
                history_url,
                params={
                    "symbol": symbol,
                    "resolution": "1m",
                    "from": start_epoch,
                    "to": start_epoch + 60,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            history_response.raise_for_status()
            history_payload = history_response.json()
            candles = history_payload.get("candles")
            if not isinstance(candles, list) or not candles:
                return None

            selected_candle = None
            for candle in candles:
                if isinstance(candle, list) and len(candle) >= 2:
                    candle_ts = candle[0]
                    if isinstance(candle_ts, (int, float)) and int(candle_ts) == start_epoch:
                        selected_candle = candle
                        break

            if selected_candle is None:
                for candle in candles:
                    if isinstance(candle, list) and len(candle) >= 2 and isinstance(candle[0], (int, float)):
                        selected_candle = candle
                        break

            if not isinstance(selected_candle, list) or len(selected_candle) < 2:
                return None

            open_price = float(selected_candle[1])
            return _normalize_chainlink_price(open_price)
    except (httpx.HTTPError, ValueError, TypeError):
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
    decider = DecisionRouter(
        strategy_mode=config.strategy_mode,
        btc_updown_shadow_mode=config.btc_updown_shadow_mode,
        btc_updown_live_enabled=config.btc_updown_live_enabled,
        btc_updown_config=BTCUpdownConfig(
            min_confidence_to_trade=config.btc_updown_min_confidence_to_trade,
            min_score_to_trade=config.btc_updown_min_score_to_trade,
            max_entry_price=config.btc_updown_max_entry_price,
            kelly_fraction=config.btc_updown_kelly_fraction,
            max_trade_size_usd=config.btc_updown_max_trade_size_usd,
            min_trade_size_usd=config.btc_updown_min_trade_size_usd,
        ),
    )
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
    paper_simulation = PaperTradeSimulationConfig(
        entry_slippage_bps=config.paper_entry_slippage_bps,
        dynamic_slippage_enabled=config.paper_dynamic_slippage_enabled,
        dynamic_slippage_edge_factor_bps=config.paper_dynamic_slippage_edge_factor_bps,
        dynamic_slippage_confidence_factor_bps=config.paper_dynamic_slippage_confidence_factor_bps,
        dynamic_slippage_expiry_factor_bps=config.paper_dynamic_slippage_expiry_factor_bps,
        max_slippage_bps=config.paper_max_slippage_bps,
        gas_fee_usd_per_side=config.paper_gas_fee_usd_per_side,
        adverse_selection_bps=config.paper_adverse_selection_bps,
        min_notional_usd=config.paper_min_notional_usd,
    )
    open_paper_trades: list[dict] = []
    daily_trade_totals: dict[str, dict[str, float | int]] = {}
    odds_history: deque[tuple[float, float, float]] = deque(maxlen=240)
    price_change_anchor: float | None = None
    last_logged_opportunity: dict | None = None
    last_logged_odds_filter_blocked: dict | None = None
    last_logged_risk_blocked: dict | None = None
    last_logged_net_edge_blocked: dict | None = None

    def log_paper_entry(entry: dict) -> None:
        agent_state.add_paper_trade_entry(entry)
        if paper_logger is not None:
            paper_logger.append(entry)

    def settle_round(
        round_id: int,
        close_btc_price: float,
        close_ts: float,
        round_open_btc_price: float | None,
    ) -> None:
        remaining: list[dict] = []

        def update_daily_totals(day_utc: str, pnl_usd: float, outcome: str) -> dict[str, float | int]:
            daily = daily_trade_totals.setdefault(
                day_utc,
                {
                    "closed_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "invalid": 0,
                    "realized_pnl_usd": 0.0,
                },
            )
            daily["closed_trades"] = int(daily["closed_trades"]) + 1
            if outcome == "win":
                daily["wins"] = int(daily["wins"]) + 1
            elif outcome == "loss":
                daily["losses"] = int(daily["losses"]) + 1
            elif outcome == "invalid":
                daily["invalid"] = int(daily["invalid"]) + 1

            daily["realized_pnl_usd"] = float(daily["realized_pnl_usd"]) + pnl_usd
            return daily

        day_utc = datetime.fromtimestamp(close_ts, tz=timezone.utc).strftime("%Y-%m-%d")

        if round_open_btc_price is None:
            for trade in open_paper_trades:
                if trade["round_id"] != round_id:
                    remaining.append(trade)
                    continue

                closing = {
                    "type": "paper_trade_closed",
                    "id": trade["id"],
                    "round_id": round_id,
                    "action": trade["action"],
                    "strategy": trade.get("strategy"),
                    "polymarket_slug": trade.get("polymarket_slug"),
                    "entry_price": trade["entry_price"],
                    "exit_price": trade["entry_price"],
                    "entry_ts": trade["entry_ts"],
                    "entry_ts_iso_utc": trade.get("entry_ts_iso_utc") or _to_iso_utc(trade.get("entry_ts")),
                    "exit_ts": close_ts,
                    "exit_ts_iso_utc": _to_iso_utc(close_ts),
                    "round_close_ts": trade.get("round_close_ts"),
                    "round_close_ts_iso_utc": trade.get("round_close_ts_iso_utc"),
                    "open_seconds_to_close": trade.get("open_seconds_to_close"),
                    "open_minutes_to_close": trade.get("open_minutes_to_close"),
                    "trade_duration_seconds": (
                        round(close_ts - float(trade["entry_ts"]), 3)
                        if isinstance(trade.get("entry_ts"), (int, float))
                        else None
                    ),
                    "trade_duration_minutes": (
                        round((close_ts - float(trade["entry_ts"])) / 60.0, 4)
                        if isinstance(trade.get("entry_ts"), (int, float))
                        else None
                    ),
                    "confidence": trade.get("confidence"),
                    "confidence_pct": trade.get("confidence_pct"),
                    "decision_score": trade.get("decision_score"),
                    "decision_reason": trade.get("decision_reason"),
                    "decision_signals": trade.get("decision_signals"),
                    "edge_strength": trade.get("edge_strength"),
                    "odds_alignment": trade.get("odds_alignment"),
                    "polymarket_yes_price": trade.get("polymarket_yes_price"),
                    "polymarket_no_price": trade.get("polymarket_no_price"),
                    "polymarket_price_sum": trade.get("polymarket_price_sum"),
                    "polymarket_price_gap": trade.get("polymarket_price_gap"),
                    "btc_price_at_decision": trade.get("btc_price_at_decision"),
                    "btc_price_at_entry": trade.get("btc_price_at_entry"),
                    "btc_price_to_beat": trade.get("btc_price_to_beat"),
                    "btc_price_to_beat_source": trade.get("btc_price_to_beat_source"),
                    "btc_price_at_close": close_btc_price,
                    "btc_move_abs_vs_price_to_beat": None,
                    "btc_move_pct_vs_price_to_beat": None,
                    "expected_outcome_if_closed_now": trade.get("expected_outcome_if_closed_now"),
                    "market_implied_prob_yes": trade.get("market_implied_prob_yes"),
                    "model_prob_yes_raw": trade.get("model_prob_yes_raw"),
                    "model_prob_yes_adjusted": trade.get("model_prob_yes_adjusted"),
                    "model_prob_no_adjusted": trade.get("model_prob_no_adjusted"),
                    "edge_vs_market_implied_prob": trade.get("edge_vs_market_implied_prob"),
                    "market_outcome": "unknown",
                    "btc_round_open_price": None,
                    "btc_round_close_price": close_btc_price,
                    "outcome": "invalid",
                    "stake_usd": float(trade.get("notional_usd", config.paper_trade_notional_usd)),
                    "return_pct": 0.0,
                    "gross_return_pct": 0.0,
                    "total_cost_pct": 0.0,
                    "gas_fees_usd": 0.0,
                    "adverse_selection_bps_applied": 0.0,
                    "gross_pnl_usd": 0.0,
                    "pnl_usd": 0.0,
                    "risk_assessment": trade.get("risk_assessment"),
                }
                daily = update_daily_totals(day_utc, 0.0, "invalid")
                closing.update(
                    {
                        "day_utc": day_utc,
                        "day_closed_trades": int(daily["closed_trades"]),
                        "day_wins": int(daily["wins"]),
                        "day_losses": int(daily["losses"]),
                        "day_invalid": int(daily["invalid"]),
                        "day_realized_pnl_usd": round(float(daily["realized_pnl_usd"]), 4),
                    }
                )
                log_paper_entry(closing)
                agent_state.add_event("warning", "paper_trade_closed_without_round_open", closing)

            open_paper_trades.clear()
            open_paper_trades.extend(remaining)
            return

        market_outcome = _market_outcome_from_btc_prices(round_open_btc_price, close_btc_price)

        for trade in open_paper_trades:
            if trade["round_id"] != round_id:
                remaining.append(trade)
                continue

            result = evaluate_paper_trade(
                action=trade["action"],
                entry_price=float(trade["entry_price"]),
                market_outcome=market_outcome,
                notional_usd=float(trade.get("notional_usd", config.paper_trade_notional_usd)),
                simulation=paper_simulation,
            )

            settlement_price = 1.0 if (
                (trade["action"] == "BUY_YES" and market_outcome == "yes")
                or (trade["action"] == "BUY_NO" and market_outcome == "no")
            ) else 0.0
            if market_outcome == "push":
                settlement_price = float(trade["entry_price"])

            price_to_beat_btc = trade.get("btc_price_to_beat")
            price_to_beat_source = trade.get("btc_price_to_beat_source")
            if not isinstance(price_to_beat_btc, (int, float)):
                price_to_beat_btc = round_open_btc_price
                if price_to_beat_source is None and isinstance(round_open_btc_price, (int, float)):
                    price_to_beat_source = "round_open_fallback"

            btc_move_abs_vs_price_to_beat = (
                close_btc_price - float(price_to_beat_btc)
                if isinstance(price_to_beat_btc, (int, float))
                else None
            )
            btc_move_pct_vs_price_to_beat = (
                ((close_btc_price - float(price_to_beat_btc)) / float(price_to_beat_btc)) * 100.0
                if isinstance(price_to_beat_btc, (int, float)) and float(price_to_beat_btc) != 0.0
                else None
            )

            closing = {
                "type": "paper_trade_closed",
                "id": trade["id"],
                "round_id": round_id,
                "action": trade["action"],
                "strategy": trade.get("strategy"),
                "polymarket_slug": trade.get("polymarket_slug"),
                "entry_price": trade["entry_price"],
                "exit_price": settlement_price,
                "entry_ts": trade["entry_ts"],
                "entry_ts_iso_utc": trade.get("entry_ts_iso_utc") or _to_iso_utc(trade.get("entry_ts")),
                "exit_ts": close_ts,
                "exit_ts_iso_utc": _to_iso_utc(close_ts),
                "round_close_ts": trade.get("round_close_ts"),
                "round_close_ts_iso_utc": trade.get("round_close_ts_iso_utc"),
                "open_seconds_to_close": trade.get("open_seconds_to_close"),
                "open_minutes_to_close": trade.get("open_minutes_to_close"),
                "trade_duration_seconds": (
                    round(close_ts - float(trade["entry_ts"]), 3)
                    if isinstance(trade.get("entry_ts"), (int, float))
                    else None
                ),
                "trade_duration_minutes": (
                    round((close_ts - float(trade["entry_ts"])) / 60.0, 4)
                    if isinstance(trade.get("entry_ts"), (int, float))
                    else None
                ),
                "confidence": trade.get("confidence"),
                "confidence_pct": trade.get("confidence_pct"),
                "decision_score": trade.get("decision_score"),
                "decision_reason": trade.get("decision_reason"),
                "decision_signals": trade.get("decision_signals"),
                "edge_strength": trade.get("edge_strength"),
                "odds_alignment": trade.get("odds_alignment"),
                "polymarket_yes_price": trade.get("polymarket_yes_price"),
                "polymarket_no_price": trade.get("polymarket_no_price"),
                "polymarket_price_sum": trade.get("polymarket_price_sum"),
                "polymarket_price_gap": trade.get("polymarket_price_gap"),
                "btc_price_at_decision": trade.get("btc_price_at_decision"),
                "btc_price_at_entry": trade.get("btc_price_at_entry"),
                "btc_price_to_beat": price_to_beat_btc,
                "btc_price_to_beat_source": price_to_beat_source,
                "btc_price_at_close": close_btc_price,
                "btc_move_abs_vs_price_to_beat": (
                    round(float(btc_move_abs_vs_price_to_beat), 6)
                    if isinstance(btc_move_abs_vs_price_to_beat, (int, float))
                    else None
                ),
                "btc_move_pct_vs_price_to_beat": (
                    round(float(btc_move_pct_vs_price_to_beat), 6)
                    if isinstance(btc_move_pct_vs_price_to_beat, (int, float))
                    else None
                ),
                "expected_outcome_if_closed_now": trade.get("expected_outcome_if_closed_now"),
                "market_implied_prob_yes": trade.get("market_implied_prob_yes"),
                "model_prob_yes_raw": trade.get("model_prob_yes_raw"),
                "model_prob_yes_adjusted": trade.get("model_prob_yes_adjusted"),
                "model_prob_no_adjusted": trade.get("model_prob_no_adjusted"),
                "edge_vs_market_implied_prob": trade.get("edge_vs_market_implied_prob"),
                "market_outcome": result.market_outcome,
                "btc_round_open_price": round_open_btc_price,
                "btc_round_close_price": close_btc_price,
                "outcome": result.outcome,
                "stake_usd": float(trade.get("notional_usd", config.paper_trade_notional_usd)),
                "return_pct": round(result.return_pct, 4),
                "gross_return_pct": round(result.gross_return_pct, 4),
                "total_cost_pct": round(result.total_cost_pct, 4),
                "gas_fees_usd": round(result.gas_fees_usd, 4),
                "adverse_selection_bps_applied": result.adverse_selection_bps_applied,
                "gross_pnl_usd": round(result.gross_pnl_usd, 4),
                "pnl_usd": round(result.pnl_usd, 4),
                "risk_assessment": trade.get("risk_assessment"),
            }
            daily = update_daily_totals(day_utc, float(result.pnl_usd), result.outcome)
            closing.update(
                {
                    "day_utc": day_utc,
                    "day_closed_trades": int(daily["closed_trades"]),
                    "day_wins": int(daily["wins"]),
                    "day_losses": int(daily["losses"]),
                    "day_invalid": int(daily["invalid"]),
                    "day_realized_pnl_usd": round(float(daily["realized_pnl_usd"]), 4),
                }
            )
            log_paper_entry(closing)
            agent_state.add_event("info", "paper_trade_closed", closing)

        open_paper_trades.clear()
        open_paper_trades.extend(remaining)

    while True:
        window = await scheduler.wait_until_activation()
        if last_round_executed == window.round_id:
            await asyncio.sleep(0.2)
            continue

        round_open_btc_price = await _fetch_round_open_price(
            symbol=config.btc_symbol,
            round_start_ts=window.start_ts,
            round_seconds=config.round_seconds,
        )
        round_open_btc_price_source: str | None = (
            "binance_klines" if isinstance(round_open_btc_price, (int, float)) else None
        )

        chainlink_open_price = await _fetch_chainlink_round_open_price(
            symbol=config.btc_symbol,
            round_start_ts=window.start_ts,
            chainlink_base_url=config.chainlink_candlestick_base_url,
            chainlink_login=config.chainlink_candlestick_login,
            chainlink_password=config.chainlink_candlestick_password,
        )
        if isinstance(chainlink_open_price, (int, float)):
            round_open_btc_price = chainlink_open_price
            round_open_btc_price_source = "chainlink_history_rows"

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

            if round_open_btc_price is None:
                round_open_btc_price = tick.price
                if round_open_btc_price_source is None:
                    round_open_btc_price_source = "live_tick_fallback"

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
                settle_round(window.round_id, tick.price, tick.ts, round_open_btc_price)
                agent_state.add_event("info", "round_closed", {"round_id": window.round_id})
                odds_snapshot = agent_state.get_polymarket_odds_snapshot()
                market_slug = str(odds_snapshot.get("slug") or config.market_symbol)
                await enqueue_market_close_review(
                    market_id=market_slug,
                    market_slug=market_slug,
                    round_id=window.round_id,
                    round_open_ts=datetime.fromtimestamp(window.start_ts, tz=timezone.utc),
                    round_close_ts=datetime.fromtimestamp(window.close_ts, tz=timezone.utc),
                )
                last_round_executed = window.round_id
                break

            odds_snapshot = agent_state.get_polymarket_odds_snapshot()
            yes_price = odds_snapshot.get("yes_price")
            no_price = odds_snapshot.get("no_price")

            orderbook_imbalance: float | None = None
            trade_momentum: float | None = None
            feed_divergence_bps: float | None = None

            if isinstance(yes_price, (float, int)) and isinstance(no_price, (float, int)):
                yes_value = float(yes_price)
                no_value = float(no_price)
                denom = yes_value + no_value
                if denom > 0:
                    orderbook_imbalance = _clamp((yes_value - no_value) / denom, -1.0, 1.0)

                odds_history.append((now_ts, yes_value, no_value))
                lookback_start = now_ts - 60.0
                baseline: tuple[float, float, float] | None = None
                for sample in odds_history:
                    if sample[0] >= lookback_start:
                        baseline = sample
                        break
                if baseline is None and odds_history:
                    baseline = odds_history[0]

                if baseline is not None:
                    _, yes_base, no_base = baseline
                    raw_momentum = (yes_value - yes_base) - (no_value - no_base)
                    trade_momentum = _clamp(raw_momentum * 5.0, -1.0, 1.0)

            binance_snapshot = agent_state.get_binance_price_snapshot()
            binance_price = binance_snapshot.get("price")
            if isinstance(binance_price, (float, int)) and float(binance_price) > 0:
                feed_divergence_bps = abs((tick.price - float(binance_price)) / float(binance_price)) * 10_000.0

            decision = decider.on_tick(
                tick,
                extra_state={
                    "seconds_to_close": int(max(0, window.close_ts - now_ts)),
                    "round_seconds": config.round_seconds,
                    "polymarket_yes_price": yes_price,
                    "polymarket_no_price": no_price,
                    "orderbook_imbalance": orderbook_imbalance,
                    "trade_momentum": trade_momentum,
                    "feed_divergence_bps": feed_divergence_bps,
                },
            )
            if decision is None:
                continue

            action, context = decision
            raw_confidence = float(context.get("confidence", 0.0))
            confidence = raw_confidence

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

                model_prob_yes_raw = _model_prob_yes_from_action(action, raw_confidence)
                model_prob_yes_adjusted = _model_prob_yes_from_action(action, confidence)
                market_implied_prob_yes = float(yes_price)
                context["model_prob_yes_raw"] = (
                    round(float(model_prob_yes_raw), 6)
                    if isinstance(model_prob_yes_raw, (int, float))
                    else None
                )
                context["model_prob_yes_adjusted"] = (
                    round(float(model_prob_yes_adjusted), 6)
                    if isinstance(model_prob_yes_adjusted, (int, float))
                    else None
                )
                context["model_prob_no_adjusted"] = (
                    round(1.0 - float(model_prob_yes_adjusted), 6)
                    if isinstance(model_prob_yes_adjusted, (int, float))
                    else None
                )
                context["market_implied_prob_yes"] = round(market_implied_prob_yes, 6)
                context["edge_vs_market_implied_prob"] = (
                    round(float(model_prob_yes_adjusted) - market_implied_prob_yes, 6)
                    if isinstance(model_prob_yes_adjusted, (int, float))
                    else None
                )

                odds_filter_min_confidence = (
                    config.btc_updown_min_confidence_to_trade
                    if config.strategy_mode == "btc_updown"
                    else 0.55
                )
                if confidence < odds_filter_min_confidence:
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

            edge_strength_value = (
                abs(float(yes_price) - float(no_price))
                if isinstance(yes_price, (float, int)) and isinstance(no_price, (float, int))
                else None
            )

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
                "edge_strength": edge_strength_value,
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

            effective_slippage_bps = compute_effective_entry_slippage_bps(
                paper_simulation,
                edge_strength=edge_strength_value,
                confidence=(
                    float(context.get("confidence"))
                    if isinstance(context.get("confidence"), (float, int))
                    else None
                ),
                seconds_to_close=int(max(0, window.close_ts - now_ts)),
                round_seconds=config.round_seconds,
            )

            expected_edge_bps = estimate_expected_edge_bps(
                edge_strength=edge_strength_value,
                confidence=(
                    float(context.get("confidence"))
                    if isinstance(context.get("confidence"), (float, int))
                    else None
                ),
                edge_strength_to_bps=config.paper_edge_strength_to_bps,
            )
            estimated_total_cost_bps = estimate_total_cost_bps(
                notional_usd=config.paper_trade_notional_usd,
                simulation=paper_simulation,
                effective_entry_slippage_bps=effective_slippage_bps,
            )
            estimated_net_edge_bps = expected_edge_bps - estimated_total_cost_bps

            if (
                config.paper_min_net_edge_bps > 0
                and estimated_net_edge_bps < config.paper_min_net_edge_bps
            ):
                net_edge_blocked_event = {
                    "action": action,
                    "round_id": window.round_id,
                    "reason": "net_edge_below_threshold",
                    "min_net_edge_bps": round(config.paper_min_net_edge_bps, 4),
                    "expected_edge_bps": round(expected_edge_bps, 4),
                    "estimated_total_cost_bps": round(estimated_total_cost_bps, 4),
                    "estimated_net_edge_bps": round(estimated_net_edge_bps, 4),
                    "effective_entry_slippage_bps": round(effective_slippage_bps, 4),
                    "price": tick.price,
                    "edge_strength": edge_strength_value,
                    "confidence": context.get("confidence"),
                }
                if should_log_material_event(
                    net_edge_blocked_event,
                    last_logged_net_edge_blocked,
                    metric_keys=(
                        "price",
                        "expected_edge_bps",
                        "estimated_total_cost_bps",
                        "estimated_net_edge_bps",
                    ),
                ):
                    agent_state.add_event(
                        "warning",
                        "net_edge_blocked",
                        net_edge_blocked_event,
                    )
                    last_logged_net_edge_blocked = net_edge_blocked_event
                continue

            market_entry_reference = (
                context.get("polymarket_yes_price")
                if action == "BUY_YES"
                else context.get("polymarket_no_price")
            )
            if not isinstance(market_entry_reference, (float, int)):
                risk_blocked_event = {
                    "action": action,
                    "round_id": window.round_id,
                    "reason": "missing_polymarket_entry_price",
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

            executed_entry_price = apply_entry_execution(
                action=action,
                reference_price=float(market_entry_reference),
                simulation=paper_simulation,
                slippage_bps=effective_slippage_bps,
            )

            trade_entry = {
                "type": "paper_trade_opened",
                "id": str(uuid4()),
                "ts": now_ts,
                "entry_ts": tick.ts,
                "entry_ts_iso_utc": _to_iso_utc(tick.ts),
                "round_id": window.round_id,
                "round_close_ts": window.close_ts,
                "round_close_ts_iso_utc": _to_iso_utc(window.close_ts),
                "open_seconds_to_close": int(max(0, window.close_ts - now_ts)),
                "open_minutes_to_close": round(max(0.0, window.close_ts - now_ts) / 60.0, 4),
                "action": action,
                "strategy": context.get("strategy"),
                "confidence": context.get("confidence"),
                "confidence_pct": (
                    round(float(context.get("confidence")) * 100.0, 4)
                    if isinstance(context.get("confidence"), (float, int))
                    else None
                ),
                "decision_score": context.get("score"),
                "decision_reason": context.get("reason"),
                "decision_signals": context.get("signals"),
                "btc_price_at_decision": tick.price,
                "btc_price_at_entry": tick.price,
                "btc_price_to_beat": round_open_btc_price,
                "btc_price_to_beat_source": round_open_btc_price_source,
                "expected_outcome_if_closed_now": _expected_outcome_from_reference(
                    current_btc_price=tick.price,
                    price_to_beat_btc=round_open_btc_price,
                ),
                "signal_price": float(market_entry_reference),
                "entry_price": executed_entry_price,
                "edge_strength": edge_strength_value,
                "notional_usd": config.paper_trade_notional_usd,
                "stake_usd": config.paper_trade_notional_usd,
                "entry_slippage_bps": paper_simulation.entry_slippage_bps,
                "effective_entry_slippage_bps": round(effective_slippage_bps, 4),
                "expected_edge_bps": round(expected_edge_bps, 4),
                "estimated_total_cost_bps": round(estimated_total_cost_bps, 4),
                "estimated_net_edge_bps": round(estimated_net_edge_bps, 4),
                "gas_fee_usd_per_side": paper_simulation.gas_fee_usd_per_side,
                "adverse_selection_bps": paper_simulation.adverse_selection_bps,
                "odds_alignment": context.get("odds_alignment", "unknown"),
                "polymarket_slug": context.get("polymarket_slug"),
                "polymarket_yes_price": context.get("polymarket_yes_price"),
                "polymarket_no_price": context.get("polymarket_no_price"),
                "market_implied_prob_yes": context.get("market_implied_prob_yes"),
                "model_prob_yes_raw": context.get("model_prob_yes_raw"),
                "model_prob_yes_adjusted": context.get("model_prob_yes_adjusted"),
                "model_prob_no_adjusted": context.get("model_prob_no_adjusted"),
                "edge_vs_market_implied_prob": context.get("edge_vs_market_implied_prob"),
                "polymarket_price_sum": (
                    round(
                        float(context.get("polymarket_yes_price"))
                        + float(context.get("polymarket_no_price")),
                        6,
                    )
                    if isinstance(context.get("polymarket_yes_price"), (float, int))
                    and isinstance(context.get("polymarket_no_price"), (float, int))
                    else None
                ),
                "polymarket_price_gap": (
                    round(
                        abs(
                            float(context.get("polymarket_yes_price"))
                            - float(context.get("polymarket_no_price"))
                        ),
                        6,
                    )
                    if isinstance(context.get("polymarket_yes_price"), (float, int))
                    and isinstance(context.get("polymarket_no_price"), (float, int))
                    else None
                ),
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
