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

def analyze(rows: list[dict[str, object]], window: int, beta: float, min_samples: int = 20) -> dict[str, object] | None:
    changes, levels, previous = [], [], None
    for row in rows:
        # Use executable-book mids for the RV level; last trade is a confirmation field.
        mid3 = row.get("3y_mid", row.get("3y_trade_price"))
        mid10 = row.get("10y_mid", row.get("10y_trade_price"))
        if not isinstance(mid3, float) or not isinstance(mid10, float): continue
        level = mid10 - beta * mid3
        if previous is None:
            levels.append(level)
        elif (mid3, mid10) != previous:
            changes.append(level - (previous[1] - beta * previous[0]))
            levels.append(level)
        previous = (mid3, mid10)
    if not levels: return None
    level_sample = levels[-window:]
    latest_level = level_sample[-1]
    level_mean = statistics.fmean(level_sample)
    level_stdev = statistics.stdev(level_sample) if len(level_sample) >= 2 else 0.0
    change_sample, latest_change = changes[-window:], (changes[-1] if changes else 0.0)
    change_mean = statistics.fmean(change_sample) if change_sample else 0.0
    change_stdev = statistics.stdev(change_sample) if len(change_sample) >= 2 else 0.0
    level_zscore = ((latest_level - level_mean) / level_stdev
                    if len(level_sample) >= min_samples and level_stdev > 1e-12 else 0.0)
    change_zscore = ((latest_change - change_mean) / change_stdev
                     if len(change_sample) >= 2 and change_stdev > 1e-12 else 0.0)
    return {"timestamp_utc": rows[-1]["timestamp_utc"], "samples": len(changes),
            "latest_rv_level": latest_level, "level_mean": level_mean, "level_stdev": level_stdev,
            "latest_rv_change": latest_change, "window_mean": change_mean, "window_stdev": change_stdev,
            "zscore": level_zscore, "level_zscore": level_zscore, "change_zscore": change_zscore,
            "beta": beta}

def main() -> int:
    p = argparse.ArgumentParser(description="Summarize KTB 3Y/10Y relative-value changes.")
    p.add_argument("csv_path", nargs="?", type=Path, default=Path("data/snapshots.csv")); p.add_argument("--window", type=int, default=120); p.add_argument("--beta", type=float, default=2.88)
    a = p.parse_args()
    if a.window < 2: p.error("--window must be at least 2")
    result = analyze(read_rows(a.csv_path), a.window, a.beta)
    if result is None: print("분석할 유효한 스냅샷이 없습니다."); return 1
    print(f"KTB RV summary | {result['timestamp_utc']}")
    print(f"samples {int(result['samples'])} | beta {result['beta']:.4f} | window {a.window}")
    print(f"RV level {result['latest_rv_level']:+.6f} | level mean {result['level_mean']:+.6f} | level stdev {result['level_stdev']:.6f} | level z-score {result['level_zscore']:+.3f}")
    print(f"latest RV change {result['latest_rv_change']:+.6f} | change z-score {result['change_zscore']:+.3f}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
