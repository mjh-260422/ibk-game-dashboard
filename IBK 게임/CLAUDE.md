# IBK 게임 대시보드 프로젝트

## 개요
IBK카드 앱 게이미피케이션 운영 현황 대시보드 (Streamlit Cloud 배포)

**배포 URL:** https://ibk-game-dashboard-agculmnfwzi68drau9ujy6.streamlit.app/

## 핵심 파일
| 파일 | 역할 |
|------|------|
| `dashboard.py` | Streamlit 대시보드 메인 (배포됨) |
| `data_loader.py` | Google Sheets → Python DataFrame 변환 |
| `report_generator.py` | 구글시트 탭 생성/갱신 (23열 구조) |

## Google Sheets
- **스프레드시트 ID:** `1G2A_FyERvQOVQBUsu9AHx7FPrE-UAIX4Ohl9UNtalzY`
- **서비스 계정:** `mjh-873@fluid-furnace-491101-j2.iam.gserviceaccount.com`
- **키 파일:** `C:\Users\jihye\.claude\google-sheets-key.json` (git 제외, Streamlit Secrets에도 등록)
- Streamlit Cloud에서는 `st.secrets["gcp_service_account"]`로 읽음

## 시트 컬럼 구조 (A~W, 0-based)
```
A=게임명 B=공급사명 C=상품명 D=게임P E=면가 F=수수료율
G=발행수 H=교환수 I=만료수 J~M=금액집계 N=교환율 O=미교환율
P=교환금액(15) Q=수수료금액(16) R=정산금액(17) S=잠재수익(18)
T=잠재수익률(19) U=수익률_면가(20) V=확정수익(21) W=확정수익률(22)
```

## 배포 방법
```
git add IBK\ 게임/dashboard.py
git commit -m "..."
git push origin master
```
→ Streamlit Cloud 자동 재배포 (~1분 소요)

## 주요 기술 결정사항
- `column_config` rename은 Pandas Styler와 함께 쓰면 무시됨 → `.rename()`을 DataFrame에 직접 적용
- `skip_fmt` 파라미터: 확정수익/잠재수익은 문자열로 변환 후 표시하므로 INT_COLS 서식 적용 제외
- `_fmt_highlight()`: 교환율 통계적 이상값 강조 (30% 목표 기준 강조는 제거됨)
- 확정수익 = 정산금액 − (발행수−만료수)×면가 + 수수료
- 잠재수익 = 정산금액 − 교환금액 + 수수료
- `report_generator.py`는 실행 시 시트 삭제 후 재생성 → MCP로 직접 수정해도 다음 실행 시 초기화됨

## Python 실행
```
py dashboard.py       # 로컬 테스트
py report_generator.py  # 구글시트 갱신
```
