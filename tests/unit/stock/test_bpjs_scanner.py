"""BPJS SCANNER (``STS003_IDX_LIQUIDITY``): IDX intraday liquidity + momentum.

Synthetic 5m bars in Asia/Jakarta: two full previous sessions (so the previous
close is available) plus today's bars up to a fixed ``now``.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from asta.core.signal_model import Candle, Market, ScanContext, SignalType

JKT = ZoneInfo("Asia/Jakarta")
#: Tuesday 2026-11-17, 10:00 WIB - inside the 09:30-15:45 scan window.
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=JKT)

SCANNER_ID = "STS003_IDX_LIQUIDITY"


def _bar(timestamp, price, volume):
    return Candle(
        timestamp=timestamp,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=volume,
    )


def session_bars(day, price, volume=1_000.0):
    """One IDX session of 5m bars: 09:00-11:55 and 13:30-15:55 (no lunch)."""
    bars = []
    for start_hour, start_minute, end_hour, end_minute in ((9, 0, 11, 55), (13, 30, 15, 55)):
        stamp = datetime.combine(day, time(start_hour, start_minute), tzinfo=JKT)
        end = datetime.combine(day, time(end_hour, end_minute), tzinfo=JKT)
        while stamp <= end:
            bars.append(_bar(stamp, price, volume))
            stamp += timedelta(minutes=5)
    return bars


def idx_context(
    now=NOW,
    prev_close=1000.0,
    price=1010.0,
    per_bar_volume=300_000.0,
    today_bars=12,
    symbol="BBCA.JK",
):
    candles = session_bars(now.date() - timedelta(days=2), prev_close)
    candles += session_bars(now.date() - timedelta(days=1), prev_close)
    start = datetime.combine(now.date(), time(9, 0), tzinfo=JKT)
    for index in range(today_bars):
        stamp = start + timedelta(minutes=5 * index)
        if stamp > now:
            break
        candles.append(_bar(stamp, price, per_bar_volume))
    return ScanContext(
        market=Market.STOCK,
        symbol=symbol,
        timeframe="5m",
        candles=candles,
        now=now,
    )


# -- identity ---------------------------------------------------------------
def test_bpjs_is_wired_as_a_5m_stock_scanner(scanners):
    scanner = scanners[SCANNER_ID]
    assert scanner.name == "BPJS SCANNER"
    assert scanner.market is Market.STOCK
    assert scanner.timeframe == "5m"
    assert scanner.enabled


def test_bpjs_defaults_to_the_whole_idx_universe(scanners):
    symbols = scanners[SCANNER_ID].symbols
    assert len(symbols) > 900
    assert all(symbol.endswith(".JK") for symbol in symbols)
    assert "BBCA.JK" in symbols


# -- the signal -------------------------------------------------------------
def test_bpjs_fires_on_a_liquid_up_name(scanners):
    scanner = scanners[SCANNER_ID]
    signals = scanner.scan(idx_context())

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.price == 1010.0
    # tick-rounded: 1010 -> tick 5, stop floors to 985, target ceils to 1065
    assert signal.stop_loss == 985.0
    assert signal.take_profit == 1065.0
    assert signal.levels_source == "structure"
    assert signal.risk_reward == 2.2
    assert signal.risk_pct == 2.475
    # time exit before the close, not a bar count
    assert signal.expires_at == datetime(2026, 11, 17, 15, 45, tzinfo=JKT)
    assert signal.indicators["volume_today"] == 3_600_000.0
    assert signal.indicators["value_today"] == 3_636_000_000.0
    assert signal.indicators["change_pct"] == 1.0
    assert signal.metadata["foreign_net"] is None
    assert "Net Foreign Buy/Sell" in signal.metadata["foreign_note"]
    assert "perlu cek ulang di Net Foreign Buy/Sell, harus diatas 0" in signal.reason
    # one alert per symbol per session
    assert signal.metadata["dedup_window_seconds"] == 25_200


def test_bpjs_scans_everything_when_the_batch_covers_the_universe(scanners):
    scanner = scanners[SCANNER_ID]
    universe = ["S{}".format(index) for index in range(10)]

    # batch_size 120 > 10 symbols: no rotation, one pass covers it all
    assert scanner.pick_symbols(universe) == universe
    assert scanner.pick_symbols(universe) == universe


def test_bpjs_rotation_wraps_around():
    from asta.core.scanner_base import ScannerConfig
    from asta.markets.stock.scanners.STS003_IDX_LIQUIDITY.scanner import IndexLiquidityScanner

    scanner = IndexLiquidityScanner(
        ScannerConfig(
            id=SCANNER_ID,
            name="BPJS SCANNER",
            market=Market.STOCK,
            timeframe="5m",
            params={"batch_size": 4},
        )
    )
    universe = ["S{}".format(index) for index in range(10)]

    assert scanner.pick_symbols(universe) == ["S0", "S1", "S2", "S3"]
    assert scanner.pick_symbols(universe) == ["S4", "S5", "S6", "S7"]
    assert scanner.pick_symbols(universe) == ["S8", "S9", "S0", "S1"]


# -- the screens ------------------------------------------------------------
def test_bpjs_skips_names_under_the_price_floor(scanners):
    scanner = scanners[SCANNER_ID]
    # 90 IDR: volume and value still clear the bar, only the price screen trips
    context = idx_context(prev_close=89.0, price=90.0, per_bar_volume=1_000_000.0)
    assert scanner.scan(context) == []


def test_bpjs_skips_thin_volume(scanners):
    scanner = scanners[SCANNER_ID]
    context = idx_context(per_bar_volume=50_000.0)  # 600k shares today
    assert scanner.scan(context) == []


def test_bpjs_skips_thin_value(scanners):
    scanner = scanners[SCANNER_ID]
    # 2.4M shares at 100 IDR = 240M IDR: volume passes, value does not
    context = idx_context(prev_close=99.0, price=100.0, per_bar_volume=200_000.0)
    assert scanner.scan(context) == []


def test_bpjs_skips_names_that_are_down_on_the_day(scanners):
    scanner = scanners[SCANNER_ID]
    context = idx_context(prev_close=1000.0, price=990.0)
    assert scanner.scan(context) == []


def test_bpjs_skips_flat_names(scanners):
    scanner = scanners[SCANNER_ID]
    context = idx_context(prev_close=1000.0, price=1000.0)
    assert scanner.scan(context) == []


# -- the session window -----------------------------------------------------
def test_bpjs_silent_before_the_first_pass(scanners):
    scanner = scanners[SCANNER_ID]
    early = datetime(2026, 11, 17, 9, 15, tzinfo=JKT)  # 15 minutes before 09:30
    assert scanner.scan(idx_context(now=early)) == []


def test_bpjs_silent_after_the_time_exit(scanners):
    scanner = scanners[SCANNER_ID]
    late = datetime(2026, 11, 17, 15, 50, tzinfo=JKT)
    assert scanner.scan(idx_context(now=late)) == []


def test_bpjs_silent_at_the_weekend(scanners):
    scanner = scanners[SCANNER_ID]
    saturday = datetime(2026, 11, 21, 10, 0, tzinfo=JKT)
    assert scanner.scan(idx_context(now=saturday)) == []


def test_bpjs_skips_names_without_prints_today(scanners):
    scanner = scanners[SCANNER_ID]
    context = idx_context(today_bars=0)
    assert scanner.scan(context) == []


def test_bpjs_skips_a_stale_last_bar(scanners):
    scanner = scanners[SCANNER_ID]
    # only the 09:00 print exists and "now" is 10:00 -> 60 minutes of silence
    assert scanner.scan(idx_context(today_bars=1)) == []


# -- tick rounding ----------------------------------------------------------
def test_idx_tick_bands():
    from asta.markets.strategies.liquidity_momentum import idx_tick, round_to_tick

    assert idx_tick(150) == 1.0
    assert idx_tick(300) == 2.0
    assert idx_tick(1500) == 5.0
    assert idx_tick(3000) == 10.0
    assert idx_tick(6000) == 25.0
    assert round_to_tick(989.8, 5.0, up=False) == 985.0
    assert round_to_tick(1060.5, 5.0, up=True) == 1065.0
