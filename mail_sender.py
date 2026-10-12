"""
메일 발송 모듈
SMTP를 통한 주간 보고서 이메일 발송
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from datetime import datetime
import os

from config import SMTPConfig

logger = logging.getLogger(__name__)


class MailSender:
    """SMTP 이메일 발송 클래스"""

    def __init__(self, config: SMTPConfig):
        self.config = config

    def _build_message(
        self,
        subject: str,
        body_html: str,
        body_text: str,
        recipients: List[str],
        attachment_paths: Optional[List[str]] = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # 첨부파일
        if attachment_paths:
            outer = MIMEMultipart("mixed")
            outer["Subject"] = msg["Subject"]
            outer["From"] = msg["From"]
            outer["To"] = msg["To"]
            outer.attach(msg)
            for path in attachment_paths:
                if not os.path.exists(path):
                    logger.warning(f"첨부파일 없음: {path}")
                    continue
                with open(path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(path)
                part.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                outer.attach(part)
            return outer

        return msg

    def send(
        self,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        recipients: Optional[List[str]] = None,
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        """이메일 발송. 성공 시 True 반환."""
        if not self.config.email or not self.config.password:
            logger.error("SMTP 이메일/비밀번호가 설정되지 않았습니다.")
            return False

        to_list = recipients or self.config.recipients
        if not to_list:
            logger.error("수신자가 없습니다.")
            return False

        if body_html is None:
            body_html = f"<pre style='font-family:sans-serif'>{body_text}</pre>"

        msg = self._build_message(subject, body_html, body_text, to_list, attachment_paths)

        try:
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.login(self.config.email, self.config.password)
                server.sendmail(self.config.email, to_list, msg.as_string())
            logger.info(f"메일 발송 완료 → {to_list} | 제목: {subject}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP 인증 실패 — 앱 비밀번호를 확인하세요.")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP 오류: {e}")
        except Exception as e:
            logger.error(f"메일 발송 중 예외 발생: {e}")
        return False


def markdown_to_html(markdown_text: str) -> str:
    """마크다운을 간단한 HTML로 변환 (외부 라이브러리 없이)"""
    import re

    lines = markdown_text.split("\n")
    html_lines = []
    in_table = False
    in_list = False

    for line in lines:
        # 테이블
        if line.strip().startswith("|"):
            if not in_table:
                html_lines.append("<table border='1' cellpadding='6' style='border-collapse:collapse'>")
                in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # 구분선 행 무시
            row_html = "".join(f"<td>{c}</td>" for c in cells)
            html_lines.append(f"<tr>{row_html}</tr>")
            continue
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False

        # 리스트
        if line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:].strip()}</li>")
            continue
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False

        # 헤딩
        heading_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # 수평선
        if line.strip() in ("---", "***", "___"):
            html_lines.append("<hr>")
            continue

        # 굵게 (**text**)
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)

        # 빈 줄
        if line.strip() == "":
            html_lines.append("<br>")
            continue

        html_lines.append(f"<p style='margin:4px 0'>{line}</p>")

    if in_table:
        html_lines.append("</table>")
    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def build_weekly_email_html(report_markdown: str, week_label: str) -> str:
    """주간 보고서 이메일 HTML 본문 생성"""
    body_html = markdown_to_html(report_markdown)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
         font-size: 14px; color: #222; max-width: 800px; margin: auto; padding: 20px; }}
  h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
  h2 {{ color: #34495e; margin-top: 24px; }}
  h3 {{ color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  td, th {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  strong {{ color: #c0392b; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 16px 0; }}
  .footer {{ margin-top: 40px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 12px; }}
</style>
</head>
<body>
{body_html}
<div class="footer">
  📧 메일 리포터 자동 발송 | {week_label} | {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</body>
</html>"""
