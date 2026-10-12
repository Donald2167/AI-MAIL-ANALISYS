"""
메일 리포터 패키지
"""
from .config import LLMConfig, AppConfig, MAIL_CATEGORIES
from .mail_crawler import Email
from .mail_classifier import MailClassifier, group_emails_by_category, group_emails_by_sender
from .summary_generator import SummaryGenerator, LLMClient, OpenAIClient, MockLLMClient
from .mail_rag import MailRAG, MailQueryEngine

__version__ = "1.0.0"
__all__ = [
    "LLMConfig",
    "AppConfig",
    "MAIL_CATEGORIES",
    "Email",
    "MailClassifier",
    "group_emails_by_category",
    "group_emails_by_sender",
    "SummaryGenerator",
    "LLMClient",
    "OpenAIClient",
    "MockLLMClient",
    "MailRAG",
    "MailQueryEngine"
]
