"""
Streamlit 기반 메일 대시보드 UI
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mail_crawler import Email, save_emails_to_json, load_emails_from_json, import_eml_directory
from mail_classifier import (MailClassifier, group_emails_by_category, group_emails_by_sender,
                             get_email_statistics, EmailAnalyzer, get_deadline_status_text)
from summary_generator import GeminiClient, OpenAIClient, OllamaClient, MockLLMClient
from config import MAIL_CATEGORIES, AppConfig, LLMConfig, save_llm_config, load_llm_config

# 페이지 설정
st.set_page_config(
    page_title="📧 메일 리포터",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 앱 설정
config = AppConfig()

# 세션 상태 초기화
if 'emails' not in st.session_state:
    st.session_state.emails = []
if 'selected_email' not in st.session_state:
    st.session_state.selected_email = None


def load_email_data() -> list:
    """emails.json 로드 (없으면 빈 리스트 반환)"""
    data_file = os.path.join(config.data_dir, "emails.json")
    if os.path.exists(data_file):
        return load_emails_from_json(data_file)
    return []


def run_eml_import(eml_dir: str, force: bool = False) -> tuple:
    """mail_data/ 폴더의 .eml 파일을 가져와 emails.json에 병합"""
    json_path = os.path.join(config.data_dir, "emails.json")
    added, skipped = import_eml_directory(
        eml_dir, json_path,
        classify=True, force=force, filename_filter=None
    )
    return added, skipped


def init_llm_client(use_llm: bool = False) -> object:
    """LLM 클라이언트 초기화 - 저장된 설정 또는 환경 변수 사용"""
    if not use_llm:
        return None
    
    # 저장된 설정 또는 환경 변수에서 로드
    llm_config = load_llm_config()
    provider = llm_config.get("provider", "openai").lower()
    api_key = llm_config.get("api_key", "")
    model = llm_config.get("model", "gpt-4o-mini")
    
    try:
        if provider == "openai":
            if not api_key:
                st.error("OpenAI API 키가 없습니다. 설정에서 API 키를 입력하세요.")
                return None
            return OpenAIClient(api_key=api_key, model=model or "gpt-4o-mini")
        elif provider == "gemini":
            if not api_key:
                st.error("Gemini API 키가 없습니다. 설정에서 API 키를 입력하세요.")
                return None
            return GeminiClient(api_key=api_key, model=model or "gemini-2.5-flash")
        elif provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return OllamaClient(base_url=base_url, model=model or "llama3")
        else:
            st.warning(f"알 수 없는 LLM 제공자: {provider}. MockLLMClient를 사용합니다.")
            return MockLLMClient()
    except Exception as e:
        st.error(f"LLM 클라이언트 초기화 실패: {e}")
        return None



def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("📧 메일 리포터")
        st.divider()
        
        # 메뉴
        menu = st.radio(
            "메뉴",
            ["📊 대시보드", "📬 메일 목록", "📁 발신자별", "🔍 검색/질의", "⚙️ 설정"],
            label_visibility="collapsed"
        )
        
        st.divider()

        # EML 가져오기
        eml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_data")
        eml_exists = os.path.isdir(eml_dir) and any(
            f.lower().endswith(".eml") for f in os.listdir(eml_dir)
        ) if os.path.isdir(eml_dir) else False

        if eml_exists:
            if st.button("📂 EML 가져오기 (전체)", use_container_width=True,
                         help="모든 .eml 파일을 파싱합니다"):
                with st.spinner("EML 파일 파싱 중..."):
                    added, skipped = run_eml_import(eml_dir, force=True)
                st.session_state.emails = load_email_data()
                st.success(f"✅ 완료 — 추가/갱신 {added}건 | 중복 건너뜀 {skipped}건")
                st.rerun()
        else:
            st.caption("📁 mail_data/ 폴더에 .eml 파일을 넣어주세요")

        st.divider()

        # 보고서 생성
        if st.button("📝 HTML 보고서 생성", use_container_width=True):
            if st.session_state.emails:
                with st.spinner("보고서 생성 중..."):
                    html_path = generate_html_report(st.session_state.emails, config.summary_dir)
                st.success(f"HTML 보고서 생성 완료!")
                st.code(html_path, language=None)
            else:
                st.warning("메일 데이터가 없습니다.")
        
        return menu


def render_reply_required_section(emails):
    """회신필요 메일 처리 섹션"""
    st.subheader("💬 회신 필요 메일")
    
    # 회신필요 메일 필터링
    reply_required_emails = [e for e in emails if e.category == "REPLY_REQUIRED"]
    
    if not reply_required_emails:
        st.success("회신이 필요한 메일이 없습니다! 🎉")
        return
    
    st.write(f"**{len(reply_required_emails)}건**의 회신이 필요한 메일이 있습니다.")
    
    # 메일 리스트
    col_list, col_detail = st.columns([1, 2])
    
    with col_list:
        st.write("**메일 목록:**")
        
        # 스크롤 가능한 컨테이너 (높이 제한: 400px)
        with st.container(border=True, height=400):
            selected_email = None
            for idx, email in enumerate(reply_required_emails):
                # 버튼으로 메일 선택 (현재 선택된 메일은 강조)
                button_label = f"📧 [{email.sender[:12]}] {email.subject[:30]}"
                if st.button(button_label, use_container_width=True, key=f"reply_mail_{idx}"):
                    st.session_state.selected_reply_email_idx = idx
        
        # 선택된 메일 인덱스 가져오기
        if 'selected_reply_email_idx' not in st.session_state:
            st.session_state.selected_reply_email_idx = 0
        
        selected_email = reply_required_emails[st.session_state.selected_reply_email_idx]
    
    with col_detail:
        st.write("**메일 상세:**")
        
        # 선택된 메일 정보 표시
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**발신자**: {selected_email.sender}")
            st.write(f"**이메일**: {selected_email.sender_email}")
            st.write(f"**일시**: {selected_email.date.strftime('%Y-%m-%d %H:%M') if selected_email.date else 'N/A'}")
            if selected_email.attachments:
                st.write(f"**첨부파일**: {', '.join(selected_email.attachments)}")
        
        with col2:
            st.write(f"**상태**: {'읽음' if selected_email.is_read else '안읽음'}")
        
        st.divider()
        
        # 메일 본문
        st.write("**메일 내용:**")
        st.text_area("", value=selected_email.body_text, disabled=True, height=150, label_visibility="collapsed")
    
    st.divider()
    
    # LLM 요약 기능
    if st.button("📝 LLM 메일 요약", use_container_width=True, key="llm_summary_btn"):
        llm_client = init_llm_client(use_llm=True)
        if llm_client is None:
            st.error("LLM 설정이 필요합니다. 설정 탭에서 LLM을 설정하세요.")
        else:
            with st.spinner("메일 요약 중..."):
                _max_tokens = load_llm_config().get("max_tokens", 1000)
                prompt = f"""다음 이메일을 간결하게 요약하세요. 핵심 내용만 3-5줄로:

제목: {selected_email.subject}
발신자: {selected_email.sender}

내용:
{selected_email.body_text}

요약:"""
                try:
                    summary = llm_client.generate(prompt, max_tokens=_max_tokens)
                    st.success("**메일 요약:**")
                    st.write(summary)
                except Exception as e:
                    st.error(f"요약 생성 실패: {e}")
    
    # LLM 회신 작성 기능
    st.write("**회신 내용 작성**")
    user_input = st.text_area(
        "회신할 내용 (대략적인 내용을 입력하면 LLM이 완성된 메일을 작성해줍니다)",
        placeholder="예: 프로젝트 진행 예정, 검토 완료, 일정 확인 등",
        height=100,
        key="reply_input"
    )
    
    if st.button("✍️ LLM 회신 작성", use_container_width=True, key="llm_reply_btn"):
        if not user_input.strip():
            st.warning("회신 내용을 입력하세요.")
        else:
            llm_client = init_llm_client(use_llm=True)
            if llm_client is None:
                st.error("LLM 설정이 필요합니다. 설정 탭에서 LLM을 설정하세요.")
            else:
                with st.spinner("회신 메일 작성 중..."):
                    _max_tokens = load_llm_config().get("max_tokens", 1000)
                    # 원본 메일 컨텍스트 구성
                    original_context = f"발신자: {selected_email.sender}\n제목: {selected_email.subject}\n\n본문:\n{selected_email.body_text}"
                    
                    # forwarded_from 정보가 있으면 추가
                    if selected_email.forwarded_from and selected_email.forwarded_from.original_subject:
                        original_context += f"\n\n[원본 메일 정보]\n제목: {selected_email.forwarded_from.original_subject}\n발신자: {selected_email.forwarded_from.original_sender}"
                        if selected_email.forwarded_from.original_body:
                            original_context += f"\n본문 요약: {selected_email.forwarded_from.original_body[:300]}"
                    
                    prompt = f"""당신은 전문적인 업무 메일 작성 어시스턴트입니다. 아래 메일에 대한 자연스럽고 상세한 한국어 회신을 작성하세요.

【원본 메일】
{original_context}

【회신 의도】
{user_input}

【요청사항】
- 간결하면서도 정중한 톤으로 작성 (불필요한 수식어 피하고 핵심만 전달)
- 수신자를 존중하는 전문적인 태도 유지
- 원본 메일의 핵심 내용에 대해 구체적으로 응답
- 회신 의도를 충분히 반영하되, 명확하고 읽기 쉽게 작성 (2-4문단)
- 인사말로 시작하고 친절한 맺음말로 마무리
- 한국어 존댓말 사용
- 구체적인 정보나 액션 포인트가 있으면 포함
- 과도하게 길지 않도록 주의 (비즈니스 메일 기준)

【회신 메일 본문】
"""
                    try:
                        reply_content = llm_client.generate(prompt, max_tokens=_max_tokens)
                        st.success("**작성된 회신 메일:**")
                        st.text_area(
                            "회신 내용 (복사해서 사용하세요)",
                            value=reply_content,
                            height=200,
                            disabled=True
                        )
                    except Exception as e:
                        st.error(f"회신 작성 실패: {e}")


def render_priority_section(emails):
    """우선 처리 필요 섹션 렌더링"""
    st.subheader("🔴 우선 처리 필요")
    
    # 메일 분석
    analyzer = EmailAnalyzer()
    priority_analyses = analyzer.get_priority_emails(emails, top_n=10)
    
    if not priority_analyses:
        st.success("긴급 처리가 필요한 메일이 없습니다! 🎉")
        return
    
    # 긴급/중요 메일 분리
    urgent_emails = [a for a in priority_analyses if a.is_urgent]
    deadline_emails = [a for a in priority_analyses if a.days_until_deadline is not None and a.days_until_deadline <= 3]
    action_required = [a for a in priority_analyses if a.action_items]
    
    # 탭으로 구분
    tab1, tab2, tab3, tab4 = st.tabs(["🚨 전체 우선순위", "⚡ 긴급/중요", "⏰ 기한 임박", "📋 액션 필요"])
    
    with tab1:
        render_priority_list(priority_analyses[:7])
    
    with tab2:
        if urgent_emails:
            st.warning(f"**{len(urgent_emails)}건**의 긴급/중요 메일이 있습니다!")
            render_priority_list(urgent_emails)
        else:
            st.success("긴급/중요 메일이 없습니다.")
    
    with tab3:
        if deadline_emails:
            st.warning(f"**{len(deadline_emails)}건**의 기한 임박 메일이 있습니다!")
            for analysis in sorted(deadline_emails, key=lambda x: x.days_until_deadline if x.days_until_deadline is not None else 999):
                render_deadline_email(analysis)
        else:
            st.success("기한이 임박한 메일이 없습니다.")
    
    with tab4:
        if action_required:
            st.info(f"**{len(action_required)}건**의 액션이 필요한 메일이 있습니다.")
            for analysis in action_required[:5]:
                render_action_email(analysis)
        else:
            st.success("당장 처리해야 할 액션이 없습니다.")


def render_priority_list(analyses):
    """우선순위 메일 목록 렌더링"""
    for analysis in analyses:
        email = analysis.email
        
        # 아이콘 결정
        if analysis.is_urgent:
            icon = "🚨"
        elif analysis.is_important:
            icon = "⭐"
        elif analysis.days_until_deadline is not None and analysis.days_until_deadline <= 1:
            icon = "⏰"
        else:
            icon = "📌"
        
        # 상태 배지
        badges = []
        if analysis.is_urgent:
            badges.append("🔴 긴급")
        if analysis.is_important:
            badges.append("⭐ 중요")
        if analysis.days_until_deadline is not None:
            status_text, color = get_deadline_status_text(analysis.days_until_deadline)
            if status_text:
                badges.append(status_text)
        
        badge_text = " | ".join(badges) if badges else ""
        
        with st.expander(f"{icon} {email.subject} - {email.sender}"):
            # 상단 정보 영역
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.write(f"**발신자**: {email.sender} <{email.sender_email}>")
                st.write(f"**일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}")
                st.write(f"**카테고리**: {MAIL_CATEGORIES.get(email.category, email.category)}")
            
            with col2:
                st.write(f"**우선순위 점수**: {analysis.priority_score}")
                if badge_text:
                    st.write(f"**상태**: {badge_text}")
                if analysis.urgency_reason:
                    st.write(f"**긴급 사유**: {analysis.urgency_reason}")
            
            # 기한 정보
            if analysis.deadline_text:
                deadline_status, _ = get_deadline_status_text(analysis.days_until_deadline)
                st.info(f"📅 **기한**: {analysis.deadline_text} ({deadline_status})")
            
            # 액션 아이템
            if analysis.action_items:
                st.warning("**📋 필요한 액션:**")
                for action in analysis.action_items:
                    st.write(f"  • {action}")
            
            st.divider()
            
            # 메일 본문 요약
            st.write("**📝 내용:**")
            st.write(email.body_text[:500] + ("..." if len(email.body_text) > 500 else ""))


def render_deadline_email(analysis):
    """기한 임박 메일 카드 렌더링"""
    email = analysis.email
    status_text, color = get_deadline_status_text(analysis.days_until_deadline)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 4, 2])
        
        with col1:
            if analysis.days_until_deadline is not None and analysis.days_until_deadline <= 0:
                st.markdown("### 🔴")
            elif analysis.days_until_deadline == 1:
                st.markdown("### 🟠")
            else:
                st.markdown("### 🟡")
        
        with col2:
            st.write(f"**{email.subject}**")
            st.write(f"발신자: {email.sender}")
            if analysis.action_items:
                st.write(f"액션: {', '.join(analysis.action_items[:2])}")
        
        with col3:
            st.write(f"**{status_text}**")
            st.write(f"기한: {analysis.deadline_text}")
        
        st.divider()


def render_action_email(analysis):
    """액션 필요 메일 카드 렌더링"""
    email = analysis.email
    
    with st.expander(f"📋 {email.subject} - {email.sender}"):
        st.write(f"**발신자**: {email.sender}")
        st.write(f"**일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}")
        
        st.warning("**🎯 필요한 액션:**")
        for action in analysis.action_items:
            st.write(f"  ✓ {action}")
        
        if analysis.deadline_text:
            status_text, _ = get_deadline_status_text(analysis.days_until_deadline)
            st.info(f"⏰ 기한: {analysis.deadline_text} ({status_text})")
        
        st.divider()
        st.write("**메일 요약:**")
        # 핵심 문장 추출 (간단한 버전)
        lines = [l.strip() for l in email.body_text.split('\n') if l.strip()]
        summary_lines = [l for l in lines if not any(x in l for x in ['안녕하세요', '감사합니다', '드림', '올림'])][:3]
        for line in summary_lines:
            st.write(f"• {line[:100]}")


def render_dashboard():
    """대시보드 페이지"""
    st.title("📊 메일 대시보드")
    
    emails = st.session_state.emails
    
    # ★ 데이터가 없으면 재로드 시도
    if not emails:
        emails = load_email_data()
        st.session_state.emails = emails
    
    if not emails:
        st.info("메일 데이터가 없습니다. 사이드바의 **📂 EML 가져오기** 버튼을 클릭하세요.\n\n`mail_data/` 폴더에 .eml 파일을 넣은 뒤 가져오기를 실행하세요.")
        return
    
    stats = get_email_statistics(emails)
    
    # 상단 통계 카드
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📧 총 메일", f"{stats['total_count']}건")
    with col2:
        st.metric("🔴 미확인", f"{stats['unread_count']}건")
    with col3:
        reply_count = stats['by_category'].get('REPLY_REQUIRED', {}).get('count', 0)
        st.metric("💬 회신필요", f"{reply_count}건")
    with col4:
        st.metric("📎 첨부파일", f"{stats['has_attachments']}건")
    
    st.divider()
    
    # 카테고리별 현황
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📁 카테고리별 현황")
        
        category_data = []
        for cat, info in stats['by_category'].items():
            if info['count'] > 0:
                category_data.append({
                    "카테고리": info['label'],
                    "건수": info['count']
                })
        
        if category_data:
            df = pd.DataFrame(category_data)
            st.bar_chart(df.set_index("카테고리"))
    
    with col2:
        st.subheader("👤 Top 발신자")
        
        for sender, count in stats['top_senders'][:5]:
            st.write(f"• **{sender}**: {count}건")
    
    st.divider()
    
    # 우선순위 메일 - 개선된 버전
    render_priority_section(emails)
    
    st.divider()
    
    # 회신필요 메일 처리
    render_reply_required_section(emails)


def render_mail_list():
    """메일 목록 페이지 (필터링은 읽기 전용)"""
    st.title("📬 메일 목록")
    
    # 원본 데이터 읽기 (수정 금지)
    emails = st.session_state.emails
    if not emails:
        st.info("메일 데이터가 없습니다.")
        return
    
    # 필터 UI
    col1, col2 = st.columns(2)

    with col1:
        category_options = ["전체"] + list(MAIL_CATEGORIES.values())
        selected_category = st.selectbox(
            "카테고리 필터",
            options=category_options,
            key="mail_list_category_filter"
        )

    with col2:
        search_query = st.text_input(
            "🔍 검색",
            placeholder="제목 또는 발신자 검색...",
            key="mail_list_search_query"
        )

    # 필터링 (원본 수정 없이 뷰 전용 리스트 생성)
    temp_list = emails

    if selected_category != "전체":
        cat_codes = [k for k, v in MAIL_CATEGORIES.items() if v == selected_category]
        if cat_codes:
            temp_list = [e for e in temp_list if e.category == cat_codes[0]]

    if search_query.strip():
        q = search_query.strip().lower()
        temp_list = [
            e for e in temp_list
            if q in e.subject.lower() or q in e.sender.lower()
        ]
    
    st.write(f"**{len(temp_list)}건**의 메일")
    st.divider()
    
    # 메일 목록 표시 (읽기 전용)
    if not temp_list:
        st.info("검색 결과가 없습니다.")
        return
    
    for email in temp_list:
        category_label = MAIL_CATEGORIES.get(email.category, email.category)
        read_icon = "📧" if email.is_read else "📩"
        
        with st.expander(f"{read_icon} [{category_label}] {email.subject}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**발신자**: {email.sender} <{email.sender_email}>")
                st.write(f"**수신자**: {', '.join(email.recipients)}")
                st.write(f"**일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}")
                
                if email.attachments:
                    st.write(f"**첨부파일**: {', '.join(email.attachments)}")
            
            with col2:
                st.write(f"**카테고리**: {category_label}")
                st.write(f"**상태**: {'읽음' if email.is_read else '안읽음'}")
            
            st.divider()
            st.write(email.body_text)


def render_by_sender():
    """발신자별 페이지"""
    st.title("📁 발신자별 메일")
    
    emails = st.session_state.emails
    if not emails:
        st.info("메일 데이터가 없습니다.")
        return

    sender_groups = group_emails_by_sender(emails)

    # ── 발신자별 표시 레이블 구성 (이름 + 이메일) ──────────────────
    sender_label_map: dict = {}   # email_key → "이름 <email>" 표시용
    for email_key, group in sender_groups.items():
        rep = group[0]
        name = rep.sender.strip() if rep.sender else ""
        if name and name != email_key:
            sender_label_map[email_key] = f"{name}  <{email_key}>"
        else:
            sender_label_map[email_key] = email_key

    # ── 검색 필터 ───────────────────────────────────────────────────
    col_search, col_count = st.columns([3, 1])
    with col_search:
        search_q = st.text_input(
            "🔍 발신자 검색",
            placeholder="이름 또는 이메일 주소 입력...",
            key="sender_search"
        )
    with col_count:
        st.metric("총 발신자", f"{len(sender_groups)}명")

    all_keys = sorted(sender_groups.keys(), key=lambda k: -len(sender_groups[k]))
    if search_q:
        q = search_q.lower()
        filtered_keys = [k for k in all_keys if q in sender_label_map[k].lower()]
    else:
        filtered_keys = all_keys

    if not filtered_keys:
        st.warning("검색 결과가 없습니다.")
        return

    # ── 발신자 선택 selectbox (이름 + 이메일 표시) ──────────────────
    selected_idx = st.selectbox(
        "발신자 선택",
        range(len(filtered_keys)),
        format_func=lambda i: f"{sender_label_map[filtered_keys[i]]}  ({len(sender_groups[filtered_keys[i]])}건)",
        key="sender_select"
    )
    selected_key = filtered_keys[selected_idx]
    sender_emails = sender_groups[selected_key]
    rep_email = sender_emails[0]

    st.subheader(f"📬 {sender_label_map[selected_key]}")
    col1, col2, col3 = st.columns(3)
    col1.metric("수신 메일", f"{len(sender_emails)}건")
    unread = sum(1 for e in sender_emails if not e.is_read)
    col2.metric("미확인", f"{unread}건")
    attach = sum(1 for e in sender_emails if e.attachments)
    col3.metric("첨부파일 포함", f"{attach}건")
    st.divider()

    for email in sorted(sender_emails, key=lambda x: x.date if x.date else datetime.min, reverse=True):
        cat_label = MAIL_CATEGORIES.get(email.category, email.category)
        read_icon = "📧" if email.is_read else "📩"
        with st.expander(f"{read_icon} [{cat_label}] {email.subject}"):
            st.write(f"**일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}")
            st.write(f"**카테고리**: {cat_label}")
            if email.attachments:
                st.write(f"**첨부파일**: {', '.join(email.attachments)}")
            st.divider()
            st.write(email.body_text)


def render_search():
    """검색/질의 페이지"""
    st.title("🔍 메일 검색 및 AI 질의")

    emails = st.session_state.emails

    tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "🤖 AI 질의"])

    # ── 탭 1: 키워드 검색 ────────────────────────────────────────
    with tab_keyword:
        st.subheader("🔎 키워드 검색")

        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("키워드", placeholder="검색할 키워드 입력", key="kw_input")
        with col2:
            search_in = st.multiselect(
                "검색 대상",
                ["제목", "본문", "발신자"],
                default=["제목", "본문"],
                key="kw_target"
            )

        if keyword:
            results = []
            keyword_lower = keyword.lower()
            for email in emails:
                match = False
                if "제목" in search_in and keyword_lower in email.subject.lower():
                    match = True
                if "본문" in search_in and keyword_lower in email.body_text.lower():
                    match = True
                if "발신자" in search_in and keyword_lower in email.sender.lower():
                    match = True
                if match:
                    results.append(email)

            st.write(f"**{len(results)}건** 검색됨")
            for email in results:
                with st.expander(f"📧 {email.subject} — {email.sender}"):
                    st.write(f"**일시**: {email.date.strftime('%Y-%m-%d %H:%M') if email.date else 'N/A'}")
                    st.write(f"**카테고리**: {MAIL_CATEGORIES.get(email.category, email.category)}")
                    st.divider()
                    st.write(email.body_text[:600] + ("..." if len(email.body_text) > 600 else ""))

    # ── 탭 2: AI 질의 ─────────────────────────────────────
    with tab_ai:
        st.subheader("🤖 AI 질의")

        # 저장된 LLM 설정 로드
        llm_config = load_llm_config()
        provider = llm_config.get("provider", "openai").lower()
        api_key = llm_config.get("api_key", "")
        model = llm_config.get("model", "gpt-4o-mini")

        # LLM 설정 상태 표시
        if api_key:
            st.info(f"✅ **설정된 LLM**: {provider.upper()} ({model})")
        else:
            st.warning("⚠️ LLM이 설정되지 않았습니다. **설정 탭**에서 LLM 정보를 입력하세요.")
            return

        query = st.text_area(
            "질문 입력",
            placeholder="예: 이번 주 회의 일정 요약해줘 / 회신이 필요한 메일 알려줘 / 유재철님 메일 내용 정리해줘",
            height=80,
            key="ai_query"
        )

        if st.button("질문하기", type="primary", key="ai_query_btn"):
            if not query.strip():
                st.warning("질문을 입력하세요.")
            else:
                with st.spinner("AI가 분석 중..."):
                    # 키워드로 관련 메일 우선 필터링
                    related = search_emails(emails, query)
                    context_emails = related[:10] if related else emails[:10]

                    # 컨텍스트 구성
                    context_lines = []
                    for i, em in enumerate(context_emails, 1):
                        context_lines.append(
                            f"[메일{i}] 제목: {em.subject} | 발신자: {em.sender} | "
                            f"일시: {em.date.strftime('%Y-%m-%d %H:%M') if em.date else 'N/A'} | "
                            f"카테고리: {MAIL_CATEGORIES.get(em.category, em.category)}\n"
                            f"내용: {em.body_text[:500]}"
                        )
                    context_text = "\n\n".join(context_lines)

                    prompt = f"""당신은 업무 메일 분석 AI 어시스턴트입니다.
아래 메일 데이터를 바탕으로 사용자 질문에 한국어로 명확하게 답변하세요.

[메일 데이터 (최대 10건)]
{context_text}

[사용자 질문]
{query}

답변 시 관련 메일 제목과 발신자를 인용하고, 핵심 내용을 간결하게 정리해 주세요."""

                    try:
                        # 저장된 설정에서 LLM 클라이언트 생성
                        llm_client = init_llm_client(use_llm=True)
                        _max_tokens = load_llm_config().get("max_tokens", 1000)
                        if llm_client is None:
                            st.error("LLM 초기화 실패. 설정을 다시 확인하세요.")
                        else:
                            answer = llm_client.generate(prompt, max_tokens=_max_tokens)
                            st.success("**AI 응답**")
                            st.markdown(answer)

                            if related:
                                st.divider()
                                st.write(f"**참고된 관련 메일 ({len(context_emails)}건)**")
                                for em in context_emails:
                                    with st.expander(f"📧 {em.subject} — {em.sender}"):
                                        st.write(f"**일시**: {em.date.strftime('%Y-%m-%d %H:%M') if em.date else 'N/A'}")
                                        st.write(em.body_text[:400] + ("..." if len(em.body_text) > 400 else ""))
                    except Exception as e:
                        st.error(f"오류: {e}")


def search_emails(emails: list, query: str) -> list:
    """키워드 기반 검색 - 관련도에 따라 정렬"""
    keywords = query.lower().split()
    if not keywords:
        return []
    
    scored_results = []
    for email in emails:
        subject_lower = email.subject.lower()
        body_lower = email.body_text.lower()
        sender_lower = email.sender.lower()
        
        score = 0
        
        # 발신자 정확 일치 시 최고 점수
        if any(kw == sender_lower or sender_lower.startswith(kw) for kw in keywords):
            score += 100
        
        # 제목에 포함되면 높은 점수
        for kw in keywords:
            if kw in subject_lower:
                score += 50
        
        # 본문에 포함되면 낮은 점수
        for kw in keywords:
            if kw in body_lower:
                score += 10
        
        # 최소 하나의 키워드는 포함되어야 함
        if score > 0:
            scored_results.append((score, email))
    
    # 점수 내림차순으로 정렬
    scored_results.sort(key=lambda x: x[0], reverse=True)
    return [email for _, email in scored_results]


def generate_html_report(emails: list, output_dir: str) -> str:
    """이메일 데이터를 시각화 포함 HTML 보고서로 생성"""
    from mail_classifier import get_email_statistics, EmailAnalyzer
    import json as _json

    os.makedirs(output_dir, exist_ok=True)
    stats = get_email_statistics(emails)
    now = datetime.now()
    report_date = now.strftime("%Y년 %m월 %d일")
    file_name = f"report_{now.strftime('%Y%m%d_%H%M%S')}.html"
    file_path = os.path.join(output_dir, file_name)

    # 카테고리 데이터
    cat_labels = []
    cat_counts = []
    cat_colors = [
        "#EF4444","#F97316","#EAB308","#22C55E",
        "#3B82F6","#8B5CF6","#EC4899","#6B7280"
    ]
    for cat, info in stats["by_category"].items():
        if info["count"] > 0:
            cat_labels.append(info["label"])
            cat_counts.append(info["count"])

    # 날짜별 메일 수
    date_counter: dict = {}
    for em in emails:
        if em.date:
            d = em.date.strftime("%Y-%m-%d")
            date_counter[d] = date_counter.get(d, 0) + 1
    sorted_dates = sorted(date_counter.keys())
    date_labels = sorted_dates
    date_counts = [date_counter[d] for d in sorted_dates]

    # 발신자 Top 7
    sender_labels = [s for s, _ in stats["top_senders"][:7]]
    sender_counts = [c for _, c in stats["top_senders"][:7]]

    # 우선순위 메일
    analyzer = EmailAnalyzer()
    priority_analyses = analyzer.get_priority_emails(emails, top_n=10)
    urgent_rows = ""
    for a in priority_analyses[:10]:
        em = a.email
        badge = "🔴 긴급" if a.is_urgent else ("⭐ 중요" if a.is_important else "📌")
        deadline = a.deadline_text or "-"
        actions = ", ".join(a.action_items[:2]) if a.action_items else "-"
        date_str = em.date.strftime("%Y-%m-%d %H:%M") if em.date else "-"
        cat_label = MAIL_CATEGORIES.get(em.category, em.category)
        urgent_rows += f"""
        <tr>
          <td>{badge}</td>
          <td class="subject">{em.subject}</td>
          <td>{em.sender}</td>
          <td>{cat_label}</td>
          <td>{date_str}</td>
          <td>{deadline}</td>
          <td>{actions}</td>
        </tr>"""

    # 전체 메일 목록
    all_rows = ""
    for em in sorted(emails, key=lambda x: x.date if x.date else datetime.min, reverse=True):
        cat_label = MAIL_CATEGORIES.get(em.category, em.category)
        date_str = em.date.strftime("%Y-%m-%d %H:%M") if em.date else "-"
        read_badge = "읽음" if em.is_read else '<span class="unread">안읽음</span>'
        attach = "📎" if em.attachments else ""
        all_rows += f"""
        <tr>
          <td>{date_str}</td>
          <td class="subject">{em.subject}{attach}</td>
          <td>{em.sender}</td>
          <td><span class="cat-badge">{cat_label}</span></td>
          <td>{read_badge}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>메일 업무 보고서 — {report_date}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --primary: #3B82F6; --danger: #EF4444; --success: #22C55E;
    --warn: #F97316; --bg: #F1F5F9; --card: #FFFFFF;
    --text: #1E293B; --sub: #64748B; --border: #E2E8F0;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
         background: var(--bg); color: var(--text); font-size: 14px; }}
  header {{ background: var(--primary); color: #fff; padding: 24px 40px; }}
  header h1 {{ font-size: 22px; font-weight: 700; }}
  header p  {{ font-size: 13px; opacity: .8; margin-top: 4px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .kpi {{ background: var(--card); border-radius: 12px; padding: 20px 24px;
          box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .kpi .label {{ font-size: 12px; color: var(--sub); margin-bottom: 6px; }}
  .kpi .value {{ font-size: 28px; font-weight: 700; }}
  .kpi.danger .value {{ color: var(--danger); }}
  .kpi.warn  .value {{ color: var(--warn); }}
  .kpi.ok    .value {{ color: var(--success); }}
  .section-title {{ font-size: 16px; font-weight: 700; margin: 32px 0 16px; border-left: 4px solid var(--primary); padding-left: 10px; }}
  .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
  .chart-card {{ background: var(--card); border-radius: 12px; padding: 24px;
                 box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .chart-card h3 {{ font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--sub); }}
  .chart-wrap {{ position: relative; height: 260px; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card);
           border-radius: 12px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 32px; }}
  thead th {{ background: var(--primary); color: #fff; padding: 12px 14px;
              text-align: left; font-size: 13px; font-weight: 600; }}
  tbody tr:nth-child(even) {{ background: #F8FAFC; }}
  tbody tr:hover {{ background: #EFF6FF; }}
  tbody td {{ padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: top; }}
  .subject {{ max-width: 280px; }}
  .unread {{ background: #FEE2E2; color: var(--danger); padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }}
  .cat-badge {{ background: #DBEAFE; color: #1D4ED8; padding: 2px 8px; border-radius: 9999px; font-size: 11px; white-space: nowrap; }}
  footer {{ text-align: center; color: var(--sub); font-size: 12px; padding: 24px; }}
  @media(max-width:768px) {{
    .kpi-grid {{ grid-template-columns: repeat(2,1fr); }}
    .charts-row {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<header>
  <h1>📧 메일 업무 보고서</h1>
  <p>생성일시: {now.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; 총 {stats['total_count']}건 분석</p>
</header>
<div class="container">

  <!-- KPI -->
  <div class="kpi-grid">
    <div class="kpi danger">
      <div class="label">🔴 미확인 메일</div>
      <div class="value">{stats['unread_count']}건</div>
    </div>
    <div class="kpi warn">
      <div class="label">💬 회신 필요</div>
      <div class="value">{stats['by_category'].get('REPLY_REQUIRED', {}).get('count', 0)}건</div>
    </div>
    <div class="kpi warn">
      <div class="label">✅ 결재 요청</div>
      <div class="value">{stats['by_category'].get('APPROVAL_REQUEST', {}).get('count', 0)}건</div>
    </div>
    <div class="kpi ok">
      <div class="label">📎 첨부파일 포함</div>
      <div class="value">{stats['has_attachments']}건</div>
    </div>
  </div>

  <!-- 차트 -->
  <div class="section-title">📊 메일 현황 시각화</div>
  <div class="charts-row">
    <div class="chart-card">
      <h3>카테고리별 분포</h3>
      <div class="chart-wrap"><canvas id="catChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>발신자 Top 7</h3>
      <div class="chart-wrap"><canvas id="senderChart"></canvas></div>
    </div>
  </div>
  <div class="charts-row" style="grid-template-columns:1fr;">
    <div class="chart-card">
      <h3>날짜별 수신 추이</h3>
      <div class="chart-wrap" style="height:200px"><canvas id="dateChart"></canvas></div>
    </div>
  </div>

  <!-- 우선순위 메일 -->
  <div class="section-title">🔴 우선 처리 필요 메일</div>
  <table>
    <thead>
      <tr>
        <th>상태</th><th>제목</th><th>발신자</th><th>카테고리</th>
        <th>일시</th><th>기한</th><th>필요 액션</th>
      </tr>
    </thead>
    <tbody>{urgent_rows}</tbody>
  </table>

  <!-- 전체 메일 목록 -->
  <div class="section-title">📬 전체 메일 목록</div>
  <table>
    <thead>
      <tr><th>일시</th><th>제목</th><th>발신자</th><th>카테고리</th><th>상태</th></tr>
    </thead>
    <tbody>{all_rows}</tbody>
  </table>

</div>
<footer>Mail Reporter — 자동 생성 보고서 &copy; {now.year}</footer>

<script>
const CAT_LABELS  = {_json.dumps(cat_labels, ensure_ascii=False)};
const CAT_COUNTS  = {_json.dumps(cat_counts)};
const CAT_COLORS  = {_json.dumps(cat_colors[:len(cat_labels)])};
const SND_LABELS  = {_json.dumps(sender_labels, ensure_ascii=False)};
const SND_COUNTS  = {_json.dumps(sender_counts)};
const DATE_LABELS = {_json.dumps(date_labels)};
const DATE_COUNTS = {_json.dumps(date_counts)};

new Chart(document.getElementById('catChart'), {{
  type: 'doughnut',
  data: {{ labels: CAT_LABELS, datasets: [{{ data: CAT_COUNTS, backgroundColor: CAT_COLORS, borderWidth: 2 }}] }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ position: 'right', labels: {{ font: {{ size: 12 }} }} }} }} }}
}});

new Chart(document.getElementById('senderChart'), {{
  type: 'bar',
  data: {{ labels: SND_LABELS, datasets: [{{ label: '메일 수', data: SND_COUNTS,
    backgroundColor: '#3B82F6', borderRadius: 6 }}] }},
  options: {{ responsive: true, maintainAspectRatio: false, indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: {{ stepSize: 1 }} }} }} }}
}});

new Chart(document.getElementById('dateChart'), {{
  type: 'line',
  data: {{ labels: DATE_LABELS, datasets: [{{ label: '수신 건수', data: DATE_COUNTS,
    borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,.15)',
    tension: 0.4, fill: true, pointRadius: 4 }}] }},
  options: {{ responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});
</script>
</body>
</html>"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

    return file_path


def render_settings():
    """설정 페이지"""
    st.title("⚙️ 설정")
    
    st.subheader("🤖 LLM 설정")
    
    # 저장된 설정 로드
    saved_config = load_llm_config()
    
    with st.form("llm_settings"):
        provider_options = ["openai", "gemini", "ollama"]
        provider_display = {"openai": "OpenAI", "gemini": "Google Gemini", "ollama": "Ollama (로컬)"}
        
        default_provider = saved_config.get("provider", "openai")
        provider = st.selectbox(
            "LLM 제공자",
            options=provider_options,
            format_func=lambda x: provider_display.get(x, x),
            index=provider_options.index(default_provider) if default_provider in provider_options else 0
        )
        
        api_key = st.text_input(
            "API 키",
            value=saved_config.get("api_key", ""),
            type="password"
        )
        
        # 모델 기본값 설정
        model_defaults = {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-2.5-flash",
            "ollama": "llama3"
        }
        model = st.text_input(
            "모델명",
            value=saved_config.get("model", model_defaults.get(provider, ""))
        )
        
        max_tokens = st.number_input(
            "Max Tokens (최대 생성 토큰 수)",
            min_value=100,
            max_value=8000,
            value=int(saved_config.get("max_tokens", 1000)),
            step=100,
            help="LLM이 한 번에 생성할 수 있는 최대 토큰 수. 높을수록 더 긴 응답 생성 (기본값: 1000)"
        )
        
        if st.form_submit_button("💾 저장", type="primary"):
            if provider in ["openai", "gemini"] and not api_key:
                st.error(f"{provider_display.get(provider)}는 API 키가 필요합니다.")
            else:
                if save_llm_config(provider, api_key, model, int(max_tokens)):
                    st.success(f"✅ LLM 설정이 저장되었습니다!\n\n제공자: {provider_display.get(provider)}\n모델: {model}\nMax Tokens: {int(max_tokens)}")
                    st.info("설정이 대시보드와 명령줄 도구에서 자동으로 사용됩니다.")
                else:
                    st.error("설정 저장에 실패했습니다.")
    
    st.divider()
    
    st.subheader(" 데이터 관리")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ 모든 데이터 삭제", type="secondary"):
            st.warning("이 기능은 샘플에서 비활성화되어 있습니다.")
    
    with col2:
        if st.button("📤 데이터 내보내기"):
            st.info("데이터 내보내기 기능 (구현 예정)")


def main():
    """메인 함수"""
    # ★ 필터 상태 초기화 (처음 한 번만)
    if 'mail_list_category_filter' not in st.session_state:
        st.session_state.mail_list_category_filter = "전체"
    if 'mail_list_search_query' not in st.session_state:
        st.session_state.mail_list_search_query = ""

    # ★ emails.json 변경 감지 → 항상 최신 데이터 반영 (start.bat 실행 후 자동 갱신)
    json_path = os.path.join(config.data_dir, "emails.json")
    if os.path.exists(json_path):
        mtime = os.path.getmtime(json_path)
        if st.session_state.get('_emails_json_mtime') != mtime:
            st.session_state.emails = load_email_data()
            st.session_state._emails_json_mtime = mtime
    elif 'emails' not in st.session_state:
        # emails.json 없음: EML 자동 로드 시도 (최초 실행)
        st.session_state.emails = []
        eml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_data")
        if os.path.isdir(eml_dir):
            eml_files = [f for f in os.listdir(eml_dir) if f.lower().endswith(".eml")]
            if eml_files:
                with st.spinner(f"⏳ {len(eml_files)}개의 EML 파일을 자동으로 가져오는 중..."):
                    try:
                        added, skipped = run_eml_import(eml_dir, force=True)
                        st.session_state.emails = load_email_data()
                        if st.session_state.emails:
                            st.success(f"✅ 자동 로드 완료 — 추가/갱신 {added}건 | 중복 건너뜀 {skipped}건")
                    except Exception as e:
                        st.warning(f"⚠️ 자동 로드 실패: {str(e)}")
    
    # 사이드바 메뉴
    menu = render_sidebar()
    
    # 페이지 렌더링
    if menu == "📊 대시보드":
        render_dashboard()
    elif menu == "📬 메일 목록":
        render_mail_list()
    elif menu == "📁 발신자별":
        render_by_sender()
    elif menu == "🔍 검색/질의":
        render_search()
    elif menu == "⚙️ 설정":
        render_settings()


if __name__ == "__main__":
    main()
