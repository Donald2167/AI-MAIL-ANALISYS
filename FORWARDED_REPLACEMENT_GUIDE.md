# 전달 메일 정보 대체 파싱 기능

## 📋 변경 사항 정리

### 이전 동작
- 원본 정보를 `forwarded_from` 필드에만 저장
- 메일의 기본 정보(subject, sender, recipients 등)는 전달자 정보 유지

### 새로운 동작 (업데이트)
- **원본 메일 정보로 완전히 대체**
- 제목에서 "전달:" 제거
- 전달자 정보는 `forwarded_from`에 역할 변경

---

## 🎯 적용 조건 (3가지 모두 만족)

1. **제목에 '전달:' 포함**
   - "전달:", "FW:", "Fwd:" 중 하나

2. **From (발신자)**
   - 전유진: 8921246@hanwha.com
   - 유재철: 8921242@hanwha.com

3. **To (수신자)**
   - youjin0404@hanwha.com 포함

---

## 📊 파싱 결과 비교

### 원본 메일 (EML 헤더)
```
From: 전유진 <8921246@hanwha.com>
To: 전유진 한화시스템/ICT <youjin0404@hanwha.com>
Subject: 전달: 원본 메일 제목
Date: 2026-04-30T12:39:32+0900
```

### HTML Body의 원본 정보
```
보낸 사람: Lee Hee Won <lhw@company.com>
보낸 날짜: 2026년 4월 30일 오전 12:39:32
받는 사람: user1@company.com; user2@company.com
참조: cc@company.com
제목: 원본 메일 제목
```

### JSON에 저장되는 정보
```json
{
  "subject": "원본 메일 제목",  // "전달:" 제거됨
  "sender": "Lee Hee Won",      // 원본 발신자로 대체
  "sender_email": "lhw@company.com",
  "recipients": ["user1@company.com", "user2@company.com"],  // 원본 수신자로 대체
  "date": "2026-04-30T12:39:32+0900",  // 원본 날짜
  "body_text": "원본 본문 내용",  // 원본 본문으로 대체
  "forwarded_from": {
    "original_sender": "전유진",  // 전달자 정보 저장 (역할 변경)
    "original_sender_email": "8921246@hanwha.com",
    "original_date": "2026-04-30 12:39:32 +0900",
    "original_to": ["user1@company.com", "user2@company.com"]
  }
}
```

---

## 💡 사용 예시

```python
from mail_crawler import parse_eml_file

# 조건 만족하는 전달 메일
email = parse_eml_file("mail_data/2026-04-30_전달_메일.eml")

# 결과
print(email.subject)              # "원본 메일 제목" (전달: 제거됨)
print(email.sender)               # "Lee Hee Won" (원본 발신자)
print(email.sender_email)         # "lhw@company.com"
print(email.recipients)           # 원본 수신자 목록
print(email.body_text)            # 원본 본문

# 전달자 정보는 forwarded_from에서 확인 가능
print(email.forwarded_from.original_sender)  # "전유진"
```

---

## 🔄 워크플로우

```
EML 파일 (전달 메일)
├─ From: 전유진 (8921246@hanwha.com)
├─ To: youjin0404@hanwha.com
├─ Subject: "전달: 원본 제목"
└─ HTML Body:
   ├─ 보낸 사람: Lee Hee Won <lhw@...>
   ├─ 보낸 날짜: 2026년 4월 30일...
   ├─ 받는 사람: user1@...; user2@...
   ├─ 참조: cc@...
   ├─ 제목: 원본 제목
   └─ 본문: 원본 본문...

       ↓ parse_eml_file() 함수

JSON (emails.json)
├─ subject: "원본 제목" ✓
├─ sender: "Lee Hee Won" ✓
├─ sender_email: "lhw@..." ✓
├─ recipients: ["user1@...", "user2@..."] ✓
├─ body_text: "원본 본문..." ✓
└─ forwarded_from:
   ├─ original_sender: "전유진" ✓
   ├─ original_sender_email: "8921246@..." ✓
   └─ ...
```

---

## ✨ 주요 변경점

| 항목 | 이전 | 현재 |
|------|------|------|
| **subject** | "전달: 원본 제목" | "원본 제목" |
| **sender** | "전유진" | "Lee Hee Won" |
| **recipients** | ["youjin0404@..."] | ["user1@...", "user2@..."] |
| **body_text** | 전달자의 메시지 | 원본 본문 |
| **forwarded_from** | 원본 정보 저장 | 전달자 정보 저장 |

---

## 🔧 구현 세부사항

### `parse_eml_file()` 함수의 변경 로직

1. **조건 확인**
   ```python
   subject_has_forward = "전달:" in subject or "FW:" in subject or "Fwd:" in subject
   sender_is_yujin_or_jaeseol = sender_email_addr in ["8921246@hanwha.com", "8921242@hanwha.com"]
   to_is_yujin = any("youjin0404@hanwha.com" in r for r in recipients)
   ```

2. **조건 만족 시 원본 정보 추출**
   ```python
   if body_html:
       forwarded_info = _extract_forwarded_email_from_html(body_html)
   if not forwarded_info.original_subject and body_text:
       forwarded_info = _extract_forwarded_email_from_text(body_text)
   ```

3. **원본 정보로 메일 정보 대체**
   ```python
   subject = forwarded_info.original_subject or subject
   sender_name = forwarded_info.original_sender
   sender_email_addr = forwarded_info.original_sender_email
   recipients = forwarded_info.original_to or recipients
   body_text = forwarded_info.original_body or body_text
   ```

4. **제목에서 "전달:" 제거**
   ```python
   subject = re.sub(r'^전달\s*[:：]\s*', '', subject).strip()
   subject = re.sub(r'^FW\s*[:：]\s*', '', subject, flags=re.IGNORECASE).strip()
   subject = re.sub(r'^Fwd\s*[:：]\s*', '', subject, flags=re.IGNORECASE).strip()
   ```

5. **전달자 정보를 forwarded_from에 저장**
   ```python
   forwarded_info.original_sender = forwarded_from_sender  # 전달자명
   forwarded_info.original_sender_email = forwarded_from_sender_email
   ```

---

## 📝 JSON 저장 형식

emails.json에 저장될 때:

```json
{
  "id": "eml_abc123...",
  "subject": "실시간 통합DB 시스템 구축안",
  "sender": "Lee Hee Won",
  "sender_email": "lhw@company.com",
  "recipients": [
    "user1@company.com",
    "user2@company.com"
  ],
  "date": "2026-04-30T12:39:32+09:00",
  "body_text": "원본 본문 내용...",
  "body_html": "...",
  "attachments": [],
  "category": "",
  "is_read": true,
  "forwarded_from": {
    "original_sender": "전유진",
    "original_sender_email": "8921246@hanwha.com",
    "original_date": "2026-04-30 18:39:32 +0900",
    "original_to": [
      "user1@company.com",
      "user2@company.com"
    ],
    "original_cc": [
      "cc@company.com"
    ],
    "original_subject": "실시간 통합DB 시스템 구축안",
    "original_body": "원본 본문 내용..."
  }
}
```

---

## ✅ 검증 방법

```bash
python test_forwarded_replacement.py
```

출력 예시:
```
📧 테스트 파일: 2026-04-30 1519_전유진_전달 테스트입니다.eml
════════════════════════════════════════════════════════════════════════════════

[파싱 결과]
  📌 Subject (제목에서 '전달:' 제거 여부):
     실시간 통합DB 시스템 구축안
     ✓ '전달:' 제거됨: True

  👤 Sender (원본 발신자로 대체 여부):
     Lee Hee Won <lhw@company.com>

  📧 Recipients (원본 수신자로 대체 여부):
     user1@company.com, user2@company.com

  [전달자 정보 (forwarded_from에 저장됨)]
     전달자: 전유진
     전달자 이메일: 8921246@hanwha.com
```

---

## 🎯 다음 단계

- 대시보드에서 원본 정보 기준으로 메일 분석
- 발신자별 통계 (원본 발신자 기준)
- 원본 메일 체인 추적
- forwarded_from 정보로 전달 경로 시각화

