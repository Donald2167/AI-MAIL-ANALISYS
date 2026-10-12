"""
전달 메일 파싱 기능 사용 예시
"""

from mail_crawler import parse_eml_file
from pathlib import Path

def example_basic_usage():
    """기본 사용법"""
    
    # EML 파일 파싱
    email = parse_eml_file("mail_data/example_forwarded.eml")
    
    # 기본 메일 정보
    print(f"Subject: {email.subject}")
    print(f"From: {email.sender} <{email.sender_email}>")
    print(f"To: {email.recipients}")
    
    # 전달 메일 원본 정보 (조건 만족 시에만 채워짐)
    if email.forwarded_from.original_sender:
        print("\n[원본 메일 정보]")
        print(f"보낸사람: {email.forwarded_from.original_sender}")
        print(f"이메일: {email.forwarded_from.original_sender_email}")
        print(f"보낸 날짜: {email.forwarded_from.original_date}")
        print(f"받는 사람: {'; '.join(email.forwarded_from.original_to)}")
        print(f"참조: {'; '.join(email.forwarded_from.original_cc)}")
        print(f"제목: {email.forwarded_from.original_subject}")
        print(f"본문 미리보기: {email.forwarded_from.original_body[:200]}...")


def example_batch_processing():
    """배치 처리 예시"""
    
    from mail_crawler import import_eml_directory
    import json
    
    # 디렉토리의 모든 전달 메일 가져오기
    added, skipped = import_eml_directory(
        eml_dir="mail_data",
        json_path="data/emails.json",
        classify=True,
        filename_filter=None  # 모든 .eml 파일 처리
    )
    
    print(f"추가/갱신됨: {added}개")
    print(f"건너뛰어짐: {skipped}개")
    
    # JSON에서 로드하여 전달 메일만 필터링
    from mail_crawler import load_emails_from_json
    
    emails = load_emails_from_json("data/emails.json")
    forwarded_emails = [e for e in emails if e.forwarded_from.original_sender]
    
    print(f"\n전달 메일 총 {len(forwarded_emails)}개 발견")
    
    # 원본 발신자별로 그룹화
    from collections import defaultdict
    by_original_sender = defaultdict(list)
    
    for email in forwarded_emails:
        sender = email.forwarded_from.original_sender
        by_original_sender[sender].append(email)
    
    for sender, emails_from_sender in by_original_sender.items():
        print(f"\n{sender}로부터: {len(emails_from_sender)}개")
        for email in emails_from_sender[:3]:  # 최대 3개만 표시
            print(f"  - {email.forwarded_from.original_subject}")


def example_filtering():
    """특정 조건의 전달 메일 필터링"""
    
    from mail_crawler import load_emails_from_json
    
    emails = load_emails_from_json("data/emails.json")
    
    # 1. 원본 발신자가 특정인인 메일
    specific_sender = "Lee Hee Won"
    filtered = [
        e for e in emails 
        if e.forwarded_from.original_sender == specific_sender
    ]
    print(f"{specific_sender}로부터 받은 메일: {len(filtered)}개")
    
    # 2. 특정 키워드를 포함한 원본 제목의 메일
    keyword = "시스템"
    filtered = [
        e for e in emails 
        if keyword in e.forwarded_from.original_subject
    ]
    print(f"'{keyword}'를 포함한 메일: {len(filtered)}개")
    
    # 3. 원본 메일에 참조자가 있는 메일
    with_cc = [
        e for e in emails 
        if e.forwarded_from.original_cc
    ]
    print(f"참조자가 있는 원본 메일: {len(with_cc)}개")


def example_export_to_csv():
    """전달 메일 정보를 CSV로 내보내기"""
    
    import csv
    from mail_crawler import load_emails_from_json
    
    emails = load_emails_from_json("data/emails.json")
    forwarded_emails = [e for e in emails if e.forwarded_from.original_sender]
    
    with open("forwarded_emails.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "전달 메일 ID",
            "전달 제목",
            "전달 발신자",
            "원본 발신자",
            "원본 이메일",
            "원본 날짜",
            "원본 받는 사람",
            "원본 참조",
            "원본 제목",
        ])
        
        for email in forwarded_emails:
            writer.writerow([
                email.id,
                email.subject,
                email.sender,
                email.forwarded_from.original_sender,
                email.forwarded_from.original_sender_email,
                email.forwarded_from.original_date,
                "; ".join(email.forwarded_from.original_to),
                "; ".join(email.forwarded_from.original_cc),
                email.forwarded_from.original_subject,
            ])
    
    print(f"✓ forwarded_emails.csv로 내보내기 완료 ({len(forwarded_emails)}개)")


if __name__ == "__main__":
    print("=== 전달 메일 파싱 기능 사용 예시 ===\n")
    
    print("1. 기본 사용법")
    print("-" * 50)
    # example_basic_usage()
    
    print("\n2. 배치 처리")
    print("-" * 50)
    # example_batch_processing()
    
    print("\n3. 필터링")
    print("-" * 50)
    # example_filtering()
    
    print("\n4. CSV 내보내기")
    print("-" * 50)
    # example_export_to_csv()
