# KTB Excel RTD Monitor

한국 국채선물 3Y/10Y의 Excel RTD 실시간 호가와 시장 체결가를 Python으로 수집하는 관찰용 프로토타입입니다. 자동주문·주문 API·실거래 기능은 포함하지 않습니다.

## 빠른 실행

1. 32비트 데스크톱 Excel에서 `국채선물 호가창.xlsx`를 엽니다.
2. CheckExpert RTD 값이 표시되는지 확인합니다.
3. `실시간_호가_시작.bat`을 더블클릭합니다.
4. `대시보드_시작.bat`을 더블클릭합니다.

수집을 중단하려면 수집 창에서 `Ctrl+C`를 누릅니다.

## 수동 실행

```powershell
.\.venv32\Scripts\python.exe .\ktb_rtd_monitor.py --interval-ms 250 --output-dir .\data --log both --no-clear
```

최근 로그 분석:

```powershell
.\.venv32\Scripts\python.exe .\analyze_snapshots.py .\data\snapshots_with_trades.csv --window 120 --beta 2.88
```

## 주요 파일

- `ktb_rtd_monitor.py`: Excel 연결, 지표 계산, CSV/SQLite 수집
- `analyze_snapshots.py`: 이벤트 기반 RV 요약
- `dashboard.py`: 실시간 Tkinter 대시보드
- `test_metrics.py`: 단위 테스트
- `requirements.txt`: Python 의존성
- `DEVELOPMENT_LOG.md`: 전체 개발 내역과 한계

## 데이터 구조

워크시트는 `Sheet1`이며 3Y 심볼은 `KBFA020`, 10Y 심볼은 `KXFA020`입니다. 체결가는 `G2`(3Y), `O2`(10Y)이며 RTD 필드는 `15001`입니다.

| 데이터 | 3Y | 10Y |
|---|---|---|
| Ask price | `D2:D6` | `L2:L6` |
| Ask quantity | `C2:C6` | `K2:K6` |
| Bid price | `D7:D11` | `L7:L11` |
| Bid quantity | `E7:E11` | `M7:M11` |
| Trade price | `G2` | `O2` |

## 주의

기본 beta `2.88`은 초기값입니다. 실제 연구에는 계약별 DV01로 hedge ratio를 계산해야 합니다. OBI/WOBI와 z-score 임계값은 아직 국채선물 데이터로 검증된 매매 기준이 아닙니다.

자세한 상태와 다음 작업은 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)를 참고하세요.
