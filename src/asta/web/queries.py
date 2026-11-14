"""Read-only queries over the ASTA signal database.

The dashboard must never open a write handle: the scanner keeps appending while
the UI polls. Every connection here is ``mode=ro`` and short-lived, so a slow
HTTP request can never hold the writer's lock.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

COLUMNS = (
    "id, signal_id, scanner_id, scanner_name, market, symbol, timeframe, signal_type, "
    "confidence, price, stop_loss, take_profit, risk_reward, risk_pct, atr, levels_source, "
    "status, realized_r, bars_held, created_at, closed_at, expires_at, strategy, reason, source"
)

SORTS = {
    "newest": "created_at DESC",
    "oldest": "created_at ASC",
    "best": "realized_r DESC",
    "worst": "realized_r ASC",
    "confidence": "confidence DESC",
}

CLOSED = "status IN ('hit_tp', 'hit_sl') AND realized_r IS NOT NULL"


def _num(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _json_object(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        import json

        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except (TypeError, ValueError):
        return {}


def serialize(row: sqlite3.Row) -> Dict[str, Any]:
    """One DB row -> the JSON shape the web app consumes (camelCase)."""
    return {
        "id": row["id"],
        "signalId": row["signal_id"],
        "scannerId": row["scanner_id"],
        "scanner": row["scanner_name"],
        "market": row["market"],
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "side": (row["signal_type"] or "").lower(),
        "confidence": _num(row["confidence"]),
        "price": _num(row["price"]),
        "stopLoss": _num(row["stop_loss"]),
        "takeProfit": _num(row["take_profit"]),
        "riskReward": _num(row["risk_reward"]),
        "riskPct": _num(row["risk_pct"]),
        "atr": _num(row["atr"]),
        "levelsSource": row["levels_source"] or "",
        "status": (row["status"] or "open").lower(),
        "realizedR": _num(row["realized_r"]),
        "barsHeld": _integer(row["bars_held"]),
        "createdAt": row["created_at"],
        "closedAt": row["closed_at"],
        "expiresAt": row["expires_at"],
        "strategy": row["strategy"] or "",
        "reason": row["reason"] or "",
        "source": row["source"] or "live",
        "indicators": _json_object(row["indicators"] if "indicators" in row.keys() else "{}"),
    }


class SignalQueries:
    """Thin, dependency-free reader used by the HTTP layer."""

    def __init__(self, db_path: Path | str):
        self.path = Path(db_path).expanduser()

    # -- connection -------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        uri = "file:{}?mode=ro".format(quote(str(self.path)))
        connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def available(self) -> bool:
        return self.path.exists()

    # -- reads ------------------------------------------------------------
    def list_signals(
        self,
        status: Optional[str] = None,
        scanner: Optional[str] = None,
        market: Optional[str] = None,
        timeframe: Optional[str] = None,
        query: Optional[str] = None,
        sort: str = "newest",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        clauses: List[str] = []
        params: List[Any] = []
        if status and status != "all":
            clauses.append("status = ?")
            params.append(status)
        if scanner and scanner != "all":
            clauses.append("scanner_name = ?")
            params.append(scanner)
        if market and market != "all":
            clauses.append("market = ?")
            params.append(market)
        if timeframe and timeframe != "all":
            clauses.append("timeframe = ?")
            params.append(timeframe)
        if query:
            like = "%{}%".format(query.strip())
            clauses.append(
                "(symbol LIKE ? COLLATE NOCASE OR scanner_name LIKE ? COLLATE NOCASE "
                "OR reason LIKE ? COLLATE NOCASE)"
            )
            params.extend([like, like, like])

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = SORTS.get(sort, SORTS["newest"])

        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM signals{}".format(where), params
            ).fetchone()[0]
            sql = "SELECT {} FROM signals{}{} LIMIT ? OFFSET ?".format(
                COLUMNS,
                where,
                " ORDER BY " + order,
            )
            rows = connection.execute(
                sql, params + [limit if limit is not None else -1, offset]
            ).fetchall()
        return [serialize(row) for row in rows], int(total)

    def get_signal(self, signal_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT {} FROM signals WHERE signal_id = ? OR id = ?".format(COLUMNS),
                (signal_key, signal_key),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT {} FROM signals WHERE CAST(id AS TEXT) = ?".format(COLUMNS),
                    (signal_key,),
                ).fetchone()
        return serialize(row) if row is not None else None

    def meta(self) -> Dict[str, Any]:
        empty = {
            "generatedAt": _timestamp(),
            "total": 0,
            "closed": 0,
            "open": 0,
            "wins": 0,
            "losses": 0,
            "winRate": 0.0,
            "expectancyR": 0.0,
            "netR": 0.0,
            "profitFactor": None,
            "firstSignal": None,
            "lastSignal": None,
        }
        if not self.available():
            return empty
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*)                                                    AS total,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END)            AS open_n,
                    SUM(CASE WHEN {closed} THEN 1 ELSE 0 END)                   AS closed_n,
                    SUM(CASE WHEN {closed} AND realized_r > 0 THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN {closed} AND realized_r <= 0 THEN 1 ELSE 0 END) AS losses,
                    SUM(CASE WHEN {closed} THEN realized_r ELSE 0 END)          AS net_r,
                    SUM(CASE WHEN {closed} AND realized_r > 0 THEN realized_r ELSE 0 END) AS gross_win,
                    SUM(CASE WHEN {closed} AND realized_r < 0 THEN -realized_r ELSE 0 END) AS gross_loss,
                    MIN(created_at)                                             AS first_at,
                    MAX(created_at)                                             AS last_at
                FROM signals
                """.format(closed=CLOSED)
            ).fetchone()

            closed = int(row["closed_n"] or 0)
            wins = int(row["wins"] or 0)
            gross_win = float(row["gross_win"] or 0.0)
            gross_loss = float(row["gross_loss"] or 0.0)
            net = float(row["net_r"] or 0.0)
            return {
                "generatedAt": _timestamp(),
                "total": int(row["total"] or 0),
                "closed": closed,
                "open": int(row["open_n"] or 0),
                "wins": wins,
                "losses": int(row["losses"] or 0),
                "winRate": (wins / closed * 100) if closed else 0.0,
                "expectancyR": (net / closed) if closed else 0.0,
                "netR": net,
                "profitFactor": (gross_win / gross_loss) if gross_loss else None,
                "firstSignal": row["first_at"],
                "lastSignal": row["last_at"],
            }

    def facets(self) -> Dict[str, List[str]]:
        """Distinct filter values, so the UI never hardcodes them."""
        with self._connect() as connection:
            def distinct(column: str) -> List[str]:
                rows = connection.execute(
                    "SELECT DISTINCT {} FROM signals WHERE {} != ''".format(column, column)
                ).fetchall()
                return sorted(str(row[0]) for row in rows if row[0])

            return {
                "scanners": distinct("scanner_name"),
                "markets": distinct("market"),
                "timeframes": distinct("timeframe"),
            }

    def count(self) -> int:
        if not self.available():
            return 0
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0])
