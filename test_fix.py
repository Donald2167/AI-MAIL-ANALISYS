#!/usr/bin/env python3
"""
파싱 오류 테스트 및 검증
"""
import os
import sys
from mail_crawler import parse_eml_file

def test_problematic_file():
    """문제가 있는 파일 테스트"""
    mail_dir = "mail_data"
    
    # 문제 파일
    problem_files = [
        "2026-05-14 0853_전유진_전달 실시간CMS 제안서 .eml",
    ]
    
    for filename in problem_files:
        filepath = os.path.join(mail_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠ 파일 없음: {filename}")
            continue
        
        print(f"\n{'='*80}")
        print(f"📧 테스트: {filename}")
        print(f"{'='*80}\n")
        
        try:
            email = parse_eml_file(filepath)
            
            print(f"✓ 파싱 성공!")
            print(f"\n[결과]")
            print(f"  Subject: {email.subject}")
            print(f"  Sender: {email.sender} <{email.sender_email}>")
            print(f"  Recipients: {', '.join(email.recipients)}")
            
            if email.forwarded_from.original_sender:
                print(f"\n[원본 정보 추출됨]")
                print(f"  Original Sender: {email.forwarded_from.original_sender}")
                print(f"  Original Subject: {email.forwarded_from.original_subject}")
                print(f"  Original To: {', '.join(email.forwarded_from.original_to)}")
            else:
                print(f"\n[원본 정보 미추출]")
            
        except Exception as e:
            print(f"✗ 파싱 실패: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_problematic_file()
