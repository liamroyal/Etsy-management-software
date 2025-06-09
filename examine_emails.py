import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone, timedelta
import os
from typing import List, Dict
from config import (
    EMAIL_IMAP_SERVER,
    EMAIL_USERNAME,
    EMAIL_PASSWORD,
    ALLOWED_SENDERS
)

def decode_email_subject(subject) -> str:
    """Decode email subject"""
    if subject is None:
        return ""
    
    decoded_headers = decode_header(subject)
    subject_parts = []
    
    for content, encoding in decoded_headers:
        if isinstance(content, bytes):
            if encoding:
                try:
                    subject_parts.append(content.decode(encoding))
                except:
                    subject_parts.append(content.decode('utf-8', 'ignore'))
            else:
                subject_parts.append(content.decode('utf-8', 'ignore'))
        else:
            subject_parts.append(content)
    
    return " ".join(subject_parts)

def get_email_body(msg) -> str:
    """Extract email body text"""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode()
                except:
                    return part.get_payload(decode=True).decode('utf-8', 'ignore')
    else:
        try:
            return msg.get_payload(decode=True).decode()
        except:
            return msg.get_payload(decode=True).decode('utf-8', 'ignore')
    return ""

def examine_recent_emails():
    print("Examining recent emails from each sender...")
    
    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        mail.login(EMAIL_USERNAME, EMAIL_PASSWORD.encode('utf-8').decode('utf-8'))
        mail.select('INBOX')
        
        # Search for emails from the last 30 days
        date_30_days_ago = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        _, message_numbers = mail.search(None, f'(SINCE "{date_30_days_ago}")')
        
        # Store emails by sender
        emails_by_sender = {sender: [] for sender in ALLOWED_SENDERS}
        
        for num in message_numbers[0].split():
            try:
                _, msg_data = mail.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)
                
                # Get sender
                sender = msg.get('from', '').lower()
                matching_sender = next(
                    (s for s in ALLOWED_SENDERS if s.lower() in sender),
                    None
                )
                
                if matching_sender:
                    # Get email details
                    subject = decode_email_subject(msg.get('subject', ''))
                    body = get_email_body(msg)
                    date_str = msg.get('date', '')
                    
                    try:
                        email_date = email.utils.parsedate_to_datetime(date_str)
                    except:
                        email_date = datetime.now(timezone.utc)
                    
                    emails_by_sender[matching_sender].append({
                        'subject': subject,
                        'body': body,
                        'date': email_date
                    })
            except Exception as e:
                print(f"Warning: Failed to process email: {str(e)}")
                continue
        
        # Display the last 5 emails from each sender
        for sender, emails in emails_by_sender.items():
            print(f"\n{'='*80}")
            print(f"Last {min(5, len(emails))} emails from {sender}:")
            print(f"{'='*80}")
            
            # Sort by date and take last 5
            sorted_emails = sorted(emails, key=lambda x: x['date'])[-5:]
            
            for i, email_data in enumerate(sorted_emails, 1):
                print(f"\nEmail {i}:")
                print(f"Date: {email_data['date']}")
                print(f"Subject: {email_data['subject']}")
                print("\nBody preview (first 500 characters):")
                print("-" * 40)
                body_preview = email_data['body'].replace('\r', '').strip()
                print(body_preview[:500] + ("..." if len(body_preview) > 500 else ""))
                print("-" * 40)
        
        # Logout
        mail.logout()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    examine_recent_emails() 