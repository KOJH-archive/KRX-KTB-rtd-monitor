"""Analyze KTB RTD snapshots already collected by ktb_rtd_monitor.py."""
from __future__ import annotations
import argparse, csv, statistics
from pathlib import Path

def read_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            try: rows.append({k: (v if k == "timestamp_utc" else float(v)) for k, v in raw.items()})
            except (TypeError, ValueError): pass
        return rows

def analyze(rows: list[dict[str, object]], window: int, beta: float) -> dict[str, object] | None:
    changes, previous = [], None
    for row in rows:
        mid3 = row.get("3y_trade_price", row.get("3y_mid"))
        mid10 = row.get("10y_trade_price", row.get("10y_mid"))
        if not isinstance(mid3, float) or not isinstance(mid10, float): continue
        if previous is not None and (mid3, mid10) != previous:
            changes.append((mid10 - previous[1]) - beta * (mid3 - previous[0]))
        previous = (mid3, mid10)
    if not changes: return None
    sample, latest = changes[-window:], changes[-1]
    mean = statistics.fmean(sample)
    stdev = statistics.stdev(sample) if len(sample) >= 2 else 0.0
    return {"timestamp_utc": rows[-1]["timestamp_utc"], "samples": len(changes), "latest_rv_change": latest,
            "window_mean": mean, "window_stdev": stdev, "zscore": (latest-mean)/stdev if stdev > 1e-12 else 0.0, "beta": beta}

def main() -> int:
    p = argparse.ArgumentParser(description="Summarize KTB 3Y/10Y relative-value changes.")
    p.add_argument("csv_path", nargs="?", type=Path, default=Path("data/snapshots.csv")); p.add_argument("--window", type=int, default=120); p.add_argument("--beta", type=float, default=2.88)
    a = p.parse_args()
    if a.window < 2: p.error("--window must be at least 2")
    result = analyze(read_rows(a.csv_path), a.window, a.beta)
    if result is None: print("분석할 유효한 스냅샷이 없습니다."); return 1
    print(f"KTB RV summary | {result['timestamp_utc']}")
    print(f"samples {int(result['samples'])} | beta {result['beta']:.4f} | window {a.window}")
    print(f"latest RV change {result['latest_rv_change']:+.6f} | mean {result['window_mean']:+.6f} | stdev {result['window_stdev']:.6f} | z-score {result['zscore']:+.3f}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
