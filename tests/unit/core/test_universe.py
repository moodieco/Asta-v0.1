from asta.markets.crypto import universe as crypto
from asta.markets.forex import universe as forex
from asta.markets.stock import universe as stock


def test_crypto_normalisation_and_assets():
    assert crypto.normalize("btc/usdt") == "BTCUSDT"
    assert crypto.normalize("eth-usdt") == "ETHUSDT"
    assert crypto.base_asset("SOLUSDT") == "SOL"
    assert crypto.quote_asset("SOLUSDT") == "USDT"
    assert crypto.is_major("btc/usdt") is True
    assert crypto.is_major("PEPEUSDT") is False


def test_crypto_symbols_fall_back_to_defaults():
    assert crypto.symbols() == crypto.DEFAULT_SYMBOLS
    assert crypto.symbols(["btc/usdt", "eth/usdt"]) == ["BTCUSDT", "ETHUSDT"]


def test_forex_normalisation_and_pairs():
    assert forex.normalize("eurusd") == "EUR_USD"
    assert forex.normalize("gbp/jpy") == "GBP_JPY"
    assert forex.base_currency("EUR_USD") == "EUR"
    assert forex.quote_currency("USD_JPY") == "JPY"
    assert forex.is_jpy_pair("USDJPY") is True
    assert forex.is_major("EUR_USD") is True


def test_stock_normalisation():
    assert stock.normalize("$aapl") == "AAPL"
    assert stock.symbols(["nvda"]) == ["NVDA"]
    assert stock.symbols() == stock.DEFAULT_SYMBOLS
