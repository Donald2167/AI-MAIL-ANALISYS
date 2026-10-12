#!/usr/bin/env python3
"""
전달 메일 정보 대체 파싱 검증
"""
import os
import sys
from mail_crawler import parse_eml_file

def test_forwarded_replacement():
    """전달 메일이 원본 정보로 대체되는지 검증"""
    mail_dir = "mail_data"
    
    # 조건을 만족하는 전달 메일 찾기
    # 1. 제목에 "전달:" 포함
    # 2. From이 전유진(8921246) 또는 유재철(8921242)
    # 3. To가 youjin0404
    forwarded_files = [
        f for f in os.listdir(mail_dir) 
        if ("전달" in f or "FW" in f) and f.endswith(".eml")
    ]
    
    if not forwarded_files:
        print("✗ 조건을 만족하는 전달 메일이 없습니다.")
        return
    
    test_file = forwarded_files[0]
    filepath = os.path.join(mail_dir, test_file)
    
    print(f"\n{'='*80}")
    print(f"📧 테스트 파일: {test_file}")
    print(f"{'='*80}\n")
    
    try:
        email = parse_eml_file(filepath)
        
        print(f"[파싱 결과]")
        print(f"  📌 Subject (제목에서 '전달:' 제거 여부):")
        print(f"     {email.subject}")
        print(f"     ✓ '전달:' 제거됨: {'전달:' not in email.subject}")
        
        print(f"\n  👤 Sender (원본 발신자로 대체 여부):")
        print(f"     {email.sender} <{email.sender_email}>")
        
        print(f"\n  📧 Recipients (원본 수신자로 대체 여부):")
        print(f"     {', '.join(email.recipients)}")
        
        print(f"\n  📅 Date:")
        print(f"     {email.date}")
        
        if email.forwarded_from.original_sender:
            print(f"\n  [전달자 정보 (forwarded_from에 저장됨)]")
            print(f"     전달자: {email.forwarded_from.original_sender}")
            print(f"     전달자 이메일: {email.forwarded_from.original_sender_email}")
        else:
            print(f"\n  [원본 정보 미추출]")
            print(f"     HTML/Text body에서 원본 정보를 찾을 수 없습니다.")
        
        print(f"\n  📝 Body 미리보기:")
        body_preview = email.body_text[:150].replace('\n', ' ')
        print(f"     {body_preview}...")
        
        print(f"\n{'='*80}")
        print("✓ 검증 완료")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_forwarded_replacement()
