"""Market specific scanners and strategies.

Layout::

    markets/<market>/scanners/<SCANNER_ID>/{scanner.py, config.yaml}
    markets/<market>/strategies/<strategy>.py
    markets/<market>/indicators/__init__.py   (market-scoped indicator exports)
    markets/indicators/<module>.py            (shared indicator maths)
"""
