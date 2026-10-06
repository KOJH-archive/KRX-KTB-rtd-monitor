from __future__ import annotations
import csv, tkinter as tk
from pathlib import Path
from analyze_snapshots import analyze, read_rows

DATA_DIR = Path(__file__).parent / "data"

def current_csv() -> Path:
    """Use the live trade-price log when it exists, otherwise the legacy log."""
    trade_csv = DATA_DIR / "snapshots_with_trades.csv"
    legacy_csv = DATA_DIR / "snapshots.csv"
    if trade_csv.exists() and trade_csv.stat().st_size > 0:
        return trade_csv
    return legacy_csv

class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__(); self.title("KTB RTD Dashboard"); self.geometry("760x430"); self.configure(bg="#101820")
        self.rv_state, self.rv_candidate, self.rv_count = "중립/관찰", None, 0
        self.labels = {}
        tk.Label(self, text="KTB RTD Dashboard  |  observation only", fg="white", bg="#101820", font=("Segoe UI", 16, "bold")).pack(pady=12)
        self.status = tk.Label(self, text="Waiting for snapshots...", fg="#9fb3c8", bg="#101820", font=("Consolas", 10)); self.status.pack()
        grid = tk.Frame(self, bg="#101820"); grid.pack(pady=18)
        for c, title in enumerate(("Metric", "3Y", "10Y", "Interpretation")): tk.Label(grid, text=title, width=24, fg="#8ed1fc", bg="#1b2a38", font=("Segoe UI", 11, "bold")).grid(row=0, column=c, padx=2, pady=2)
        for r, key, title in ((1,"mid","Mid"),(2,"spread","Spread"),(3,"obi","OBI"),(4,"weighted_obi","WOBI"),(5,"microprice","Microprice"),(6,"bid_depth","Bid depth"),(7,"ask_depth","Ask depth")):
            tk.Label(grid, text=title, width=24, fg="white", bg="#101820", anchor="w").grid(row=r,column=0,padx=2,pady=3)
            for c, name in enumerate(("3y","10y"),1):
                label=tk.Label(grid,text="-",width=24,fg="#e8f1f2",bg="#243746",font=("Consolas",11)); label.grid(row=r,column=c,padx=2,pady=3); self.labels[(name,key)]=label
            help_text = {"mid":"현재 최우선 호가의 단순 중간값", "spread":"매수-매도 간격; 작을수록 유동성 양호", "obi":"5단계 전체 잔량: + 매수 우세 / - 매도 우세", "weighted_obi":"WOBI: 가까운 호가에 높은 가중치; + 매수 압력 / - 매도 압력", "microprice":"최우선 호가 잔량으로 가중한 예상 중심가격", "bid_depth":"5단계 매수 총잔량", "ask_depth":"5단계 매도 총잔량"}[key]
            tk.Label(grid, text=help_text, width=38, fg="#b8c7d1", bg="#101820", anchor="w", wraplength=270, justify="left").grid(row=r,column=3,padx=4,pady=3)
        self.rv = tk.Label(self, text="RV: -", fg="#ffd166", bg="#101820", font=("Consolas", 13, "bold")); self.rv.pack(pady=10)
        self.after(500, self.refresh)
    def refresh(self):
        try:
            csv_path = current_csv()
            with csv_path.open("r", newline="", encoding="utf-8") as f: rows=list(csv.DictReader(f))
            if rows:
                row=rows[-1]; self.status.config(text=f"UTC {row['timestamp_utc']}   |   source: {csv_path.name}")
                for name in ("3y","10y"):
                    for key in ("mid","spread","obi","weighted_obi","microprice","bid_depth","ask_depth"):
                        value=float(row[f"{name}_{key}"]); text=f"{value:.4f}" if key in ("mid","microprice") else (f"{value:+.3f}" if "obi" in key else f"{value:.3f}")
                        self.labels[(name,key)].config(text=text)
                result = analyze(read_rows(csv_path), window=120, beta=2.88, min_samples=20)
                if result:
                    z = float(result["zscore"])
                    candidate = "10Y 상대강세" if z >= 2 else ("10Y 상대약세" if z <= -2 else None)
                    if self.rv_state == "10Y 상대강세" and z > 1.5: candidate = "10Y 상대강세"
                    elif self.rv_state == "10Y 상대약세" and z < -1.5: candidate = "10Y 상대약세"
                    if candidate == self.rv_state or candidate is None and self.rv_state == "중립/관찰":
                        self.rv_candidate, self.rv_count = None, 0
                    else:
                        self.rv_count = self.rv_count + 1 if candidate == self.rv_candidate else 1
                        self.rv_candidate = candidate
                        if self.rv_count >= 3:
                            self.rv_state = candidate or "중립/관찰"; self.rv_candidate, self.rv_count = None, 0
                    state = self.rv_state
                    sample_count = int(result["samples"])
                    if sample_count < 20:
                        state = f"데이터 축적 중 ({sample_count}/20 이벤트)"
                    self.rv.config(text=f"RV level {float(result['latest_rv_level']):+.4f}  |  평균 {float(result['level_mean']):+.4f}  |  z-score {z:+.3f}  |  해석: {state}")
                else:
                    self.rv.config(text="RV: 유효한 가격 변화가 쌓이는 중입니다 (최소 2개 스냅샷 필요)")
        except (FileNotFoundError, PermissionError, KeyError, ValueError): pass
        self.after(500, self.refresh)

if __name__ == "__main__": Dashboard().mainloop()
