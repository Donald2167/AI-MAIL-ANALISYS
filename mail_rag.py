"""
RAG (Retrieval-Augmented Generation) 기반 메일 질의 모듈
벡터 검색과 LLM을 결합하여 자연어 질의에 대한 응답 생성
"""
from typing import List, Dict, Optional, Tuple
import os
import json
import hashlib
from dataclasses import dataclass
from mail_crawler import Email
from summary_generator import LLMClient, OpenAIClient, MockLLMClient
from config import MAIL_CATEGORIES, load_llm_config


@dataclass
class SearchResult:
    """검색 결과"""
    email: Email
    score: float
    snippet: str


class SimpleVectorStore:
    """간단한 벡터 저장소 (테스트용)
    실제 프로덕션에서는 ChromaDB, Pinecone, FAISS 등 사용
    """
    
    def __init__(self, storage_path: str = "./data/vector_db"):
        self.storage_path = storage_path
        self.documents: Dict[str, dict] = {}  # id -> {text, embedding, metadata}
        os.makedirs(storage_path, exist_ok=True)
        self._load()
    
    def _load(self):
        """저장된 데이터 로드"""
        index_file = os.path.join(self.storage_path, "index.json")
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                self.documents = json.load(f)
    
    def _save(self):
        """데이터 저장"""
        index_file = os.path.join(self.storage_path, "index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, ensure_ascii=False)
    
    def _get_simple_embedding(self, text: str) -> List[float]:
        """간단한 TF 기반 임베딩 (테스트용)
        실제로는 OpenAI embeddings 또는 sentence-transformers 사용
        """
        # 단어 빈도 기반 간단한 벡터 생성
        words = text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # 해시 기반 고정 크기 벡터 생성 (간단한 시뮬레이션)
        vector = [0.0] * 100
        for word, freq in word_freq.items():
            idx = int(hashlib.md5(word.encode()).hexdigest()[:8], 16) % 100
            vector[idx] += freq
        
        # 정규화
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return vector
    
    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        """문서 추가"""
        embedding = self._get_simple_embedding(text)
        self.documents[doc_id] = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {}
        }
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """유사 문서 검색"""
        query_embedding = self._get_simple_embedding(query)
        
        results = []
        for doc_id, doc in self.documents.items():
            # 코사인 유사도 계산
            doc_embedding = doc["embedding"]
            dot_product = sum(a * b for a, b in zip(query_embedding, doc_embedding))
            results.append((doc_id, dot_product))
        
        # 점수 기준 정렬
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def save(self):
        """명시적 저장"""
        self._save()


class MailRAG:
    """메일 검색 및 질의응답 시스템"""
    
    def __init__(self, llm_client: LLMClient = None, vector_store: SimpleVectorStore = None):
        self.llm_client = llm_client or MockLLMClient()
        self.vector_store = vector_store or SimpleVectorStore()
        self.emails_cache: Dict[str, Email] = {}
    
    def index_emails(self, emails: List[Email]):
        """이메일 인덱싱"""
        for email in emails:
            # 검색용 텍스트 생성
            search_text = f"""
제목: {email.subject}
발신자: {email.sender} {email.sender_email}
카테고리: {MAIL_CATEGORIES.get(email.category, email.category)}
내용: {email.body_text}
"""
            self.vector_store.add_document(
                doc_id=email.id,
                text=search_text,
                metadata={
                    "subject": email.subject,
                    "sender": email.sender,
                    "sender_email": email.sender_email,
                    "category": email.category,
                    "date": email.date.isoformat() if email.date else None
                }
            )
            self.emails_cache[email.id] = email
        
        self.vector_store.save()
    
    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """메일 검색"""
        search_results = self.vector_store.search(query, top_k)
        
        results = []
        for doc_id, score in search_results:
            if doc_id in self.emails_cache:
                email = self.emails_cache[doc_id]
                # 스니펫 생성
                snippet = email.body_text[:150] + "..." if len(email.body_text) > 150 else email.body_text
                results.append(SearchResult(email=email, score=score, snippet=snippet))
        
        return results
    
    def answer_query(self, query: str) -> Dict:
        """자연어 질의에 대한 응답 생성"""
        # 1. 관련 메일 검색
        search_results = self.search(query, top_k=5)
        
        if not search_results:
            return {
                "answer": "관련된 메일을 찾지 못했습니다.",
                "emails": [],
                "query": query
            }
        
        # 2. 컨텍스트 구성
        context_parts = []
        for i, result in enumerate(search_results, 1):
            email = result.email
            context_parts.append(f"""
[메일 {i}]
제목: {email.subject}
발신자: {email.sender}
일시: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}
카테고리: {MAIL_CATEGORIES.get(email.category, email.category)}
내용: {email.body_text[:500]}
""")
        
        context = "\n---\n".join(context_parts)
        
        # 3. LLM으로 응답 생성
        prompt = f"""다음은 사용자의 메일함에서 검색된 이메일들입니다.
사용자의 질문에 이 메일들을 기반으로 답변하세요.

[검색된 메일들]
{context}

[사용자 질문]
{query}

위 메일들을 참고하여 사용자의 질문에 정확하고 간결하게 답변하세요.
관련 메일이 있다면 어떤 메일에서 정보를 찾았는지도 알려주세요.
"""
        
        try:
            answer = self.llm_client.generate(prompt, max_tokens=500)
        except Exception as e:
            answer = f"응답 생성 중 오류가 발생했습니다: {e}\n\n관련 메일 {len(search_results)}건이 검색되었습니다."
        
        return {
            "answer": answer,
            "emails": [r.email for r in search_results],
            "query": query,
            "search_scores": [(r.email.id, r.score) for r in search_results]
        }
    
    def get_summary_for_query(self, query: str) -> str:
        """질의에 대한 요약 응답"""
        result = self.answer_query(query)
        
        if not result["emails"]:
            return result["answer"]
        
        summary = f"""## 질의 응답

**질문**: {query}

**답변**: {result['answer']}

---

### 관련 메일 ({len(result['emails'])}건)

"""
        for email in result['emails']:
            summary += f"""- **{email.subject}** ({email.sender})
  - 일시: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}
  - 카테고리: {MAIL_CATEGORIES.get(email.category, email.category)}

"""
        
        return summary


class MailQueryEngine:
    """통합 메일 질의 엔진"""
    
    def __init__(self, emails: List[Email] = None, llm_client: LLMClient = None):
        self.rag = MailRAG(llm_client)
        if emails:
            self.index_emails(emails)
    
    def index_emails(self, emails: List[Email]):
        """이메일 인덱싱"""
        self.rag.index_emails(emails)
    
    def query(self, question: str) -> Dict:
        """질의 실행"""
        return self.rag.answer_query(question)
    
    def search(self, keywords: str, top_k: int = 10) -> List[Email]:
        """키워드 검색"""
        results = self.rag.search(keywords, top_k)
        return [r.email for r in results]
    
    def get_emails_by_sender(self, sender: str) -> List[Email]:
        """발신자별 메일 검색"""
        results = []
        for email in self.rag.emails_cache.values():
            if sender.lower() in email.sender.lower() or sender.lower() in email.sender_email.lower():
                results.append(email)
        return results
    
    def get_emails_by_category(self, category: str) -> List[Email]:
        """카테고리별 메일 검색"""
        results = []
        for email in self.rag.emails_cache.values():
            cat_label = MAIL_CATEGORIES.get(email.category, "")
            if category.lower() in email.category.lower() or category in cat_label:
                results.append(email)
        return results
    
    def get_action_items(self) -> List[Email]:
        """액션 필요 메일 목록"""
        action_categories = ['REPLY_REQUIRED', 'APPROVAL_REQUEST', 'TASK_REQUEST']
        results = []
        for email in self.rag.emails_cache.values():
            if email.category in action_categories:
                results.append(email)
        return results


# CLI 인터페이스
def interactive_query(emails: List[Email]):
    """대화형 질의 인터페이스"""
    # 저장된 LLM 설정 로드
    llm_config = load_llm_config()
    
    # LLM 클라이언트 초기화
    llm_client = None
    provider = llm_config.get("provider", "openai").lower()
    api_key = llm_config.get("api_key", "")
    model = llm_config.get("model", "gpt-4o-mini")
    
    if provider == "openai" and api_key:
        try:
            llm_client = OpenAIClient(api_key=api_key, model=model)
            print(f"✅ OpenAI LLM 사용: {model}")
        except Exception as e:
            print(f"⚠ OpenAI 초기화 실패: {e}. MockLLMClient 사용합니다.")
            llm_client = MockLLMClient()
    else:
        print("⚠ LLM 설정이 없습니다. Mock LLM을 사용합니다.")
        llm_client = MockLLMClient()
    
    engine = MailQueryEngine(emails, llm_client)
    
    print("\n📧 메일 질의 시스템")
    print("=" * 50)
    print("질문을 입력하세요. 종료하려면 'quit' 또는 'q'를 입력하세요.\n")
    
    while True:
        try:
            question = input("🔍 질문: ").strip()
            
            if question.lower() in ['quit', 'q', '종료']:
                print("프로그램을 종료합니다.")
                break
            
            if not question:
                continue
            
            result = engine.query(question)
            
            print("\n" + "=" * 50)
            print("📝 답변:")
            print(result['answer'])
            
            if result['emails']:
                print(f"\n📬 관련 메일 {len(result['emails'])}건:")
                for email in result['emails'][:3]:
                    print(f"  • {email.subject} ({email.sender})")
            
            print("=" * 50 + "\n")
            
        except KeyboardInterrupt:
            print("\n프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"오류 발생: {e}")


if __name__ == "__main__":
    from mail_crawler import create_sample_emails
    from mail_classifier import MailClassifier
    
    # 샘플 데이터 생성
    emails = create_sample_emails()
    
    # 분류
    classifier = MailClassifier()
    emails = classifier.classify_batch(emails)
    
    # 대화형 질의 시작
    interactive_query(emails)
