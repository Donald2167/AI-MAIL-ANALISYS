"""
메일 리포터 - 메인 진입점

사용 방법:
  python main.py                        # EML 가져오기 → 대시보드 (기본)
  python main.py import-eml             # mail_data/ 폴더의 .eml 파일 가져오기만
  python main.py import-eml --llm       # LLM으로 분류하며 가져오기
  python main.py dashboard              # 대시보드만 실행 (이미 데이터 있을 때)
  python main.py report                 # HTML 보고서 생성
  python main.py query                  # 터미널 대화형 질의
"""
import argparse
import os
import sys

# 모듈 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mail_crawler import save_emails_to_json, load_emails_from_json, import_eml_directory
from mail_rag import MailQueryEngine, interactive_query
from mail_classifier import MailClassifier
from summary_generator import MockLLMClient, OpenAIClient, GeminiClient, OllamaClient
from config import AppConfig, LLMConfig, load_llm_config, save_llm_config


EML_DATA_DIR = os.path.join(os.path.dirname(__file__), "mail_data")


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
                print("⚠ OpenAI API 키가 설정되지 않았습니다.")
                print("  설정 방법: 대시보드 설정 탭에서 설정하거나 set LLM_API_KEY=your_api_key")
                return None
            print(f"🤖 OpenAI 모델 사용: {model}")
            return OpenAIClient(api_key=api_key, model=model)
        
        elif provider == "gemini":
            if not api_key:
                print("⚠ Gemini API 키가 설정되지 않았습니다.")
                print("  설정 방법: 대시보드 설정 탭에서 설정하거나 set LLM_API_KEY=your_api_key")
                return None
            print(f"🤖 Gemini 모델 사용: {model}")
            return GeminiClient(api_key=api_key, model=model)
        
        elif provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            print(f"🤖 Ollama 모델 사용: {model} ({base_url})")
            return OllamaClient(model=model, base_url=base_url)
        
        else:
            print(f"⚠ 알 수 없는 LLM 제공자: {provider}")
            print("  지원하는 제공자: openai, gemini, ollama")
            return None
    
    except Exception as e:
        print(f"⚠ LLM 초기화 실패: {e}")
        print("  키워드 기반 분류로 진행합니다.")
        return None


def run_dashboard():
    """Streamlit 대시보드 실행"""
    import subprocess
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.py")
    subprocess.run(["streamlit", "run", dashboard_path])


def run_eml_import(app_config: AppConfig, eml_dir: str = None,
                   classify: bool = True, force: bool = False, use_llm: bool = False, 
                   verify_junk: bool = False):
    """mail_data/ 폴더의 .eml 파일을 emails.json에 병합 저장
    
    Args:
        verify_junk: True이면 정크의심 메일만 LLM으로 2차 검증
    """
    eml_dir = eml_dir or EML_DATA_DIR
    json_path = os.path.join(app_config.data_dir, "emails.json")

    if not os.path.isdir(eml_dir):
        print(f"❌ EML 폴더가 없습니다: {eml_dir}")
        print(f"   mail_data/ 폴더에 .eml 파일을 넣은 뒤 다시 실행하세요.")
        return 0, 0

    eml_count = sum(1 for f in os.listdir(eml_dir) if f.lower().endswith(".eml"))
    if eml_count == 0:
        print(f"⚠  {eml_dir} 에 .eml 파일이 없습니다.")
        return 0, 0

    print(f"📂 EML 폴더 : {eml_dir}  ({eml_count}개 파일)")
    print(f"💾 저장 위치: {json_path}")
    
    llm_client = None
    
    # verify_junk 모드 확인
    if verify_junk:
        print("🔍 정크의심 메일 2차 검증 모드")
        llm_client = init_llm_client(use_llm=True)
        if not llm_client:
            print("⚠ LLM 초기화 실패, 정크 검증을 스킵합니다.")
            verify_junk = False
    elif classify and use_llm:
        print("🤖 LLM 기반 분류를 사용합니다.")
        llm_client = init_llm_client(use_llm=True)
        if not llm_client:
            print("⚠ LLM 초기화 실패, 키워드 기반 분류로 진행합니다.")
    else:
        if classify:
            print("🔑 키워드 기반 분류를 사용합니다.")

    # 1단계: EML 파싱
    print("\n📧 EML 파일 파싱 중...")
    added, skipped = import_eml_directory(
        eml_dir, json_path,
        classify=False, force=force, filename_filter=None
    )
    
    # 2단계: 분류
    if classify:
        print("\n🏷️  메일 분류 중...")
        emails = load_emails_from_json(json_path)
        classifier = MailClassifier(llm_client=llm_client if use_llm else None)
        emails = classifier.classify_batch(emails, use_llm=use_llm and llm_client is not None)
        save_emails_to_json(emails, json_path)
        print("✅ 분류 완료")
    
    # 3단계: 정크의심 메일 2차 검증 (선택사항)
    if verify_junk and llm_client:
        print("\n" + "="*60)
        emails = load_emails_from_json(json_path)
        classifier = MailClassifier(llm_client=llm_client)
        reclassified, confirmed_junk = classifier.reclassify_junk_emails_with_llm(emails)
        save_emails_to_json(emails, json_path)
        print("="*60)
    elif verify_junk and not llm_client:
        print("\n⚠  정크 검증을 요청했지만 LLM이 초기화되지 않아 스킵됩니다.")
    
    print(f"\n✅ 최종 완료")
    print(f"   추가/갱신: {added}건 | 중복 건너뜀: {skipped}건")
    return added, skipped


def run_report(app_config: AppConfig):
    """HTML 보고서 생성"""
    from dashboard import generate_html_report
    data_file = os.path.join(app_config.data_dir, "emails.json")
    if not os.path.exists(data_file):
        print("❌ 메일 데이터가 없습니다. 먼저 import-eml 을 실행하세요.")
        return
    emails = load_emails_from_json(data_file)
    path = generate_html_report(emails, app_config.summary_dir)
    print(f"✅ HTML 보고서 생성 완료: {path}")


def run_query_mode(app_config: AppConfig):
    """터미널 대화형 질의 모드"""
    data_file = os.path.join(app_config.data_dir, "emails.json")
    if not os.path.exists(data_file):
        print("메일 데이터가 없습니다. 먼저 import-eml 을 실행하세요.")
        return
    emails = load_emails_from_json(data_file)
    interactive_query(emails)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="📧 메일 리포터 — 로컬 EML 파일 기반 업무 메일 분석 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""예시:
  python main.py                          EML 가져오기 후 대시보드 실행
  python main.py import-eml               EML 파일만 가져오기 (대시보드 미실행)
  python main.py import-eml --llm         LLM으로 분류하며 가져오기
  python main.py import-eml --force       모든 EML 재파싱
  python main.py dashboard                대시보드만 실행
  python main.py report                   HTML 보고서 생성
  python main.py query                    터미널 대화형 질의

LLM 설정 (환경 변수):
  set LLM_PROVIDER=openai       (openai, gemini, ollama)
  set LLM_API_KEY=your_api_key
  set LLM_MODEL=gpt-4o-mini     (OpenAI/Gemini 모델명)
  set OLLAMA_BASE_URL=http://localhost:11434  (Ollama 주소)
"""
    )

    subparsers = parser.add_subparsers(dest="command")

    # import-eml
    eml_parser = subparsers.add_parser("import-eml", help="mail_data/ 폴더의 .eml 파일 가져오기")
    eml_parser.add_argument("--eml-dir", default=EML_DATA_DIR, help=".eml 폴더 경로")
    eml_parser.add_argument("--force", action="store_true", help="기존 항목도 재파싱하여 덮어씀")
    eml_parser.add_argument("--no-classify", action="store_true", help="자동 분류 건너뜀")
    eml_parser.add_argument("--llm", action="store_true", help="LLM으로 분류 (기본값: 키워드 기반)")
    eml_parser.add_argument("--verify-junk", action="store_true", help="정크의심 메일만 LLM으로 2차 검증")

    # dashboard
    subparsers.add_parser("dashboard", help="Streamlit 대시보드 실행")

    # report
    subparsers.add_parser("report", help="HTML 보고서 생성")

    # query
    subparsers.add_parser("query", help="터미널 대화형 질의 모드")

    args = parser.parse_args()
    app_config = AppConfig()

    # 명령 없이 실행 → EML 가져오기 후 대시보드
    if args.command is None:
        print("=" * 55)
        print(" 📧 메일 리포터 시작")
        print("=" * 55)
        added, _ = run_eml_import(app_config)
        if added > 0:
            print()
        print("🌐 대시보드를 실행합니다 → http://localhost:8501")
        run_dashboard()
        return

    if args.command == "import-eml":
        run_eml_import(app_config, args.eml_dir,
                       classify=not args.no_classify, force=args.force, use_llm=args.llm,
                       verify_junk=args.verify_junk)

    elif args.command == "dashboard":
        run_dashboard()

    elif args.command == "report":
        run_report(app_config)

    elif args.command == "query":
        run_query_mode(app_config)


if __name__ == "__main__":
    main()
