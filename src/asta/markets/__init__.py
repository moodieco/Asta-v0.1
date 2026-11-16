"""Market specific scanners and strategies.

Layout::

    markets/strategies/<strategy>.py                 (generic implementation)
    markets/strategies/<market>_<strategy>.py         (per-market tuning, same folder)
    markets/<market>/scanners/<SCANNER_ID>/{scanner.py, config.yaml}
    markets/<market>/indicators/__init__.py   (market-scoped indicator exports)
    markets/indicators/<module>.py            (shared indicator maths)
"""
