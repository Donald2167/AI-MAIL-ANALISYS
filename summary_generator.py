"""
요약 생성 모듈
LLM을 활용한 메일 요약 및 보고서 생성
"""
from typing import List, Dict, Optional
from datetime import datetime
import json
import os
from mail_crawler import Email
from mail_classifier import group_emails_by_category, get_email_statistics
from config import MAIL_CATEGORIES, load_llm_config


class LLMClient:
    """LLM API 클라이언트 (추상 클래스)"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """텍스트 생성"""
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """OpenAI API 클라이언트"""
    
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3
            )
            return response.choices[0].message.content
        except ImportError:
            raise ImportError("openai 패키지를 설치하세요: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI API 오류: {e}")


class OllamaClient(LLMClient):
    """Ollama 로컬 LLM 클라이언트"""
    
    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434"):
        super().__init__(api_key="", model=model, base_url=base_url)
    
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        try:
            import requests
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens}
                }
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except ImportError:
            raise ImportError("requests 패키지를 설치하세요: pip install requests")
        except Exception as e:
            raise Exception(f"Ollama API 오류: {e}")


class GeminiClient(LLMClient):
    """Google Gemini API 클라이언트"""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        super().__init__(api_key=api_key, model=model)

    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.3,
                ),
            )
            return response.text
        except ImportError:
            raise ImportError("google-generativeai 패키지를 설치하세요: pip install google-generativeai")
        except Exception as e:
            raise Exception(f"Gemini API 오류: {e}")


class MockLLMClient(LLMClient):
    """테스트용 Mock LLM 클라이언트"""
    
    def __init__(self):
        super().__init__(api_key="mock")
    
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        # 간단한 규칙 기반 요약 생성
        if "요약" in prompt or "summary" in prompt.lower():
            return """## 메일 요약

**핵심 내용**: 이 메일은 업무 관련 요청 또는 안내 사항을 담고 있습니다.

**주요 포인트**:
- 주요 안건 확인 필요
- 일정 또는 마감일 확인 권장
- 필요시 회신 또는 후속 조치 필요

**권장 액션**: 내용 검토 후 필요한 조치를 취하세요."""
        
        if "분류" in prompt or "category" in prompt.lower():
            return "CATEGORY: OTHER"
        
        return "처리 완료"


class SummaryGenerator:
    """메일 요약 생성기"""
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or MockLLMClient()
    
    def summarize_email_simple(self, email: Email) -> str:
        """LLM 없이 간단한 요약 생성"""
        lines = email.body_text.split('\n')
        # 빈 줄과 인사말 제외하고 첫 3줄 추출
        content_lines = [
            line.strip() for line in lines 
            if line.strip() and not any(
                greeting in line for greeting in ['안녕하세요', '감사합니다', '드림', '올림']
            )
        ]
        summary = ' '.join(content_lines[:3])
        return summary[:200] + '...' if len(summary) > 200 else summary
    
    def generate_category_report(self, category: str, emails: List[Email]) -> str:
        """카테고리별 요약 보고서 생성"""
        if not emails:
            return f"## {MAIL_CATEGORIES.get(category, category)}\n\n해당 카테고리의 메일이 없습니다."
        
        email_summaries = []
        for email in emails[:10]:  # 최대 10개
            summary = self.summarize_email_simple(email)
            email_summaries.append(f"- **{email.subject}** ({email.sender})\n  {summary}")
        
        report = f"""## {MAIL_CATEGORIES.get(category, category)}

**총 {len(emails)}건** | 미확인: {len([e for e in emails if not e.is_read])}건

### 메일 목록
{chr(10).join(email_summaries)}
"""
        return report
    
    def generate_daily_report(self, emails: List[Email], date: datetime = None) -> str:
        """일일 메일 요약 보고서 생성"""
        date = date or datetime.now()
        date_str = date.strftime('%Y년 %m월 %d일')
        
        stats = get_email_statistics(emails)
        category_groups = group_emails_by_category(emails)
        
        # 우선순위 높은 메일 (회신필요, 결재요청)
        priority_emails = []
        for cat in ['REPLY_REQUIRED', 'APPROVAL_REQUEST', 'TASK_REQUEST']:
            priority_emails.extend(category_groups.get(cat, []))
        
        report = f"""# 📧 일일 메일 요약 보고서

**일자**: {date_str}
**생성 시간**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 📊 통계 요약

| 항목 | 수량 |
|------|------|
| 총 메일 | {stats['total_count']}건 |
| 미확인 | {stats['unread_count']}건 |
| 첨부파일 포함 | {stats['has_attachments']}건 |

### 카테고리별 현황
"""
        
        for cat, info in stats['by_category'].items():
            if info['count'] > 0:
                report += f"- **{info['label']}**: {info['count']}건\n"
        
        report += "\n---\n\n## 🔴 우선 처리 필요\n\n"
        
        if priority_emails:
            for email in priority_emails[:5]:
                report += f"""### {email.subject}
- **발신자**: {email.sender}
- **일시**: {email.date.strftime('%m/%d %H:%M') if email.date else 'N/A'}
- **카테고리**: {MAIL_CATEGORIES.get(email.category, email.category)}
- **요약**: {self.summarize_email_simple(email)}

"""
        else:
            report += "긴급 처리가 필요한 메일이 없습니다.\n\n"
        
        report += "---\n\n## 📋 카테고리별 상세\n\n"
        
        for category, emails_list in category_groups.items():
            if emails_list:
                report += self.generate_category_report(category, emails_list)
                report += "\n---\n\n"
        
        return report
    
    def generate_sender_report(self, sender_email: str, emails: List[Email]) -> str:
        """발신자별 메일 요약 보고서"""
        if not emails:
            return f"# {sender_email}\n\n메일 없음"
        
        sender_name = emails[0].sender
        
        report = f"""# 📬 발신자별 메일 요약

**발신자**: {sender_name} <{sender_email}>
**총 메일**: {len(emails)}건
**기간**: {min(e.date for e in emails if e.date).strftime('%Y-%m-%d')} ~ {max(e.date for e in emails if e.date).strftime('%Y-%m-%d')}

---

## 메일 목록

"""
        for email in sorted(emails, key=lambda x: x.date if x.date else datetime.min, reverse=True):
            report += f"""### {email.subject}
- **일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}
- **카테고리**: {MAIL_CATEGORIES.get(email.category, email.category)}
- **요약**: {self.summarize_email_simple(email)}

"""
        return report


def save_report(report: str, filepath: str):
    """보고서를 파일로 저장"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)


class WeeklySummaryGenerator:
    """주간 요약 보고서 생성기 — 이번 주 메일을 바탕으로 차주 액션 아이템 정리"""

    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or MockLLMClient()
        self.base_generator = SummaryGenerator(llm_client)

    def generate_weekly_report(self, emails: List[Email], week_label: str = "") -> str:
        """주간 요약 보고서 생성.

        Args:
            emails: 이번 주 수집된 전체 메일 목록
            week_label: 보고서 표지에 표시할 주차 문자열 (예: "2026년 20주차")

        Returns:
            마크다운 형식 주간 보고서 문자열
        """
        if not week_label:
            week_label = datetime.now().strftime("%Y년 %W주차")

        stats = get_email_statistics(emails)
        category_groups = group_emails_by_category(emails)

        # 우선순위 메일 (회신·결재·업무요청)
        priority_cats = ["REPLY_REQUIRED", "APPROVAL_REQUEST", "TASK_REQUEST"]
        priority_emails = []
        for cat in priority_cats:
            priority_emails.extend(category_groups.get(cat, []))

        # 미처리(미읽음 포함) 우선순위 메일
        pending = [e for e in priority_emails if not e.is_read]

        # LLM 프롬프트 — 차주 액션/알아야 할 정보 추출
        context_lines = []
        for e in emails[:30]:  # 최대 30건으로 컨텍스트 구성
            context_lines.append(
                f"[{MAIL_CATEGORIES.get(e.category, e.category)}] {e.subject} "
                f"(발신: {e.sender}, 일시: {e.date.strftime('%m/%d') if e.date else '-'})\n"
                f"{self.base_generator.summarize_email_simple(e)}"
            )
        context_text = "\n\n".join(context_lines)

        llm_prompt = f"""다음은 이번 주({week_label}) 수신된 업무 이메일 목록과 각 요약입니다.

{context_text}

위 내용을 바탕으로 아래 두 섹션을 한국어로 작성하세요.

## 차주 필수 액션
- 답변·결재·처리가 필요한 항목을 우선순위 순으로 정리
- 각 항목에 담당자/마감일이 있으면 표기

## 이번 주 핵심 정보 요약
- 팀이 알아야 할 주요 공지, 결정 사항, 변경 사항 요약
- 불필요한 내용은 제외하고 핵심만 3~7줄로 정리"""

        llm_output = self.llm_client.generate(llm_prompt, max_tokens=1500)

        # 보고서 조립
        report = f"""# 📅 주간 메일 요약 보고서

**기간**: {week_label}
**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 📊 이번 주 통계

| 항목 | 수량 |
|------|------|
| 총 수신 메일 | {stats['total_count']}건 |
| 미확인 | {stats['unread_count']}건 |
| 첨부파일 포함 | {stats['has_attachments']}건 |
| 처리 필요 (미읽음) | {len(pending)}건 |

### 카테고리별 현황
"""
        for cat, info in stats["by_category"].items():
            if info["count"] > 0:
                report += f"- **{info['label']}**: {info['count']}건\n"

        report += f"\n---\n\n{llm_output}\n\n---\n\n"

        # 미처리 항목 상세
        if pending:
            report += "## 🔴 미처리 항목 상세\n\n"
            for e in pending[:10]:
                report += (
                    f"### {e.subject}\n"
                    f"- **발신자**: {e.sender} ({e.sender_email})\n"
                    f"- **카테고리**: {MAIL_CATEGORIES.get(e.category, e.category)}\n"
                    f"- **수신 일시**: {e.date.strftime('%Y-%m-%d %H:%M') if e.date else 'N/A'}\n"
                    f"- **요약**: {self.base_generator.summarize_email_simple(e)}\n\n"
                )

        return report


def generate_weekly_report_file(
    emails: List[Email],
    weekly_dir: str,
    llm_client: LLMClient = None,
) -> tuple[str, str]:
    """주간 보고서를 파일로 저장하고 (보고서 텍스트, 파일 경로)를 반환."""
    from datetime import date
    today = date.today()
    week_label = f"{today.year}년 {today.strftime('%W')}주차"
    filename = f"weekly_{today.strftime('%Y_W%W')}.md"
    filepath = os.path.join(weekly_dir, filename)

    generator = WeeklySummaryGenerator(llm_client)
    report = generator.generate_weekly_report(emails, week_label)
    save_report(report, filepath)
    print(f"주간 보고서 저장: {filepath}")
    return report, filepath
