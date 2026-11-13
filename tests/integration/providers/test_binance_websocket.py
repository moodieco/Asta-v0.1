import json

from asta.providers.crypto.binance import BinanceClient, parse_kline_message

MESSAGE = {
    "stream": "btcusdt@kline_1m",
    "data": {
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": 1704067200000,
            "T": 1704067259999,
            "i": "1m",
            "o": "42000.0",
            "h": "42100.0",
            "l": "41900.0",
            "c": "42050.0",
            "v": "12.5",
            "x": False,
        },
    },
}


def test_parse_kline_message_from_dict():
    event = parse_kline_message(MESSAGE)
    assert event is not None
    assert event.symbol == "BTCUSDT"
    assert event.interval == "1m"
    assert event.candle.close == 42050.0
    assert event.candle.volume == 12.5
    assert event.closed is False


def test_parse_kline_message_from_json_string():
    event = parse_kline_message(json.dumps(MESSAGE))
    assert event is not None and event.symbol == "BTCUSDT"


def test_parse_kline_message_ignores_other_events():
    assert parse_kline_message({"e": "aggTrade", "s": "BTCUSDT"}) is None
    assert parse_kline_message("not json") is None
    assert parse_kline_message({"e": "kline", "k": {"t": "bad"}}) is None


def test_stream_url_builds_combined_streams():
    url = BinanceClient.stream_url(["btcusdt", "ETHUSDT"], interval="15m")
    assert url.startswith("wss://stream.binance.com:9443/stream?streams=")
    assert "btcusdt@kline_15m" in url and "ethusdt@kline_15m" in url
