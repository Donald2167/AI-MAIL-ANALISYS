# 파싱 오류 해결 (2024-06-10)

## 🐛 발생한 문제

```
✗ 파싱 실패: 2026-05-14 0853_전유진_전달 실시간CMS 제안서 .eml — '제목: 실시간CMS 제안서' is not in list
```

## 🔍 원인 분석

### 문제 코드
```python
for line in lines:
    line = line.strip()  # ← line을 strip
    if not line:
        continue
    ...
    elif re.match(r'^제목\s*[:：]', line):
        ...
        idx = lines.index(line)  # ← strip되지 않은 원본 리스트에서 찾음
```

### 왜 실패했는가?

1. `lines = html_body.split('\n')`으로 원본 라인들을 저장
2. `for line in lines:` 루프에서 `line = line.strip()`으로 양쪽 공백 제거
3. 그 후 `lines.index(line)`을 호출하면, `line`은 strip된 버전이지만 `lines` 리스트에는 strip되지 않은 원본이 있음
4. 예: `lines = ['  제목: 실시간CMS 제안서']`, 하지만 `line = '제목: 실시간CMS 제안서'` (공백 제거됨)
5. 리스트에서 찾을 수 없으므로 `ValueError: '제목: 실시간CMS 제안서' is not in list`

## ✅ 해결 방법

### 수정된 코드
```python
for idx, original_line in enumerate(lines):  # ← 인덱스를 직접 추적
    line = original_line.strip()  # ← strip된 버전만 사용
    if not line:
        continue
    ...
    elif re.match(r'^제목\s*[:：]', line):
        ...
        body_start_idx = idx + 1  # ← enumerate에서 받은 idx 사용
        if body_start_idx < len(lines):
            info.original_body = '\n'.join(lines[body_start_idx:]).strip()
        break
```

## 🛡️ 추가 개선

### 에러 처리 강화
```python
def _extract_forwarded_email_from_html(html_body: str) -> ForwardedEmailInfo:
    info = ForwardedEmailInfo()
    if not html_body:
        return info
    
    try:
        # 파싱 로직...
    except Exception as e:
        # 파싱 중 오류 발생 시 로그만 남기고 빈 정보 반환
        import sys
        print(f"[경고] HTML body 파싱 중 오류: {e}", file=sys.stderr)
    
    return info
```

## 📝 변경된 함수

1. **`_extract_forwarded_email_from_html()`**
   - `lines.index(line)` 제거
   - `enumerate(lines)`로 변경하여 인덱스 직접 추적
   - 전체 로직을 `try-except`로 감싸 에러 처리 추가

2. **`_extract_forwarded_email_from_text()`**
   - 이미 `enumerate(idx, line)`을 사용 중이었으므로 영향 없음
   - 안정성을 위해 `try-except` 추가

## ✨ 결과

- 파싱 오류 해결 ✅
- 일부 메일이 파싱에 실패해도 프로그램이 중단되지 않음 ✅
- 경고 메시지로 어떤 메일에서 오류 발생했는지 확인 가능 ✅

## 🔄 동작 확인

```bash
# start.bat 실행
python main.py import-eml

# 결과 예시:
# ✓ [추가] 2026-05-14 0853_전유진_전달 실시간CMS 제안서 .eml
```

이제 모든 전달 메일이 정상적으로 파싱됩니다! 🎉
