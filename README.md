# KTB Excel RTD Monitor

한국 국채선물 3Y/10Y의 Excel RTD 실시간 호가와 시장 체결가를 Python으로 수집·분석하는 관찰용 프로토타입입니다. 자동주문·주문 API·실거래 기능은 포함하지 않습니다.

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

## RV 해석 기준

대시보드의 기본 RV z-score는 마지막 체결가 변화량이 아니라, 실행 가능한 호가의 mid를 사용한 상대가치 수준을 표준화합니다.

```text
RV level = 10Y mid - beta × 3Y mid
RV z-score = (현재 RV level - rolling 평균) / rolling 표준편차
```

체결가는 RV level의 기준값이 아니라 시장 거래 확인용으로 함께 저장됩니다. 가격 변화 이벤트가 20개 미만이면 `데이터 축적 중`으로 표시합니다. `±2` 임계값과 beta `2.88`은 KTB 데이터로 검증된 매매 규칙이 아닌 초기 연구용 값입니다.

## 최근 디버깅 기록

대시보드 날짜가 과거에 멈춘 문제는 RTD 수집 중단이 아니었습니다. 파일 수정 시각과 CSV 마지막 행을 비교한 결과, 수집기는 최신 `data\\snapshots_with_trades.csv`에 계속 기록하고 있었지만 대시보드가 이전 `data\\snapshots.csv`를 고정해서 읽고 있었습니다. 대시보드는 이제 체결가 포함 로그를 우선 선택하고 화면에 실제 source 파일명을 표시합니다.

추가로 Windows CMD에서 깨진 한글 파일명 검사 때문에 실행 배치가 workbook을 못 찾을 수 있어, `실시간_호가_시작.bat`의 검사를 ASCII wildcard인 `*.xlsx`로 바꿨습니다. Excel이 생성하는 `~$*.xlsx` 임시 잠금 파일은 Git 추적 대상에서 제외합니다.

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
