import pytest

from src.polymarket_agent.config import load_config


def test_load_config_requires_poly_ws_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_BTC_STREAM", "custom")
    monkeypatch.setenv("POLY_WS_URL", "")

    with pytest.raises(ValueError, match="POLY_WS_URL is required"):
        load_config()


def test_load_config_parses_expected_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_BTC_STREAM", "binance")
    monkeypatch.setenv("POLYMARKET_BTC_SYMBOL", "BTCUSDT")
    monkeypatch.setenv("POLYMARKET_BTC_WINDOW", "15m")
    monkeypatch.setenv("POLY_WS_URL", "")
    monkeypatch.setenv("POLY_MARKET_SYMBOL", "ETH")
    monkeypatch.setenv("ROUND_SECONDS", "600")
    monkeypatch.setenv("ACTIVATION_LEAD_SECONDS", "120")
    monkeypatch.setenv("WS_PING_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("AGENT_API_PORT", "9090")
    monkeypatch.setenv("MAX_TRADES_PER_ROUND", "3")
    monkeypatch.setenv("TRADE_COOLDOWN_SECONDS", "5")
    monkeypatch.setenv("POLYMARKET_WS_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_WS_URL", "wss://ws-subscriptions-clob.polymarket.com/ws/market")
    monkeypatch.setenv("POLYMARKET_MARKET_REFRESH_SECONDS", "14")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_LOGIN", "")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_PASSWORD", "")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_BASE_URL", "")
    monkeypatch.setenv("AGENT_TEST_MODE", "false")
    monkeypatch.setenv("TEST_MODE_ROUND_SECONDS", "120")
    monkeypatch.setenv("TEST_MODE_ACTIVATION_LEAD_SECONDS", "100")
    monkeypatch.setenv("POLYMARKET_MOVE_THRESHOLD_PCT", "3.0")
    monkeypatch.setenv("POLYMARKET_MOVE_MIN_ABS_DELTA", "0.03")
    monkeypatch.setenv("POLYMARKET_MOVE_LOG_COOLDOWN_SECONDS", "5.0")

    cfg = load_config()

    assert cfg.poly_ws_url is None
    assert cfg.btc_stream == "binance"
    assert cfg.btc_symbol == "BTCUSDT"
    assert cfg.btc_window == "15m"
    assert cfg.market_symbol == "ETH"
    assert cfg.round_seconds == 600
    assert cfg.activation_lead_seconds == 120
    assert cfg.ws_ping_interval_seconds == 10
    assert cfg.dry_run is False
    assert cfg.agent_api_port == 9090
    assert cfg.max_trades_per_round == 3
    assert cfg.trade_cooldown_seconds == 5
    assert cfg.polymarket_ws_enabled is True
    assert cfg.polymarket_ws_url == "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    assert cfg.polymarket_market_refresh_seconds == 14
    assert cfg.chainlink_candlestick_login is None
    assert cfg.chainlink_candlestick_password is None
    assert cfg.chainlink_candlestick_base_url is None
    assert cfg.agent_test_mode is False
    assert cfg.test_mode_round_seconds == 120
    assert cfg.test_mode_activation_lead_seconds == 100
    assert cfg.polymarket_move_threshold_pct == 3.0
    assert cfg.polymarket_move_min_abs_delta == 0.03
    assert cfg.polymarket_move_log_cooldown_seconds == 5.0


def test_load_config_requires_chainlink_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_BTC_STREAM", "chainlink")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_LOGIN", "")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_PASSWORD", "")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_BASE_URL", "")

    with pytest.raises(ValueError, match="CHAINLINK_CANDLESTICK_LOGIN is required"):
        load_config()


def test_load_config_allows_chainlink_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POLYMARKET_BTC_STREAM", "chainlink")
    monkeypatch.setenv("POLYMARKET_BTC_SYMBOL", "BTCUSD")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_LOGIN", "login")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_PASSWORD", "password")
    monkeypatch.setenv("CHAINLINK_CANDLESTICK_BASE_URL", "https://priceapi.dataengine.chain.link")

    cfg = load_config()

    assert cfg.btc_stream == "chainlink"
    assert cfg.btc_symbol == "BTCUSD"
    assert cfg.chainlink_candlestick_login == "login"
    assert cfg.chainlink_candlestick_password == "password"
    assert cfg.chainlink_candlestick_base_url == "https://priceapi.dataengine.chain.link"


def test_load_config_applies_test_mode_round_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TEST_MODE", "true")
    monkeypatch.setenv("ROUND_SECONDS", "900")
    monkeypatch.setenv("ACTIVATION_LEAD_SECONDS", "180")
    monkeypatch.setenv("TEST_MODE_ROUND_SECONDS", "60")
    monkeypatch.setenv("TEST_MODE_ACTIVATION_LEAD_SECONDS", "50")

    cfg = load_config()

    assert cfg.agent_test_mode is True
    assert cfg.round_seconds == 60
    assert cfg.activation_lead_seconds == 50
