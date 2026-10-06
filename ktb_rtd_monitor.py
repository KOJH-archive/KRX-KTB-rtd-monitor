"""Read the live values of the supplied KTB Excel RTD workbook. No order routing."""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import time
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import xlwings as xw
except ImportError:  # Lets calculation tests run before the Windows Excel dependency is installed.
    xw = None

WEIGHTS = (1.0, 0.7, 0.5, 0.3, 0.2)


class FeedUnavailable(RuntimeError):
    """Excel is unavailable, or its RTD cells do not currently hold usable values."""


@dataclass(frozen=True)
class ContractLayout:
    name: str
    symbol: str
    ask_prices: str
    ask_qty: str
    bid_prices: str
    bid_qty: str
    trade_price: str


# Verified from the supplied workbook, Sheet1.
LAYOUTS = (
    ContractLayout("3Y", "KBFA020", "D2:D6", "C2:C6", "D7:D11", "E7:E11", "G2"),
    ContractLayout("10Y", "KXFA020", "L2:L6", "K2:K6", "L7:L11", "M7:M11", "O2"),
)


def _numbers(values: Iterable[object], label: str, expected_len: int = 5) -> list[float]:
    result: list[float] = []
    for value in values:
        value = value[0] if isinstance(value, list) and len(value) == 1 else value
        if value is None or isinstance(value, bool):
            raise FeedUnavailable(f"{label}: RTD value is blank")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise FeedUnavailable(f"{label}: non-numeric RTD value {value!r}") from exc
        if number <= 0:
            raise FeedUnavailable(f"{label}: non-positive value {number}")
        result.append(number)
    if len(result) != expected_len:
        raise FeedUnavailable(f"{label}: expected {expected_len} levels, received {len(result)}")
    return result


def _column(sheet: xw.Sheet, address: str, label: str) -> list[float]:
    return _numbers(sheet.range(address).options(ndim=1).value, label)


def _metrics(prefix: str, bid_prices: list[float], bid_qty: list[float],
             ask_prices: list[float], ask_qty: list[float]) -> dict[str, float]:
    # Excel stores ask levels from 5th ask to best ask; normalize both sides to best→5th.
    ask_prices, ask_qty = list(reversed(ask_prices)), list(reversed(ask_qty))
    if bid_prices != sorted(bid_prices, reverse=True) or ask_prices != sorted(ask_prices):
        raise FeedUnavailable(f"{prefix}: book prices are not in expected bid/ask order")
    best_bid, best_ask, bid1_qty, ask1_qty = bid_prices[0], ask_prices[0], bid_qty[0], ask_qty[0]
    if best_ask < best_bid:
        raise FeedUnavailable(f"{prefix}: crossed book ({best_bid} / {best_ask})")
    bid_depth, ask_depth = sum(bid_qty), sum(ask_qty)
    weighted_bid = sum(q * w for q, w in zip(bid_qty, WEIGHTS))
    weighted_ask = sum(q * w for q, w in zip(ask_qty, WEIGHTS))
    denominator = bid_depth + ask_depth
    weighted_denominator = weighted_bid + weighted_ask
    top_denominator = bid1_qty + ask1_qty
    row: dict[str, float] = {
        f"{prefix}_best_bid": best_bid, f"{prefix}_best_ask": best_ask,
        f"{prefix}_mid": (best_bid + best_ask) / 2, f"{prefix}_spread": best_ask - best_bid,
        f"{prefix}_bid_depth": bid_depth, f"{prefix}_ask_depth": ask_depth,
        f"{prefix}_obi": (bid_depth - ask_depth) / denominator,
        f"{prefix}_weighted_obi": (weighted_bid - weighted_ask) / weighted_denominator,
        f"{prefix}_microprice": (best_ask * bid1_qty + best_bid * ask1_qty) / top_denominator,
    }
    for level, (bp, bq, ap, aq) in enumerate(zip(bid_prices, bid_qty, ask_prices, ask_qty), start=1):
        row.update({f"{prefix}_bid{level}_price": bp, f"{prefix}_bid{level}_qty": bq,
                    f"{prefix}_ask{level}_price": ap, f"{prefix}_ask{level}_qty": aq})
    return row


class ExcelRtdReader:
    def __init__(self, workbook_name: str, sheet_name: str) -> None:
        self.workbook_name, self.sheet_name = workbook_name, sheet_name
        self._sheet: xw.Sheet | None = None

    def _connect(self) -> xw.Sheet:
        if xw is None:
            raise FeedUnavailable("xlwings is not installed. Run: pip install -r requirements.txt")
        wanted = Path(self.workbook_name).name.lower()
        for app in xw.apps:
            for book in app.books:
                if Path(book.name).name.lower() == wanted:
                    try:
                        return book.sheets[self.sheet_name]
                    except KeyError as exc:
                        raise FeedUnavailable(f"Sheet {self.sheet_name!r} is not open in {book.name!r}") from exc
        raise FeedUnavailable(f"Open {self.workbook_name!r} in desktop Excel first (with the RTD add-in connected).")

    def snapshot(self) -> dict[str, object]:
        try:
            self._sheet = self._sheet or self._connect()
            row: dict[str, object] = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
            for layout in LAYOUTS:
                row[f"{layout.name.lower()}_trade_price"] = _numbers([self._sheet.range(layout.trade_price).value], f"{layout.name} trade price", expected_len=1)[0]
                row.update(_metrics(layout.name.lower(), _column(self._sheet, layout.bid_prices, f"{layout.name} bid prices"),
                                    _column(self._sheet, layout.bid_qty, f"{layout.name} bid quantities"),
                                    _column(self._sheet, layout.ask_prices, f"{layout.name} ask prices"),
                                    _column(self._sheet, layout.ask_qty, f"{layout.name} ask quantities")))
            return row
        except Exception as exc:
            self._sheet = None
            if isinstance(exc, FeedUnavailable):
                raise
            raise FeedUnavailable(f"Excel read failed: {exc}") from exc


class SnapshotLogger:
    def __init__(self, output_dir: Path, csv_enabled: bool, sqlite_enabled: bool) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = output_dir / "snapshots.csv"
        db_name = "snapshots.sqlite"
        if self.csv_path.exists() and self.csv_path.stat().st_size > 0:
            first_line = self.csv_path.open("r", encoding="utf-8").readline()
            if "3y_trade_price" not in first_line:
                self.csv_path = output_dir / "snapshots_with_trades.csv"
                db_name = "snapshots_with_trades.sqlite"
        self.csv_enabled, self.sqlite_enabled = csv_enabled, sqlite_enabled
        self._header_written = self.csv_path.exists() and self.csv_path.stat().st_size > 0
        self.db = sqlite3.connect(output_dir / db_name) if sqlite_enabled else None

    def write(self, row: dict[str, object]) -> None:
        if self.csv_enabled:
            with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                if not self._header_written:
                    writer.writeheader(); self._header_written = True
                writer.writerow(row)
        if self.db:
            columns = list(row)
            definitions = ", ".join('"' + column + '" TEXT' for column in columns)
            identifiers = ", ".join('"' + column + '"' for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            self.db.execute(f"CREATE TABLE IF NOT EXISTS snapshots ({definitions})")
            self.db.execute(f"INSERT INTO snapshots ({identifiers}) VALUES ({placeholders})", [str(row[c]) for c in columns])
            self.db.commit()

    def close(self) -> None:
        if self.db:
            self.db.close()


class RollingRV:
    """In-memory relative-value display state; does not alter persisted rows."""
    def __init__(self, window: int = 120, beta: float = 2.88) -> None:
        self.window, self.beta = window, beta
        self.previous: tuple[float, float] | None = None
        self.changes: list[float] = []
        self.levels: list[float] = []

    def update(self, row: dict[str, object]) -> tuple[float, float, float, int] | None:
        current = (float(row["3y_mid"]), float(row["10y_mid"]))
        level = current[1] - self.beta * current[0]
        if self.previous is None:
            self.previous = current
            self.levels.append(level)
            return None
        if current == self.previous:
            return None
        change = (current[1] - self.previous[1]) - self.beta * (current[0] - self.previous[0])
        self.previous = current
        self.changes.append(change)
        self.levels.append(level)
        sample = self.levels[-self.window:]
        mean = statistics.fmean(sample)
        stdev = statistics.stdev(sample) if len(sample) >= 2 else 0.0
        zscore = ((level - mean) / stdev
                  if len(sample) >= 20 and stdev > 1e-12 else 0.0)
        return change, mean, zscore, len(sample)


def display(row: dict[str, object], interval_ms: int, rv: tuple[float, float, float, int] | None = None,
            clear_screen: bool = True) -> None:
    if clear_screen:
        print("\033[2J\033[H", end="")
    print(f"KTB RTD monitor  |  {row['timestamp_utc']}  |  {interval_ms} ms")
    for name in ("3y", "10y"):
        print(f"{name.upper():>3}  bid {row[name+'_best_bid']:.3f}  ask {row[name+'_best_ask']:.3f}  "
              f"mid {row[name+'_mid']:.3f}  trade {row[name+'_trade_price']:.3f}  spr {row[name+'_spread']:.3f}")
        print(f"     OBI {row[name+'_obi']:+.3f}  WOBI {row[name+'_weighted_obi']:+.3f}  "
              f"micro {row[name+'_microprice']:.4f}  depth B/A {row[name+'_bid_depth']:.0f}/{row[name+'_ask_depth']:.0f}")
    if rv is not None:
        print(f"RV level z-score {rv[2]:+.3f}  |  samples {rv[3]}/20  |  latest Δ {rv[0]:+.6f}")
    else:
        print("RV warming up (waiting for a second snapshot)")
    print("Ctrl+C to stop. Data collection only; no order functionality is present.")


def main() -> int:
    parser = argparse.ArgumentParser(description="KTB Excel RTD snapshot collector (no trading).")
    parser.add_argument("--workbook", default="국채선물 호가창.xlsx")
    parser.add_argument("--sheet", default="Sheet1")
    parser.add_argument("--interval-ms", type=int, default=250, choices=range(100, 501))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--log", choices=("csv", "sqlite", "both"), default="both")
    parser.add_argument("--no-clear", action="store_true", help="Do not emit ANSI screen-clear codes")
    args = parser.parse_args()
    reader = ExcelRtdReader(args.workbook, args.sheet)
    logger = SnapshotLogger(args.output_dir, args.log in ("csv", "both"), args.log in ("sqlite", "both"))
    rv_state = RollingRV()
    last_error: str | None = None
    try:
        while True:
            started = time.perf_counter()
            try:
                row = reader.snapshot(); logger.write(row); display(row, args.interval_ms, rv_state.update(row), not args.no_clear); last_error = None
            except FeedUnavailable as exc:
                if str(exc) != last_error:
                    print(f"[waiting for Excel] {exc}", file=sys.stderr); last_error = str(exc)
            time.sleep(max(0.0, args.interval_ms / 1000 - (time.perf_counter() - started)))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
