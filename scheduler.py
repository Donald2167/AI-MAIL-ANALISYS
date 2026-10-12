"""
스케줄러 서비스
APScheduler를 사용한 일/주 단위 배치 실행

실행 방법:
    python scheduler.py                  # 환경변수로 설정
    python scheduler.py --config         # 설정 확인만
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, date

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from config import SMTPConfig, LLMConfig, SchedulerConfig, AppConfig, load_llm_config
from mail_crawler import save_emails_to_json, load_emails_from_json, Email
from mail_classifier import MailClassifier
from summary_generator import generate_weekly_report_file
from mail_sender import MailSender, build_weekly_email_html

# ──────────────────────────────────────────────
# 설정 — 환경변수 또는 직접 수정
# ──────────────────────────────────────────────

def build_smtp_config() -> SMTPConfig:
    """환경변수가 있으면 우선 적용, 없으면 config.py 기본값 사용"""
    _default = SMTPConfig()
    recipients_raw = os.environ.get("MAIL_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    return SMTPConfig(
        smtp_server=os.environ.get("SMTP_SERVER") or _default.smtp_server,
        smtp_port=int(os.environ.get("SMTP_PORT") or _default.smtp_port),
        email=os.environ.get("MAIL_EMAIL") or _default.email,
        password=os.environ.get("MAIL_PASSWORD") or _default.password,
        recipients=recipients or _default.recipients,
    )


def build_llm_config() -> LLMConfig:
    """저장된 설정 또는 환경변수 사용"""
    saved_config = load_llm_config()
    provider = os.environ.get("LLM_PROVIDER") or saved_config.get("provider", "openai")
    api_key = os.environ.get("LLM_API_KEY") or saved_config.get("api_key", "")
    model = os.environ.get("LLM_MODEL") or saved_config.get("model", "gpt-4o-mini")
    base_url = os.environ.get("LLM_BASE_URL")
    
    return LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url or None,
    )
    )


def build_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        weekly_report_day=int(os.environ.get("WEEKLY_REPORT_DAY", "0")), # 0=월요일
        weekly_report_time=os.environ.get("WEEKLY_REPORT_TIME", "09:00"),
        log_file=os.environ.get("LOG_FILE", "./data/scheduler.log"),
    )


# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────

def setup_logging(log_file: str):
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger("scheduler")


# ──────────────────────────────────────────────
# 배치 작업 함수
# ──────────────────────────────────────────────

def _get_llm_client(llm_cfg: LLMConfig):
    """LLM 클라이언트 생성. API 키 없으면 Mock 반환."""
    from summary_generator import OpenAIClient, MockLLMClient
    if llm_cfg.api_key:
        return OpenAIClient(
            api_key=llm_cfg.api_key,
            model=llm_cfg.model,
            base_url=llm_cfg.base_url,
        )
    logger.warning("LLM API 키 없음 — Mock 클라이언트 사용")
    return MockLLMClient()


def job_weekly_report_and_send(
    smtp_cfg: SMTPConfig,
    app_cfg: AppConfig,
    llm_cfg: LLMConfig,
):
    """[주간 배치] 이번 주 메일 집계 → 주간 보고서 생성 → 이메일 발송"""
    logger.info("=== 주간 배치 시작 ===")

    data_file = os.path.join(app_cfg.data_dir, "emails.json")
    if not os.path.exists(data_file):
        logger.warning("누적 메일 데이터 없음. 주간 배치 종료.")
        return

    all_emails = load_emails_from_json(data_file)

    # 이번 주 메일 필터 (월~일)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_emails = [
        e for e in all_emails
        if e.date and e.date.date() >= week_start
    ]
    if not week_emails:
        logger.warning("이번 주 메일 없음. 기존 전체 데이터로 대체.")
        week_emails = all_emails[-200:]  # 최근 200건 fallback

    week_label = f"{today.year}년 {today.strftime('%W')}주차"
    logger.info(f"주간 보고서 대상: {len(week_emails)}건 ({week_label})")

    llm_client = _get_llm_client(llm_cfg)
    report_text, report_path = generate_weekly_report_file(
        week_emails, app_cfg.weekly_dir, llm_client
    )
    logger.info(f"주간 보고서 저장: {report_path}")

    # 이메일 발송
    if smtp_cfg.email and smtp_cfg.password and smtp_cfg.recipients:
        sender = MailSender(smtp_cfg)
        subject = f"[메일 리포터] {week_label} 주간 요약 보고서"
        html_body = build_weekly_email_html(report_text, week_label)
        success = sender.send(
            subject=subject,
            body_text=report_text,
            body_html=html_body,
            attachment_paths=[report_path],
        )
        if success:
            logger.info(f"주간 보고서 발송 완료 → {smtp_cfg.recipients}")
        else:
            logger.error("주간 보고서 발송 실패")
    else:
        logger.warning("SMTP 미설정 — 이메일 발송 건너뜀 (파일만 저장됨)")

    logger.info("=== 주간 배치 완료 ===")


# ──────────────────────────────────────────────
# 스케줄러 실행
# ──────────────────────────────────────────────

def on_job_event(event):
    if event.exception:
        logger.error(f"작업 오류: {event.job_id} — {event.exception}")
    else:
        logger.info(f"작업 완료: {event.job_id}")


def run_scheduler():
    smtp_cfg = build_smtp_config()
    llm_cfg = build_llm_config()
    sched_cfg = build_scheduler_config()
    app_cfg = AppConfig()

    setup_logging(sched_cfg.log_file)

    logger.info("=" * 50)
    logger.info("메일 리포터 스케줄러 시작")
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    logger.info(
        f"  주간 보고서: 매주 {day_names[sched_cfg.weekly_report_day]}요일 {sched_cfg.weekly_report_time}"
    )
    logger.info(f"  수신자: {smtp_cfg.recipients or '(미설정)'}")
    logger.info("=" * 50)

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_listener(on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    weekly_hour, weekly_min = map(int, sched_cfg.weekly_report_time.split(":"))

    # 주간 보고서 발송 (매주 지정 요일/시간)
    scheduler.add_job(
        job_weekly_report_and_send,
        trigger="cron",
        day_of_week=sched_cfg.weekly_report_day,
        hour=weekly_hour,
        minute=weekly_min,
        id="weekly_report",
        name="주간 보고서 생성 및 이메일 발송",
        args=[smtp_cfg, app_cfg, llm_cfg],
        misfire_grace_time=3600,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


def print_config():
    """현재 설정 정보를 출력하고 종료"""
    smtp_cfg = build_smtp_config()
    llm_cfg = build_llm_config()
    sched_cfg = build_scheduler_config()

    print("\n현재 스케줄러 설정")
    print("-" * 40)
    print(f"SMTP 서버     : {smtp_cfg.smtp_server}:{smtp_cfg.smtp_port}")
    print(f"수신자        : {smtp_cfg.recipients or '(미설정 — MAIL_RECIPIENTS 환경변수)'}")
    print(f"LLM 제공자    : {llm_cfg.provider} / {llm_cfg.model}")
    day_names = ["월", "화", "수", "목", "금", "토", "일"]
    print(f"주간 보고서   : 매주 {day_names[sched_cfg.weekly_report_day]}요일 {sched_cfg.weekly_report_time}")
    print(f"로그 파일     : {sched_cfg.log_file}")
    print()
    print("환경변수 목록:")
    env_vars = [
        ("SMTP_SERVER", "SMTP 서버 (기본: smtp.office365.com)"),
        ("SMTP_PORT", "SMTP 포트 (기본: 587)"),
        ("MAIL_EMAIL", "발신 이메일 주소"),
        ("MAIL_PASSWORD", "SMTP 비밀번호"),
        ("MAIL_RECIPIENTS", "수신자 이메일 (콤마 구분)"),
        ("LLM_PROVIDER", "LLM 제공자 (openai/ollama/gemini)"),
        ("LLM_API_KEY", "LLM API 키"),
        ("LLM_MODEL", "LLM 모델 (기본: gpt-4o-mini)"),
        ("LLM_BASE_URL", "LLM Base URL (Ollama 등 로컬용)"),
        ("WEEKLY_REPORT_DAY", "주간 보고서 요일 0=월 (기본: 0)"),
        ("WEEKLY_REPORT_TIME", "주간 보고서 시간 HH:MM (기본: 09:00)"),
    ]
    for var, desc in env_vars:
        val = os.environ.get(var, "")
        status = f"✓ {val[:20]}" if val else "  (미설정)"
        print(f"  {var:<25} {desc}  {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="메일 리포터 스케줄러")
    parser.add_argument("--config", action="store_true", help="현재 설정 확인 후 종료")
    parser.add_argument("--run-weekly", action="store_true", help="주간 배치를 지금 즉시 실행")
    args = parser.parse_args()

    if args.config:
        print_config()
        sys.exit(0)

    if args.run_weekly:
        smtp_cfg = build_smtp_config()
        llm_cfg = build_llm_config()
        sched_cfg = build_scheduler_config()
        app_cfg = AppConfig()
        setup_logging(sched_cfg.log_file)
        print("▶ 주간 배치 즉시 실행...")
        job_weekly_report_and_send(smtp_cfg, app_cfg, llm_cfg)
        sys.exit(0)

    run_scheduler()
