"""
메일 분류 모듈
키워드 기반 및 LLM 기반 메일 분류 기능 제공
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re
from datetime import datetime, timedelta
from mail_crawler import Email
from config import MAIL_CATEGORIES, CLASSIFICATION_KEYWORDS


@dataclass
class EmailAnalysis:
    """메일 분석 결과"""
    email: Email
    is_urgent: bool = False           # 긴급 여부
    is_important: bool = False        # 중요 여부
    deadline: Optional[datetime] = None  # 마감일
    deadline_text: str = ""           # 마감일 텍스트
    days_until_deadline: Optional[int] = None  # 마감일까지 남은 일수
    action_items: List[str] = None    # 액션 아이템
    priority_score: int = 0           # 우선순위 점수
    urgency_reason: str = ""          # 긴급 사유
    
    def __post_init__(self):
        if self.action_items is None:
            self.action_items = []


class MailClassifier:
    """메일 분류기"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 클라이언트 (옵션, None이면 키워드 기반 분류)
        """
        self.llm_client = llm_client
        self.categories = MAIL_CATEGORIES
        self.keywords = CLASSIFICATION_KEYWORDS
    
    def classify_by_keywords(self, email: Email) -> str:
        """키워드 기반 분류"""
        text = f"{email.subject} {email.body_text}".lower()
        
        # 각 카테고리별 매칭 점수 계산
        scores = {}
        for category, keywords in self.keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text:
                    score += 1
            scores[category] = score
        
        # 가장 높은 점수의 카테고리 반환
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "OTHER"
    
    def classify_by_llm(self, email: Email, exclude_junk: bool = False) -> str:
        """LLM 기반 분류
        
        Args:
            email: 분류할 이메일
            exclude_junk: True이면 JUNK_SUSPECTED를 제외한 카테고리로만 분류
        """
        if not self.llm_client:
            return self.classify_by_keywords(email)
        
        # exclude_junk=True이면 정크 카테고리 제외
        categories_to_use = {k: v for k, v in self.categories.items() 
                            if not (exclude_junk and k == "JUNK_SUSPECTED")}
        categories_desc = "\n".join([f"- {k}: {v}" for k, v in categories_to_use.items()])
        
        exclude_hint = ""
        if exclude_junk:
            exclude_hint = "\n⚠️ 주의: JUNK_SUSPECTED 카테고리는 사용하지 마세요. 정크가 아닌 카테고리로만 분류하세요."
        
        prompt = f"""다음 이메일을 분석하고 가장 적합한 카테고리 하나를 선택하세요.

[카테고리 목록]
{categories_desc}{exclude_hint}

[이메일 정보]
제목: {email.subject}
발신자: {email.sender}
내용:
{email.body_text[:1000]}

위 이메일의 카테고리를 아래 형식으로만 답변하세요:
CATEGORY: [카테고리코드]
"""
        
        try:
            response = self.llm_client.generate(prompt)
            # 응답에서 카테고리 추출
            match = re.search(r'CATEGORY:\s*(\w+)', response)
            if match:
                category = match.group(1).upper()
                # exclude_junk이면 JUNK_SUSPECTED 반환 안함
                if category in categories_to_use:
                    return category
        except Exception as e:
            print(f"LLM 분류 오류: {e}")
        
        # LLM 실패 시 키워드 기반으로 폴백
        if exclude_junk:
            # 정크 제외 시 키워드로도 정크 제외
            keyword_result = self.classify_by_keywords(email)
            return keyword_result if keyword_result != "JUNK_SUSPECTED" else "OTHER"
        return self.classify_by_keywords(email)
    
    def classify(self, email: Email, use_llm: bool = False) -> str:
        """메일 분류 (LLM 또는 키워드 기반)"""
        if use_llm and self.llm_client:
            return self.classify_by_llm(email)
        return self.classify_by_keywords(email)
    
    def classify_batch(self, emails: List[Email], use_llm: bool = False) -> List[Email]:
        """여러 메일 일괄 분류"""
        total = len(emails)
        for idx, email in enumerate(emails):
            try:
                # 항상 재분류 (기존 분류도 새로운 규칙으로 업데이트)
                email.category = self.classify(email, use_llm)
            except Exception as e:
                print(f"  ⚠ 분류 오류 [{idx+1}/{total}]: {email.subject[:30]} - {e}")
                email.category = "OTHER"
            
            # 진행률 표시 (50개마다)
            if (idx + 1) % 50 == 0:
                print(f"  📊 분류 진행: {idx+1}/{total}")
        
        return emails


def group_emails_by_category(emails: List[Email]) -> Dict[str, List[Email]]:
    """카테고리별로 메일 그룹화"""
    groups = {cat: [] for cat in MAIL_CATEGORIES.keys()}
    
    for email in emails:
        category = email.category if email.category else "OTHER"
        if category in groups:
            groups[category].append(email)
        else:
            groups["OTHER"].append(email)
    
    return groups


def group_emails_by_sender(emails: List[Email]) -> Dict[str, List[Email]]:
    """발신자별로 메일 그룹화"""
    groups = {}
    
    for email in emails:
        sender_key = email.sender_email or email.sender
        if sender_key not in groups:
            groups[sender_key] = []
        groups[sender_key].append(email)
    
    return groups


def get_email_statistics(emails: List[Email]) -> Dict:
    """이메일 통계 생성"""
    category_groups = group_emails_by_category(emails)
    sender_groups = group_emails_by_sender(emails)
    
    stats = {
        "total_count": len(emails),
        "unread_count": len([e for e in emails if not e.is_read]),
        "by_category": {
            cat: {
                "count": len(emails_list),
                "label": MAIL_CATEGORIES.get(cat, cat)
            }
            for cat, emails_list in category_groups.items()
        },
        "top_senders": sorted(
            [(sender, len(emails_list)) for sender, emails_list in sender_groups.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10],
        "has_attachments": len([e for e in emails if e.attachments]),
    }
    
    return stats


class EmailAnalyzer:
    """메일 상세 분석기 - 긴급도, 기한, 액션 아이템 추출"""
    
    # 긴급 키워드
    URGENT_KEYWORDS = ["긴급", "urgent", "asap", "즉시", "급히", "시급", "빠른", "당장"]
    
    # 중요 키워드  
    IMPORTANT_KEYWORDS = ["중요", "important", "필독", "반드시", "꼭", "필수"]
    
    # 기한 관련 패턴
    DEADLINE_PATTERNS = [
        # 오늘/내일/모레
        (r'오늘\s*(까지|내|중)', 0),
        (r'금일\s*(까지|내|중)', 0),
        (r'내일\s*(까지|내|중)', 1),
        (r'모레\s*(까지|내|중)', 2),
        # N일 이내/까지
        (r'(\d+)\s*일\s*(이?내|까지|안에)', None),  # 그룹 1에서 숫자 추출
        # 이번 주/다음 주
        (r'이번\s*주\s*(내|까지|중)', 'this_week'),
        (r'금주\s*(내|까지|중)', 'this_week'),
        (r'다음\s*주\s*(내|까지)', 'next_week'),
        # 특정 날짜 (M/D, M월 D일)
        (r'(\d{1,2})/(\d{1,2})\s*(까지)?', 'date'),
        (r'(\d{1,2})월\s*(\d{1,2})일\s*(까지)?', 'date'),
        # 오전/오후 시간
        (r'오후\s*(\d{1,2})\s*시\s*(까지)?', 'today_time'),
        (r'오전\s*(\d{1,2})\s*시\s*(까지)?', 'today_time'),
    ]
    
    # 액션 아이템 패턴
    ACTION_PATTERNS = [
        r'회신\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'답변\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'확인\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'검토\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'참석\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'결재\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'승인\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'준비\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'제출\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'공유\s*(부탁|요청|바랍니다|해\s*주세요)',
        r'피드백\s*(부탁|요청|바랍니다|해\s*주세요)',
    ]
    
    def __init__(self):
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def check_urgency(self, email: Email) -> Tuple[bool, bool, str]:
        """긴급/중요 여부 확인"""
        text = f"{email.subject} {email.body_text}".lower()
        subject_lower = email.subject.lower()
        
        is_urgent = False
        is_important = False
        reasons = []
        
        # 제목에서 [긴급], [중요] 태그 확인
        if re.search(r'\[긴급\]|\[urgent\]', subject_lower):
            is_urgent = True
            reasons.append("제목에 [긴급] 태그")
        
        if re.search(r'\[중요\]|\[important\]', subject_lower):
            is_important = True
            reasons.append("제목에 [중요] 태그")
        
        # 키워드 확인
        for keyword in self.URGENT_KEYWORDS:
            if keyword in text:
                is_urgent = True
                if f"'{keyword}' 키워드" not in reasons:
                    reasons.append(f"'{keyword}' 키워드 포함")
                break
        
        for keyword in self.IMPORTANT_KEYWORDS:
            if keyword in text:
                is_important = True
                break
        
        return is_urgent, is_important, ", ".join(reasons)
    
    def extract_deadline(self, email: Email) -> Tuple[Optional[datetime], str, Optional[int]]:
        """기한/마감일 추출"""
        text = f"{email.subject} {email.body_text}"
        
        for pattern, value in self.DEADLINE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                deadline = None
                deadline_text = match.group(0)
                
                if isinstance(value, int):
                    # 오늘, 내일, 모레
                    deadline = self.today + timedelta(days=value)
                elif value is None:
                    # N일 이내
                    days = int(match.group(1))
                    deadline = self.today + timedelta(days=days)
                elif value == 'this_week':
                    # 이번 주 (금요일까지)
                    days_until_friday = (4 - self.today.weekday()) % 7
                    deadline = self.today + timedelta(days=days_until_friday)
                elif value == 'next_week':
                    # 다음 주 (다음 금요일)
                    days_until_friday = (4 - self.today.weekday()) % 7 + 7
                    deadline = self.today + timedelta(days=days_until_friday)
                elif value == 'date':
                    # 특정 날짜
                    try:
                        month = int(match.group(1))
                        day = int(match.group(2))
                        year = self.today.year
                        deadline = datetime(year, month, day)
                        if deadline < self.today:
                            deadline = datetime(year + 1, month, day)
                    except:
                        pass
                elif value == 'today_time':
                    # 오늘 특정 시간
                    deadline = self.today
                
                if deadline:
                    days_until = (deadline - self.today).days
                    return deadline, deadline_text, days_until
        
        return None, "", None
    
    def extract_action_items(self, email: Email) -> List[str]:
        """액션 아이템 추출"""
        text = email.body_text
        actions = []
        
        action_mapping = {
            '회신': '📩 회신 필요',
            '답변': '📩 답변 필요',
            '확인': '✅ 확인 필요',
            '검토': '📋 검토 필요',
            '참석': '📅 참석 필요',
            '결재': '✍️ 결재 필요',
            '승인': '✍️ 승인 필요',
            '준비': '📦 자료 준비 필요',
            '제출': '📤 제출 필요',
            '공유': '📤 공유 필요',
            '피드백': '💬 피드백 필요',
        }
        
        for pattern in self.ACTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                matched_text = match.group(0)
                for key, action_label in action_mapping.items():
                    if key in matched_text and action_label not in actions:
                        actions.append(action_label)
                        break
        
        # 추가 액션 감지
        if email.attachments:
            if any(ext in str(email.attachments).lower() for ext in ['.xlsx', '.xls', '.csv']):
                actions.append('📊 첨부 데이터 확인 필요')
            elif any(ext in str(email.attachments).lower() for ext in ['.pdf', '.doc', '.docx']):
                actions.append('📄 첨부 문서 확인 필요')
        
        return actions
    
    def calculate_priority_score(self, analysis: EmailAnalysis) -> int:
        """우선순위 점수 계산"""
        score = 0
        
        # 카테고리별 기본 점수
        category_scores = {
            "REPLY_REQUIRED": 60,
            "APPROVAL_REQUEST": 55,
            "TASK_REQUEST": 50,
            "MEETING_REQUEST": 45,
            "REPORT": 30,
            "SIMPLE_NOTICE": 20,
            "OTHER": 10
        }
        score += category_scores.get(analysis.email.category, 10)
        
        # 긴급/중요 가산점
        if analysis.is_urgent:
            score += 100
        if analysis.is_important:
            score += 50
        
        # 기한 가산점 (기한이 가까울수록 높은 점수)
        if analysis.days_until_deadline is not None:
            if analysis.days_until_deadline <= 0:  # 오늘 또는 지남
                score += 80
            elif analysis.days_until_deadline == 1:  # 내일
                score += 60
            elif analysis.days_until_deadline <= 3:  # 3일 이내
                score += 40
            elif analysis.days_until_deadline <= 7:  # 일주일 이내
                score += 20
        
        # 액션 아이템 개수 가산점
        score += len(analysis.action_items) * 5
        
        # 미읽음 가산점
        if not analysis.email.is_read:
            score += 10
        
        return score
    
    def analyze_email(self, email: Email) -> EmailAnalysis:
        """단일 메일 분석"""
        is_urgent, is_important, urgency_reason = self.check_urgency(email)
        deadline, deadline_text, days_until = self.extract_deadline(email)
        action_items = self.extract_action_items(email)
        
        analysis = EmailAnalysis(
            email=email,
            is_urgent=is_urgent,
            is_important=is_important,
            deadline=deadline,
            deadline_text=deadline_text,
            days_until_deadline=days_until,
            action_items=action_items,
            urgency_reason=urgency_reason
        )
        
        analysis.priority_score = self.calculate_priority_score(analysis)
        
        return analysis
    
    def analyze_batch(self, emails: List[Email]) -> List[EmailAnalysis]:
        """여러 메일 일괄 분석"""
        analyses = [self.analyze_email(email) for email in emails]
        # 우선순위 점수로 정렬
        analyses.sort(key=lambda x: x.priority_score, reverse=True)
        return analyses
    
    def get_priority_emails(self, emails: List[Email], top_n: int = 10) -> List[EmailAnalysis]:
        """우선 처리 필요 메일 추출"""
        analyses = self.analyze_batch(emails)
        return analyses[:top_n]


def get_deadline_status_text(days: Optional[int]) -> Tuple[str, str]:
    """기한까지 남은 일수에 따른 상태 텍스트와 색상"""
    if days is None:
        return "", ""
    elif days < 0:
        return f"⚠️ {abs(days)}일 지남!", "🔴"
    elif days == 0:
        return "🚨 오늘 마감!", "🔴"
    elif days == 1:
        return "⏰ 내일 마감", "🟠"
    elif days <= 3:
        return f"⏳ {days}일 남음", "🟡"
    elif days <= 7:
        return f"📅 {days}일 남음", "🟢"
    else:
        return f"📅 {days}일 남음", "🔵"
