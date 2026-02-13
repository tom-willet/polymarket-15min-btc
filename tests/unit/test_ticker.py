from src.polymarket_agent.ticker import TickerClient


def test_binance_parser_parses_trade_payload() -> None:
    client = TickerClient(symbol="BTCUSDT", stream="binance")
    payload = '{"e":"trade","E":1749721156170,"s":"BTCUSDT","p":"106572.99","q":"0.00059","T":1749721156168}'

    tick = client._parse(payload)

    assert tick is not None
    assert tick.symbol == "BTCUSDT"
    assert tick.price == 106572.99
    assert tick.size == 0.00059
    assert tick.ts == 1749721156.168


def test_resolve_ws_url_for_binance() -> None:
    client = TickerClient(symbol="BTCUSDT", stream="binance")

    assert client._resolve_ws_url() == "wss://stream.binance.com:9443/ws/btcusdt@trade"


def test_chainlink_parser_parses_trade_payload() -> None:
    client = TickerClient(symbol="BTCUSD", stream="chainlink")
    payload = '{"f":"t","i":"BTCUSD","p":65765.12,"t":1770935000,"s":1}'

    tick = client._parse(payload)

    assert tick is not None
    assert tick.symbol == "BTCUSD"
    assert tick.price == 65765.12
    assert tick.ts == 1770935000.0
    assert tick.size == 1.0


def test_chainlink_parser_ignores_heartbeat() -> None:
    client = TickerClient(symbol="BTCUSD", stream="chainlink")

    tick = client._parse('{"heartbeat":1770935005}')

    assert tick is None


def test_chainlink_parser_normalizes_scaled_price_payload() -> None:
    client = TickerClient(symbol="BTCUSD", stream="chainlink")
    payload = '{"f":"t","i":"BTCUSD","p":6.59462722084066e+22,"t":1770935596,"s":1}'

    tick = client._parse(payload)

    assert tick is not None
    assert tick.symbol == "BTCUSD"
    assert round(tick.price, 2) == 65946.27
