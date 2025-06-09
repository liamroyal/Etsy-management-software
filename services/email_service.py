import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone
import os
from typing import List, Dict, Optional
from config import (
    EMAIL_IMAP_SERVER,
    EMAIL_USERNAME,
    EMAIL_PASSWORD,
    ALLOWED_SENDERS,
    LAST_SCRAPE_FILE
)
import pytz

class EmailService:
    def __init__(self):
        self.imap_server = EMAIL_IMAP_SERVER
        self.username = EMAIL_USERNAME
        self.password = EMAIL_PASSWORD.encode('utf-8').decode('utf-8')  # Ensure password is UTF-8
        self.allowed_senders = ALLOWED_SENDERS
        self.last_scrape_file = LAST_SCRAPE_FILE
        
        # Ensure the directory for the last_scrape_file exists
        os.makedirs(os.path.dirname(self.last_scrape_file), exist_ok=True)
    
    def get_last_scrape_time(self) -> datetime:
        """Get the timestamp of the last email scrape"""
        try:
            if os.path.exists(self.last_scrape_file):
                with open(self.last_scrape_file, 'r') as f:
                    timestamp_str = f.read().strip()
                    dt = datetime.fromisoformat(timestamp_str)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            # If file doesn't exist, create it with a timestamp from 24 hours ago
            default_time = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )  # Start of today in UTC
            self.update_last_scrape_time(default_time)
            return default_time
        except Exception as e:
            print(f"Warning: Error reading last scrape time: {str(e)}")
            return datetime.min.replace(tzinfo=timezone.utc)
    
    def update_last_scrape_time(self, timestamp: datetime = None):
        """
        Update the timestamp of the last email scrape
        If no timestamp is provided, uses current time
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.last_scrape_file), exist_ok=True)
            
            # Write the timestamp
            with open(self.last_scrape_file, 'w') as f:
                if timestamp is None:
                    timestamp = datetime.now(timezone.utc)
                elif timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                f.write(timestamp.isoformat())
        except Exception as e:
            print(f"Warning: Failed to update last scrape time: {str(e)}")
    
    def decode_email_subject(self, subject) -> str:
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
    
    def get_email_body(self, msg) -> str:
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
    
    def compare_dates(self, dt1: datetime, dt2: datetime) -> bool:
        """
        Compare two datetime objects, handling timezone-naive dates
        Returns True if dt1 > dt2
        """
        if dt1.tzinfo is None:
            dt1 = dt1.replace(tzinfo=timezone.utc)
        if dt2.tzinfo is None:
            dt2 = dt2.replace(tzinfo=timezone.utc)
        return dt1 > dt2
    
    def scrape_new_emails(self, max_emails: int = None) -> List[Dict]:
        """
        Scrape new emails from allowed senders
        :param max_emails: Maximum number of emails to retrieve (None for all new emails)
        :return: List of email data dictionaries
        """
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.username, self.password)
            mail.select('inbox')
            
            # Search for emails from allowed senders
            search_criteria = []
            for sender in self.allowed_senders:
                _, messages = mail.search(None, f'FROM "{sender}"')
                if messages[0]:
                    search_criteria.extend(messages[0].split())
            
            email_list = []
            # Sort message IDs in reverse order (newest first)
            search_criteria.sort(reverse=True)
            
            # Limit the number of emails if specified
            if max_emails:
                search_criteria = search_criteria[:max_emails]
            
            for num in search_criteria:
                try:
                    _, msg_data = mail.fetch(num, '(RFC822)')
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Extract email data
                    subject = self.decode_email_subject(email_message['subject'])
                    sender = email_message['from']
                    recipient = email_message['to']
                    date = email.utils.parsedate_to_datetime(email_message['date'])
                    
                    # Only include emails received today (local time)
                    local_tz = datetime.now().astimezone().tzinfo
                    today = datetime.now(local_tz).date()
                    email_date_local = date.astimezone(local_tz).date() if date.tzinfo else date.date()
                    if email_date_local != today:
                        continue
                    
                    # Get email body
                    body = ""
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                break
                    else:
                        body = email_message.get_payload(decode=True).decode()
                    
                    email_data = {
                        'subject': subject,
                        'from': sender,
                        'to': recipient,
                        'date': date,
                        'body': body
                    }
                    
                    email_list.append(email_data)
                    
                except Exception as e:
                    print(f"Warning: Failed to process email: {str(e)}")
                    continue
            
            # Update last scrape time
            if email_list:  # Only update if we found new emails
                self.update_last_scrape_time()
            
            mail.close()
            mail.logout()
            
            return email_list
            
        except Exception as e:
            print(f"Warning: Failed to scrape emails: {str(e)}")
            return [] 