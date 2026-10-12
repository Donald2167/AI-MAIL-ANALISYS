# 전달 메일 파싱 기능 구현 완료

## 📋 구현 내용

`mail_crawler.py`에 **전달 메일의 원본 메일 정보 추출 기능**이 구현되었습니다.

### 조건
다음 **3가지 조건을 모두 만족**하는 메일에서만 원본 정보를 추출합니다:

1. **제목에 '전달:' 포함** 
   - "전달:", "FW:", "Fwd:" 중 하나

2. **발신자가 다음 중 하나**
   - 전유진 (8921246@hanwha.com)
   - 유재철 (8921242@hanwha.com)

3. **수신자에 전유진 포함**
   - youjin0404@hanwha.com

---

## 🔍 파싱 대상

### HTML body에서 추출하는 정보
```
보낸 사람: [이름] <[이메일]>
보낸 날짜: [날짜]
받는 사람: [받는사람1]; [받는사람2]
참조: [참조자1]; [참조자2]
제목: [원본 메일 제목]
[본문 내용...]
```

### Text body 형식도 동일하게 지원

---

## 📦 데이터 구조

### `ForwardedEmailInfo` 클래스
```python
@dataclass
class ForwardedEmailInfo:
    original_sender: str              # 보낸사람
    original_sender_email: str        # 보낸사람 이메일
    original_date: str                # 보낸 날짜
    original_to: List[str]            # 받는 사람들
    original_cc: List[str]            # 참조
    original_subject: str             # 제목
    original_body: str                # 본문 내용
```

### `Email` 클래스 확장
```python
@dataclass
class Email:
    # ... 기존 필드들 ...
    forwarded_from: ForwardedEmailInfo  # 전달 메일 원본 정보 (新)
```

---

## 💻 사용 방법

### 기본 사용
```python
from mail_crawler import parse_eml_file

# EML 파일 파싱
email = parse_eml_file("mail_data/전달_메일.eml")

# 원본 메일 정보 접근
if email.forwarded_from.original_sender:
    print(f"원본 발신자: {email.forwarded_from.original_sender}")
    print(f"원본 제목: {email.forwarded_from.original_subject}")
    print(f"원본 본문: {email.forwarded_from.original_body}")
```

### 배치 처리
```python
from mail_crawler import import_eml_directory

# 모든 메일 가져오기
added, skipped = import_eml_directory(
    eml_dir="mail_data",
    json_path="data/emails.json",
    classify=True
)
```

### JSON 저장 형식
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
    "original_sender": "Lee Hee Won",
    "original_sender_email": "lhw@company.com",
    "original_date": "2026년 4월 30일 오전 12:39:32",
    "original_to": ["받는사람1", "받는사람2"],
    "original_cc": ["참조자"],
    "original_subject": "원본 메일 제목",
    "original_body": "원본 본문 내용"
  }
}
```

---

## 📝 구현된 함수

| 함수명 | 설명 |
|--------|------|
| `_extract_forwarded_email_from_html()` | HTML body에서 원본 메일 정보 추출 |
| `_extract_forwarded_email_from_text()` | Text body에서 원본 메일 정보 추출 |
| `parse_eml_file()` | 수정됨: 조건 확인 후 원본 정보 추출 |

---

## 🎯 주요 특징

✅ **HTML 우선 처리**: HTML body가 있으면 먼저 파싱, 없으면 text body 사용

✅ **유연한 구분자**: 콜론(`:`) 및 전각 콜론(`：`) 모두 지원

✅ **HTML 엔티티 자동 디코딩**: `&lt;`, `&gt;` 등 자동 변환

✅ **개행 형식 정규화**: `<br>`, `</div>`, `\r\n` 등 통일

✅ **이메일 주소 추출**: `<이메일>` 형식에서 자동 추출

✅ **다중 수신자/참조자 처리**: 세미콜론으로 구분된 여러 주소 처리

---

## 📂 관련 파일

- **mail_crawler.py** - 구현체 (수정됨)
- **FORWARDED_EMAIL_PARSING.md** - 상세 문서
- **examples_forwarded_parsing.py** - 사용 예시
- **test_forwarded_parsing.py** - 테스트 스크립트

---

## ✨ 다음 단계

이 기능을 활용하여 다음을 할 수 있습니다:

1. **원본 메일 내용 분석** - 실제 중요 정보는 원본 메일에 있음
2. **발신자별 메일 분류** - 원본 발신자 기준으로 분류
3. **메일 체인 추적** - 전달 거래(forwarding chain) 분석
4. **주제별 분석** - 원본 제목/본문 기준 분류
5. **통계 생성** - 원본 발신자별 메일 통계

---

## 🔧 설정 커스터마이징

조건을 변경하려면 `parse_eml_file()` 함수의 다음 부분을 수정하세요:

```python
# 조건 변경 예시
subject_has_forward = "전달:" in subject  # 조건 1: 제목 필터
sender_is_yujin_or_jaeseol = sender_email_addr in [...]  # 조건 2: 발신자 필터
to_is_yujin = any("youjin0404@hanwha.com" in r for r in recipients)  # 조건 3: 수신자 필터
```

---

## 📌 주의사항

- 조건을 만족하지 않는 메일의 `forwarded_from`은 **빈 객체**입니다
- 원본 정보 추출 실패 시 기존 메일 정보는 정상 저장됩니다
- 조건을 `None`으로 설정하면 **모든 메일**에서 원본 정보 추출을 시도합니다

---

**구현 완료! 🎉**
