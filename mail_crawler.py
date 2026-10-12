"""
메일 파싱 모듈

EML 파일 파싱 및 emails.json 관리 기능 제공
"""
import email as _email_module
from email.header import decode_header
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import re
import json
import os

@dataclass
class ForwardedEmailInfo:
    """전달된 메일의 원본 메일 정보"""
    original_sender: str = ""           # 보낸사람
    original_sender_email: str = ""     # 보낸사람 이메일
    original_date: str = ""             # 보낸 날짜
    original_to: List[str] = field(default_factory=list)  # 받는 사람들
    original_cc: List[str] = field(default_factory=list)  # 참조
    original_subject: str = ""          # 제목
    original_body: str = ""             # 본문 내용
    
    def to_dict(self):
        return {
            "original_sender": self.original_sender,
            "original_sender_email": self.original_sender_email,
            "original_date": self.original_date,
            "original_to": self.original_to,
            "original_cc": self.original_cc,
            "original_subject": self.original_subject,
            "original_body": self.original_body,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data) if data else cls()


@dataclass
class Email:
    """이메일 데이터 클래스"""
    id: str
    subject: str
    sender: str
    sender_email: str
    recipients: List[str]
    date: datetime
    body_text: str
    body_html: str = ""
    attachments: List[str] = field(default_factory=list)
    category: str = ""
    is_read: bool = False
    forwarded_from: ForwardedEmailInfo = field(default_factory=ForwardedEmailInfo)  # 전달 메일 원본 정보
    
    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "recipients": self.recipients,
            "date": self.date.isoformat() if self.date else None,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "attachments": self.attachments,
            "category": self.category,
            "is_read": self.is_read,
            "forwarded_from": self.forwarded_from.to_dict() if self.forwarded_from else {}
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        data['date'] = datetime.fromisoformat(data['date']) if data.get('date') else None
        forwarded_data = data.pop('forwarded_from', {})
        email = cls(**data)
        if forwarded_data:
            email.forwarded_from = ForwardedEmailInfo.from_dict(forwarded_data)
        return email



def save_emails_to_json(emails: List[Email], filepath: str):
    """이메일 리스트를 JSON 파일로 저장"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data = [e.to_dict() for e in emails]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_emails_from_json(filepath: str) -> List[Email]:
    """JSON 파일에서 이메일 리스트 로드"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [Email.from_dict(d) for d in data]


def _decode_header_str(value: str) -> str:
    """헤더 값 디코딩 (독립 유틸)"""
    from email.header import decode_header as _dh
    if not value:
        return ""
    parts = _dh(value)
    result = []
    for b, cs in parts:
        if isinstance(b, bytes):
            result.append(b.decode(cs or "utf-8", errors="ignore"))
        else:
            result.append(b)
    return "".join(result)


def _extract_forwarded_email_from_html(html_body: str) -> ForwardedEmailInfo:
    """
    HTML body에서 전달된 메일의 원본 정보 추출
    
    Outlook 한글 형식:
    <b>보낸 사람:</b> 이름 <email>
    <b>보낸 날짜:</b> 날짜 정보
    <b>받는 사람:</b> 받는사람1; 받는사람2
    <b>참조:</b> 참조자1; 참조자2
    <b>제목:</b> 원본 메일 제목
    """
    info = ForwardedEmailInfo()
    
    if not html_body:
        return info
    
    try:
        # HTML 엔티티 디코딩
        import html as html_module
        html_body = html_module.unescape(html_body)
        
        # 라인 단위로 파싱하기 위해 여러 개행 형식 통일
        html_body = re.sub(r'<br\s*/?>', '\n', html_body, flags=re.IGNORECASE)
        html_body = re.sub(r'</div>', '\n', html_body, flags=re.IGNORECASE)
        html_body = re.sub(r'<[^>]+>', '', html_body)  # 모든 HTML 태그 제거
        
        lines = html_body.split('\n')
        
        # 각 필드별 정규식 패턴 (한글)
        for idx, original_line in enumerate(lines):
            line = original_line.strip()
            if not line:
                continue
            
            # 보낸 사람: 이름 <email>
            if re.match(r'^보낸\s*사람\s*[:：]', line):
                sender_info = re.sub(r'^보낸\s*사람\s*[:：]\s*', '', line).strip()
                email_match = re.search(r'<([^>]+)>', sender_info)
                if email_match:
                    info.original_sender_email = email_match.group(1)
                    info.original_sender = sender_info[:email_match.start()].strip().strip('"')
                else:
                    info.original_sender = sender_info
            
            # 보낸 날짜: 날짜
            elif re.match(r'^보낸\s*날짜\s*[:：]', line):
                date_info = re.sub(r'^보낸\s*날짜\s*[:：]\s*', '', line).strip()
                info.original_date = date_info
            
            # 받는 사람: 받는사람1; 받는사람2
            elif re.match(r'^받는\s*사람\s*[:：]', line):
                to_info = re.sub(r'^받는\s*사람\s*[:：]\s*', '', line).strip()
                info.original_to = [t.strip() for t in to_info.split(';') if t.strip()]
            
            # 참조: 참조자1; 참조자2
            elif re.match(r'^참조\s*[:：]', line):
                cc_info = re.sub(r'^참조\s*[:：]\s*', '', line).strip()
                info.original_cc = [c.strip() for c in cc_info.split(';') if c.strip()]
            
            # 제목: 제목
            elif re.match(r'^제목\s*[:：]', line):
                subject = re.sub(r'^제목\s*[:：]\s*', '', line).strip()
                info.original_subject = subject
                # 제목 이후로는 본문이 시작됨
                body_start_idx = idx + 1
                if body_start_idx < len(lines):
                    info.original_body = '\n'.join(lines[body_start_idx:]).strip()
                break
    
    except Exception as e:
        # 파싱 중 오류 발생 시 로그만 남기고 빈 정보 반환
        import sys
        print(f"[경고] HTML body 파싱 중 오류: {e}", file=sys.stderr)
    
    return info


def _extract_forwarded_email_from_text(text_body: str) -> ForwardedEmailInfo:
    """
    Text body에서 전달된 메일의 원본 정보 추출
    
    포맷:
    ________________________________________
    보낸 사람: 이름 <email>
    보낸 날짜: 날짜
    받는 사람: 받는사람1; 받는사람2
    참조: 참조자
    제목: 원본 메일 제목
    
    원본 본문...
    """
    info = ForwardedEmailInfo()
    
    if not text_body:
        return info
    
    try:
        lines = text_body.split('\n')
        subject_found = False
        subject_line_idx = -1
        
        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 보낸 사람: 이름 <email>
            if re.match(r'^보낸\s*사람\s*[:：]', line_stripped):
                sender_info = re.sub(r'^보낸\s*사람\s*[:：]\s*', '', line_stripped).strip()
                email_match = re.search(r'<([^>]+)>', sender_info)
                if email_match:
                    info.original_sender_email = email_match.group(1)
                    info.original_sender = sender_info[:email_match.start()].strip().strip('"')
                else:
                    info.original_sender = sender_info
            
            # 보낸 날짜: 날짜
            elif re.match(r'^보낸\s*날짜\s*[:：]', line_stripped):
                date_info = re.sub(r'^보낸\s*날짜\s*[:：]\s*', '', line_stripped).strip()
                info.original_date = date_info
            
            # 받는 사람: 받는사람1; 받는사람2
            elif re.match(r'^받는\s*사람\s*[:：]', line_stripped):
                to_info = re.sub(r'^받는\s*사람\s*[:：]\s*', '', line_stripped).strip()
                info.original_to = [t.strip() for t in to_info.split(';') if t.strip()]
            
            # 참조: 참조자1; 참조자2
            elif re.match(r'^참조\s*[:：]', line_stripped):
                cc_info = re.sub(r'^참조\s*[:：]\s*', '', line_stripped).strip()
                info.original_cc = [c.strip() for c in cc_info.split(';') if c.strip()]
            
            # 제목: 제목
            elif re.match(r'^제목\s*[:：]', line_stripped):
                subject = re.sub(r'^제목\s*[:：]\s*', '', line_stripped).strip()
                info.original_subject = subject
                subject_found = True
                subject_line_idx = idx
                break
        
        # 제목 이후로 본문 추출
        if subject_found and subject_line_idx + 1 < len(lines):
            info.original_body = '\n'.join(lines[subject_line_idx + 1:]).strip()
    
    except Exception as e:
        # 파싱 중 오류 발생 시 로그만 남기고 빈 정보 반환
        import sys
        print(f"[경고] Text body 파싱 중 오류: {e}", file=sys.stderr)
    
    return info


def parse_eml_file(eml_path: str) -> Email:
    """단일 .eml 파일을 Email 객체로 변환"""
    import email as _email
    from email.utils import parsedate_to_datetime as _pdt
    import hashlib

    with open(eml_path, "rb") as f:
        msg = _email.message_from_bytes(f.read())

    subject = _decode_header_str(msg.get("Subject", ""))
    from_raw = _decode_header_str(msg.get("From", ""))
    to_raw = _decode_header_str(msg.get("To", ""))
    date_str = msg.get("Date", "")

    # 발신자 이름/이메일 분리
    sender_name, sender_email_addr = from_raw, from_raw
    m = re.search(r"<([^>]+)>", from_raw)
    if m:
        sender_email_addr = m.group(1)
        sender_name = from_raw[: m.start()].strip().strip('"') or sender_email_addr

    # 수신자 목록
    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]

    # 날짜 파싱
    try:
        date = _pdt(date_str)
    except Exception:
        date = datetime.now()

    # 본문 추출 (text/plain 우선)
    body_text = ""
    body_html = ""
    attachments = []

    for part in msg.walk():
        content_type = part.get_content_type()
        disp = str(part.get("Content-Disposition", ""))
        if "attachment" in disp:
            fname = part.get_filename()
            if fname:
                attachments.append(_decode_header_str(fname))
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        cs = part.get_content_charset() or "utf-8"
        decoded = payload.decode(cs, errors="ignore")
        if content_type == "text/plain" and not body_text:
            body_text = decoded
        elif content_type == "text/html" and not body_html:
            body_html = decoded

    # ID: 파일명 기반 해시 (중복 방지)
    email_id = "eml_" + hashlib.md5(os.path.basename(eml_path).encode("utf-8")).hexdigest()[:12]

    # ── 전달/FW 메일의 실 발신자 추출 (본문 트리밍 전에 먼저 수행) ──────────
    # 한글 Outlook 전달 포맷: "보낸 사람: 이름(EnglishName) <email>"
    # 영문 FW 포맷          : "From: 이름 <email>" (본문 내 첫 번째 From 블록)
    _fwd_name = None
    _fwd_email = None

    kor_m = re.search(r"보낸\s*사람\s*:\s*(.+?)(?:\r?\n|$)", body_text)
    if kor_m:
        raw = kor_m.group(1).strip()
        em_m = re.search(r"<([^>]+)>", raw)
        if em_m:
            _fwd_email = em_m.group(1).strip()
            _fwd_name = raw[: em_m.start()].strip().strip('"') or _fwd_email
        else:
            _fwd_name = raw
    else:
        # 영문 FW 포맷: 본문 첫 번째 "From: ..." 줄
        eng_m = re.search(r"(?:^|\r?\n)From:\s+(.+?)(?:\r?\n|$)", body_text)
        if eng_m:
            raw = eng_m.group(1).strip()
            em_m = re.search(r"<([^>]+)>", raw)
            if em_m:
                _fwd_email = em_m.group(1).strip()
                _fwd_name = raw[: em_m.start()].strip().strip('"') or _fwd_email
            else:
                _fwd_name = raw

    # 전달/FW 여부 판단 후 발신자 덮어쓰기
    _is_forward = (
        bool(re.search(r"(전달|fw|fwd)\s*[:：]", subject, re.IGNORECASE))
        or "_전달" in os.path.basename(eml_path)
        or "보낸 사람:" in body_text
        or bool(re.search(r"(?:^|\r?\n)From:\s+", body_text))
    )
    if _is_forward and _fwd_name:
        sender_name = _fwd_name
        if _fwd_email:
            sender_email_addr = _fwd_email

    # ── 전달/회신 메일 본문에서 포워딩 헤더 블록 제거 ──────────────────────
    # 한글 포맷: "보낸 사람:", "보낸 날짜:", "받는 사람:" 다음에 "제목:" 등장
    # 영문 포맷: "From:", "Sent:", "To:" 다음에 "Subject:" 등장
    # → "제목:" 또는 "Subject:" 줄을 찾아 거기서부터 시작
    subject_match = re.search(r"(?:^|\r?\n)(제목\s*:.+)", body_text)
    if not subject_match:
        subject_match = re.search(r"(?:^|\r?\n)(Subject\s*:.+)", body_text, re.IGNORECASE)
    if subject_match:
        body_text = body_text[subject_match.start(1):]

    # ── 전달 메일의 조건 확인 및 원본 정보 추출 ──────────────────────
    # 조건: 제목에 '전달:' 포함 AND (발신자가 전유진 OR 유재철) AND 수신자가 전유진
    # → 이 경우 원본 메일 정보로 완전히 대체
    forwarded_info = ForwardedEmailInfo()
    forwarded_from_sender = sender_name  # 전달자 정보 저장
    forwarded_from_sender_email = sender_email_addr
    
    subject_has_forward = "전달:" in subject or "FW:" in subject or "Fwd:" in subject
    sender_is_yujin_or_jaeseol = sender_email_addr in ["8921246@hanwha.com", "8921242@hanwha.com"]
    to_is_yujin = any("youjin0404@hanwha.com" in r for r in recipients)
    
    if subject_has_forward and sender_is_yujin_or_jaeseol and to_is_yujin:
        # HTML body 우선, 없으면 text body에서 추출
        if body_html:
            forwarded_info = _extract_forwarded_email_from_html(body_html)
        if not forwarded_info.original_subject and body_text:
            forwarded_info = _extract_forwarded_email_from_text(body_text)
        
        # 원본 정보로 메일 정보 대체
        if forwarded_info.original_sender:
            subject = forwarded_info.original_subject or subject
            sender_name = forwarded_info.original_sender
            sender_email_addr = forwarded_info.original_sender_email
            recipients = forwarded_info.original_to or recipients
            body_text = forwarded_info.original_body or body_text
            
            # 제목에서 "전달:" 제거
            subject = re.sub(r'^전달\s*[:：]\s*', '', subject).strip()
            subject = re.sub(r'^FW\s*[:：]\s*', '', subject, flags=re.IGNORECASE).strip()
            subject = re.sub(r'^Fwd\s*[:：]\s*', '', subject, flags=re.IGNORECASE).strip()
            
            # 전달자 정보를 forwarded_from에 저장 (역할 변경)
            forwarded_info = ForwardedEmailInfo()
            forwarded_info.original_sender = forwarded_from_sender
            forwarded_info.original_sender_email = forwarded_from_sender_email
            forwarded_info.original_date = date_str
            forwarded_info.original_to = [r for r in recipients if r]  # 현재 수신자가 원본 수신자로 변경됨

    return Email(
        id=email_id,
        subject=subject,
        sender=sender_name,
        sender_email=sender_email_addr,
        recipients=recipients,
        date=date,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
        is_read=True,  # 백업 파일은 이미 읽은 것으로 처리
        forwarded_from=forwarded_info,
    )


EML_FILENAME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{4}_[^_]+_전달"
)
"""날짜 순번_이름_전달 규칙에 맞는 .eml 파일명 필터 패턴"""


def import_eml_directory(
    eml_dir: str,
    json_path: str,
    classify: bool = True,
    force: bool = False,
    filename_filter: re.Pattern = EML_FILENAME_PATTERN,
) -> tuple:
    """eml_dir 내 .eml 파일 중 filename_filter 패턴에 맞는 파일만 파싱하여
    json_path의 emails.json에 병합 저장.

    파일명 규칙: YYYY-MM-DD HHMM_이름_전달 제목.eml
    (filename_filter=None 으로 호출하면 전체 .eml 파일을 처리)

    Args:
        force: True이면 이미 존재하는 eml_ ID도 재파싱하여 덮어씀

    Returns:
        (추가/갱신된 수, 건너뛴 수)
    """
    all_eml = [f for f in os.listdir(eml_dir) if f.lower().endswith(".eml")]
    if filename_filter is not None:
        matched = [f for f in all_eml if filename_filter.match(f)]
        skipped_by_name = len(all_eml) - len(matched)
        if skipped_by_name:
            print(f"  ℹ 파일명 패턴 불일치로 제외: {skipped_by_name}개")
    else:
        matched = all_eml

    eml_files = [os.path.join(eml_dir, f) for f in matched]
    if not eml_files:
        print(f"⚠ .eml 파일 없음: {eml_dir}")
        return 0, 0

    # 기존 데이터 로드
    existing = load_emails_from_json(json_path)
    # eml_ 이외 항목은 그대로 유지; eml_ 항목은 force 시 교체 대상
    non_eml = [e for e in existing if not e.id.startswith("eml_")]
    existing_eml_ids = {e.id for e in existing if e.id.startswith("eml_")}

    new_emails = []
    skipped = 0
    for path in eml_files:
        try:
            em = parse_eml_file(path)
        except Exception as e:
            print(f"  ✗ 파싱 실패: {os.path.basename(path)} — {e}")
            continue
        if em.id in existing_eml_ids and not force:
            skipped += 1
            continue
        new_emails.append(em)
        action = "갱신" if em.id in existing_eml_ids else "추가"
        print(f"  ✓ [{action}] {os.path.basename(path)}")

    if new_emails and classify:
        from mail_classifier import MailClassifier
        classifier = MailClassifier()
        new_emails = classifier.classify_batch(new_emails)

    # ★ force=False 시 skipped된 기존 eml 메일 보존 (손실 방지)
    new_email_ids = {e.id for e in new_emails}
    preserved_eml = [e for e in existing if e.id.startswith("eml_") and e.id not in new_email_ids]
    merged = non_eml + preserved_eml + new_emails
    save_emails_to_json(merged, json_path)
    return len(new_emails), skipped


# 데모/테스트용 샘플 데이터 생성
def create_sample_emails() -> List[Email]:
    """테스트용 샘플 이메일 데이터 생성"""
    from datetime import timedelta
    
    sample_emails = [
        Email(
            id="1",
            subject="[긴급] 프로젝트 진행상황 회신 요청",
            sender="김부장",
            sender_email="kim.bj@company.com",
            recipients=["me@company.com"],
            date=datetime.now() - timedelta(hours=2),
            body_text="""안녕하세요,

현재 진행 중인 AX 프로젝트 관련하여 긴급히 진행상황 공유 부탁드립니다.
특히 아래 사항에 대해 회신 부탁드립니다:

1. 현재 개발 진척률
2. 이슈사항 및 리스크
3. 다음 주 계획

금일 오후 5시까지 회신 부탁드립니다.

감사합니다.
김부장 드림""",
            category="REPLY_REQUIRED"
        ),
        Email(
            id="2", 
            subject="[중요] 내일까지 검토 요청 - 계약서 최종본",
            sender="법무팀",
            sender_email="legal@company.com",
            recipients=["me@company.com"],
            date=datetime.now() - timedelta(hours=3),
            body_text="""안녕하세요,

신규 파트너사 계약서 최종본 검토 요청드립니다.
중요한 계약이라 반드시 확인 부탁드립니다.

- 계약 상대: ABC 테크놀로지
- 계약 기간: 2026.05 ~ 2027.04 (1년)
- 계약 금액: 1억원

내일(5/6) 오전까지 검토 의견 회신 부탁드립니다.
피드백 주시면 최종 수정 후 서명 진행 예정입니다.

감사합니다.
법무팀 드림""",
            attachments=["계약서_최종본_v3.pdf"],
            category="REPLY_REQUIRED"
        ),
        Email(
            id="3",
            subject="[회의초대] 주간 정기 미팅 - 5/6(화) 10:00",
            sender="박대리",
            sender_email="park.dr@company.com",
            recipients=["me@company.com", "team@company.com"],
            date=datetime.now() - timedelta(hours=5),
            body_text="""안녕하세요,

주간 정기 미팅 일정 안내드립니다.

- 일시: 5/6(화) 10:00 - 11:00
- 장소: 회의실 A (또는 Teams 온라인)
- 안건: 주간 업무 공유 및 이슈 논의

참석 여부 회신 부탁드립니다.

감사합니다.""",
            category="MEETING_REQUEST"
        ),
        Email(
            id="4",
            subject="[공지] 5월 휴무일 안내",
            sender="인사팀",
            sender_email="hr@company.com", 
            recipients=["all@company.com"],
            date=datetime.now() - timedelta(days=1),
            body_text="""전 직원분들께 안내드립니다.

5월 휴무일을 안내해 드립니다.

- 5/5(목) 어린이날
- 5/6(금) 대체휴일

업무에 참고 부탁드립니다.

인사팀 드림""",
            category="SIMPLE_NOTICE"
        ),
        Email(
            id="5",
            subject="[긴급][결재요청] 출장비 정산 승인 건 - 오늘 마감",
            sender="이과장",
            sender_email="lee.gj@company.com",
            recipients=["me@company.com"],
            date=datetime.now() - timedelta(hours=1),
            body_text="""안녕하세요,

4월 서울 출장 관련 출장비 정산 결재 긴급 요청드립니다.
오늘까지 결재가 완료되어야 이번 달 급여에 반영됩니다.

- 출장일: 4/25 ~ 4/27
- 총 금액: 450,000원
- 세부내역: 첨부파일 참조

오늘 오후 3시까지 결재 부탁드립니다.

감사합니다.""",
            attachments=["출장비_정산서.xlsx"],
            category="APPROVAL_REQUEST"
        ),
        Email(
            id="6",
            subject="[보고] 4월 월간 실적 보고서",
            sender="최사원",
            sender_email="choi.sw@company.com",
            recipients=["me@company.com", "manager@company.com"],
            date=datetime.now() - timedelta(days=2),
            body_text="""안녕하세요,

4월 월간 실적 보고서 공유드립니다.

[요약]
- 매출: 전월 대비 15% 증가
- 신규 고객: 23건 유치
- 주요 성과: AX 프로젝트 1차 마일스톤 달성

자세한 내용은 첨부파일 참고 부탁드립니다.

감사합니다.""",
            attachments=["4월_월간보고서.pdf", "실적_데이터.xlsx"],
            category="REPORT"
        ),
        Email(
            id="7",
            subject="[중요] 자료 준비 요청 - 3일 이내",
            sender="정팀장",
            sender_email="jung.tl@company.com",
            recipients=["me@company.com"],
            date=datetime.now() - timedelta(hours=6),
            body_text="""안녕하세요,

경영진 보고 관련하여 아래 자료 준비 요청드립니다.
중요한 보고 자료이니 꼭 기한 내에 준비 부탁드립니다.

1. 프로젝트 일정표 (간트차트)
2. 투입 인력 현황
3. 예산 집행 현황

3일 이내 (5/8까지) 준비 부탁드립니다.

감사합니다.""",
            category="TASK_REQUEST"
        ),
        Email(
            id="8",
            subject="Re: 점심 식사 제안",
            sender="동료A",
            sender_email="colleague.a@company.com",
            recipients=["me@company.com"],
            date=datetime.now() - timedelta(hours=3),
            body_text="""좋아요! 12시에 로비에서 만나요~""",
            category="OTHER"
        ),
        Email(
            id="9",
            subject="[회의] 신규 프로젝트 킥오프 미팅 - 이번 주 내 참석 확인 필요",
            sender="PM김",
            sender_email="pm.kim@company.com",
            recipients=["me@company.com", "dev-team@company.com"],
            date=datetime.now() - timedelta(hours=1),
            body_text="""안녕하세요,

신규 프로젝트 'BX 시스템 구축' 킥오프 미팅을 안내드립니다.

- 일시: 5/7(수) 14:00 - 16:00
- 장소: 대회의실
- 참석 대상: 개발팀 전원, 기획팀
- 준비물: 노트북

이번 주 내로 참석 여부 회신 부탁드립니다.
필참 부탁드립니다.

감사합니다.""",
            category="MEETING_REQUEST"
        ),
        Email(
            id="10",
            subject="[긴급][중요] 보안 패치 적용 요청 - ASAP",
            sender="IT보안팀",
            sender_email="security@company.com",
            recipients=["me@company.com", "dev-team@company.com"],
            date=datetime.now() - timedelta(minutes=30),
            body_text="""긴급 공지드립니다.

최근 발견된 보안 취약점 관련하여 즉시 패치 적용이 필요합니다.

[조치사항]
1. 첨부된 보안 패치 다운로드
2. 오늘 중으로 개발 서버에 적용
3. 적용 완료 후 확인 회신

보안 이슈이므로 ASAP 처리 부탁드립니다.
오늘 퇴근 전까지 완료 확인 부탁드립니다.

IT보안팀 드림""",
            attachments=["security_patch_v2.1.zip", "적용가이드.pdf"],
            category="TASK_REQUEST"
        )
    ]
    
    return sample_emails
