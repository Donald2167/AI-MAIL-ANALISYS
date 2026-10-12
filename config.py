"""
메일 리포터 설정 파일
"""
import os
import json
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class SMTPConfig:
    """발신 메일 서버 설정 (주간 보고서 발송용)"""
    smtp_server: str = "smtp.office365.com"      # Exchange Online SMTP
    smtp_port: int = 587
    email: str = "youjin0404@hanwha.com"         # 발신 이메일 주소
    password: str = ""                           # 계정 비밀번호
    recipients: List[str] = field(default_factory=list)  # 보고서 수신자 목록

@dataclass
class LLMConfig:
    """LLM API 설정"""
    provider: str = "openai"  # openai, azure, ollama
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None  # Ollama 등 로컬 LLM용
    
    @classmethod
    def from_env(cls):
        """환경 변수에서 LLM 설정 로드"""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OLLAMA_BASE_URL", None)
        )

@dataclass
class SchedulerConfig:
    """스케줄러 설정"""
    # 주간 보고서 발송 요일 및 시간 (0=월, 6=일)
    weekly_report_day: int = 0       # 월요일
    weekly_report_time: str = "09:00"
    # 로그 파일 경로
    log_file: str = "./data/scheduler.log"

@dataclass
class AppConfig:
    """애플리케이션 설정"""
    data_dir: str = "./data"
    summary_dir: str = "./data/summaries"
    sender_folders_dir: str = "./data/by_sender"
    vector_db_dir: str = "./data/vector_db"
    weekly_dir: str = "./data/weekly"

    def __post_init__(self):
        # 필요한 디렉토리 생성
        for dir_path in [self.data_dir, self.summary_dir,
                         self.sender_folders_dir, self.vector_db_dir,
                         self.weekly_dir]:
            os.makedirs(dir_path, exist_ok=True)

# LLM 설정 파일 경로
LLM_CONFIG_FILE = "./data/llm_config.json"

def save_llm_config(provider: str, api_key: str, model: str, max_tokens: int = 1000) -> bool:
    """LLM 설정을 파일에 저장"""
    try:
        config = {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "max_tokens": max_tokens
        }
        os.makedirs(os.path.dirname(LLM_CONFIG_FILE) or ".", exist_ok=True)
        with open(LLM_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"LLM 설정 저장 실패: {e}")
        return False

def load_llm_config() -> dict:
    """저장된 LLM 설정 로드"""
    try:
        if os.path.exists(LLM_CONFIG_FILE):
            with open(LLM_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"LLM 설정 로드 실패: {e}")
    
    # 환경 변수에서 로드
    return {
        "provider": os.getenv("LLM_PROVIDER", "openai"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "1000"))
    }

# 메일 분류 카테고리
MAIL_CATEGORIES = {
    "REPLY_REQUIRED": "회신필요",
    "MEETING_REQUEST": "회의참석요청", 
    "SIMPLE_NOTICE": "단순공지",
    "APPROVAL_REQUEST": "결재요청",
    "REPORT": "보고/공유",
    "TASK_REQUEST": "업무요청",
    "OTHER": "기타"
}

# 분류 키워드 (규칙 기반 분류용)
CLASSIFICATION_KEYWORDS = {
    "REPLY_REQUIRED": ["회신", "답변", "피드백", "의견", "검토", "확인 부탁"],
    "MEETING_REQUEST": ["회의", "미팅", "참석", "일정", "zoom", "teams", "초대"],
    "SIMPLE_NOTICE": ["공지", "안내", "알림", "notice", "공유드립니다"],
    "APPROVAL_REQUEST": ["결재", "승인", "품의", "기안"],
    "REPORT": ["보고", "리포트", "report", "현황", "결과"],
    "TASK_REQUEST": ["요청", "부탁", "처리", "진행", "작업"]
}
