@echo off
chcp 65001 > nul
setlocal

REM ============================================================
REM  메일 리포터 시작 스크립트
REM  1단계: mail_data/ 폴더의 .eml 파일을 가져와 분석 데이터 구성
REM  2단계: Streamlit 대시보드 실행
REM ============================================================

cd /d "%~dp0"

REM ── 가상환경 활성화 (있으면 우선 사용) ──────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM ── Python 환경 확인 ─────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [오류] Python 을 찾을 수 없습니다. Python 3.10 이상을 설치하세요.
    pause
    exit /b 1
)

REM ── 패키지 설치 확인 ─────────────────────────────────────────
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [설치] 필수 패키지를 설치합니다...
    python -m pip install -r requirements.txt --quiet
)

REM ── mail_data 폴더 확인 ──────────────────────────────────────
if not exist "mail_data\" (
    echo [안내] mail_data\ 폴더가 없어 생성합니다.
    mkdir mail_data
)

REM ── 1단계: EML 파일 가져오기 ────────────────────────────────
echo.
echo [1/2] 전체 메일 데이터 파싱 중... (강제 재파싱)
echo       [키워드 기반 분류]
echo.
python main.py import-eml --force
echo.

REM ── 2단계: 대시보드 실행 ─────────────────────────────────────
echo [2/2] 대시보드를 실행합니다...
echo       브라우저에서 http://localhost:8501 으로 접속하세요.
echo.
python -m streamlit run dashboard.py --server.port 8501 --server.headless false

echo.
echo 종료되었습니다.
pause

