#!/usr/bin/env python3
"""
전달 메일 파싱 테스트 스크립트
"""
import os
import sys
from mail_crawler import parse_eml_file

def test_forwarded_email_parsing():
    """전달 메일 파싱 테스트"""
    mail_dir = "mail_data"
    
    # 전달 메일 찾기
    forwarded_files = [
        f for f in os.listdir(mail_dir) 
        if "전달" in f and f.endswith(".eml")
    ]
    
    if not forwarded_files:
        print("✗ 전달 메일이 없습니다.")
        return
    
    test_file = forwarded_files[0]
    filepath = os.path.join(mail_dir, test_file)
    
    print(f"\n📧 테스트 파일: {test_file}")
    print("=" * 80)
    
    try:
        email = parse_eml_file(filepath)
        
        print(f"\n[전달 메일 헤더]")
        print(f"  Subject: {email.subject}")
        print(f"  Sender: {email.sender} <{email.sender_email}>")
        print(f"  Recipients: {', '.join(email.recipients)}")
        print(f"  Date: {email.date}")
        
        print(f"\n[원본 메일 정보 (forwarded_from)]")
        if email.forwarded_from.original_sender:
            print(f"  ✓ 보낸사람: {email.forwarded_from.original_sender}")
            print(f"    이메일: {email.forwarded_from.original_sender_email}")
        else:
            print(f"  ✗ 보낸사람: [추출 실패]")
        
        if email.forwarded_from.original_date:
            print(f"  ✓ 보낸 날짜: {email.forwarded_from.original_date}")
        else:
            print(f"  ✗ 보낸 날짜: [추출 실패]")
        
        if email.forwarded_from.original_to:
            print(f"  ✓ 받는 사람: {'; '.join(email.forwarded_from.original_to)}")
        else:
            print(f"  ✗ 받는 사람: [추출 실패]")
        
        if email.forwarded_from.original_cc:
            print(f"  ✓ 참조: {'; '.join(email.forwarded_from.original_cc)}")
        else:
            print(f"  - 참조: [없음]")
        
        if email.forwarded_from.original_subject:
            print(f"  ✓ 제목: {email.forwarded_from.original_subject}")
        else:
            print(f"  ✗ 제목: [추출 실패]")
        
        if email.forwarded_from.original_body:
            body_preview = email.forwarded_from.original_body[:100].replace('\n', ' ')
            print(f"  ✓ 본문: {body_preview}...")
        else:
            print(f"  ✗ 본문: [추출 실패]")
        
        print("\n" + "=" * 80)
        print("✓ 테스트 완료")
        
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_forwarded_email_parsing()
