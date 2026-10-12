# 전달 메일 파싱 기능 문서

## 개요
`mail_crawler.py`에 전달 메일(Forwarded email)의 원본 메일 정보를 추출하는 기능이 추가되었습니다.

## 주요 변경사항

### 1. 새로운 데이터 클래스: `ForwardedEmailInfo`
원본 메일 정보를 담는 데이터 클래스입니다.

```python
@dataclass
class ForwardedEmailInfo:
    """전달된 메일의 원본 메일 정보"""
    original_sender: str             # 보낸사람
    original_sender_email: str       # 보낸사람 이메일
    original_date: str               # 보낸 날짜
    original_to: List[str]           # 받는 사람들
    original_cc: List[str]           # 참조
    original_subject: str            # 제목
    original_body: str               # 본문 내용
```

### 2. `Email` 클래스 확장
`Email` 클래스에 `forwarded_from` 필드가 추가되었습니다.

```python
@dataclass
class Email:
    # ... 기존 필드들 ...
    forwarded_from: ForwardedEmailInfo  # 전달 메일 원본 정보
```

### 3. 파싱 함수들

#### `_extract_forwarded_email_from_html(html_body: str) -> ForwardedEmailInfo`
HTML body에서 원본 메일 정보를 추출합니다.

**Outlook 한글 형식 예시:**
```html
<b>보낸 사람:</b> 이름(Name) &lt;email@company.com&gt;<br>
<b>보낸 날짜:</b> 2026년 4월 30일 오전 12:39:32 (UTC+09:00) 서울<br>
<b>받는 사람:</b> 받는사람1; 받는사람2<br>
<b>참조:</b> 참조자1; 참조자2<br>
<b>제목:</b> 원본 메일 제목
```

#### `_extract_forwarded_email_from_text(text_body: str) -> ForwardedEmailInfo`
Text body에서 원본 메일 정보를 추출합니다.

**포맷 예시:**
```
________________________________________
보낸 사람: 이름 <email@company.com>
보낸 날짜: 2026년 4월 30일 오전 12:39:32 (UTC+09:00)
받는 사람: 받는사람1; 받는사람2
참조: 참조자
제목: 원본 메일 제목

원본 본문 내용...
```

### 4. 전달 메일 감지 로직
`parse_eml_file()` 함수에서 다음 조건을 만족하는 메일에 대해 원본 정보를 추출합니다:

1. **제목에 '전달:' 포함**: "전달:", "FW:", "Fwd:" 중 하나 포함
2. **발신자가 특정 사용자**: 
   - 전유진 (8921246@hanwha.com)
   - 유재철 (8921242@hanwha.com)
3. **수신자가 전유진**: youjin0404@hanwha.com 포함

이 조건을 모두 만족하면 HTML body 또는 text body에서 원본 정보를 추출합니다.

## 사용 예시

```python
from mail_crawler import parse_eml_file

# EML 파일 파싱
email = parse_eml_file("mail_data/2026-04-30_전달_메일.eml")

# 전달 메일의 경우 forwarded_from에 원본 정보가 저장됨
if email.forwarded_from.original_sender:
    print(f"원본 발신자: {email.forwarded_from.original_sender}")
    print(f"원본 제목: {email.forwarded_from.original_subject}")
    print(f"원본 본문: {email.forwarded_from.original_body}")
```

## JSON 저장 형식

emails.json에 저장될 때 다음과 같은 구조로 저장됩니다:

```json
{
  "id": "eml_...",
  "subject": "전달: 원본 메일 제목",
  "sender": "전유진",
  "sender_email": "8921246@hanwha.com",
  "recipients": ["youjin0404@hanwha.com"],
  "date": "2026-04-30T12:39:32+09:00",
  "body_text": "...",
  "body_html": "...",
  "attachments": [],
  "category": "",
  "is_read": true,
  "forwarded_from": {
    "original_sender": "이름",
    "original_sender_email": "email@company.com",
    "original_date": "2026년 4월 30일 오전 12:39:32",
    "original_to": ["받는사람1", "받는사람2"],
    "original_cc": ["참조자"],
    "original_subject": "원본 메일 제목",
    "original_body": "원본 본문 내용"
  }
}
```

## 주의사항

1. HTML body와 text body 모두 파싱을 시도합니다 (HTML 우선)
2. HTML 엔티티 자동 디코딩
3. 여러 개행 형식 통일 처리
4. 정규식으로 유연하게 필드 구분자(`:`, `：`) 처리
5. 제목 이후 모든 내용을 본문으로 취급

## 테스트

`test_forwarded_parsing.py` 스크립트로 테스트할 수 있습니다:

```bash
python test_forwarded_parsing.py
```
