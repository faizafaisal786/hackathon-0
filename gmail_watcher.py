"""
📧 Gmail Watcher
Monitors Gmail for unread emails and converts them to markdown files

Author: AI Employee System
Date: February 9, 2026
Requirements: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import os
import pickle
import base64
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
import time

try:
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    print("⚠️ Gmail libraries not installed. Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")


class GmailWatcher:
    """Watches Gmail for unread emails and converts them to markdown"""
    
    # Gmail API scope
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, vault_path, credentials_file=None):
        """
        Initialize Gmail Watcher
        
        Args:
            vault_path: Path to AI_Employee_Vault
            credentials_file: Path to Gmail credentials JSON file
        """
        self.vault_path = Path(vault_path)
        self.needs_action_path = self.vault_path / "Needs_Action"
        self.logs_path = self.vault_path / "Logs"
        self.credentials_file = credentials_file or "credentials.json"
        self.token_file = "gmail_token.pickle"
        
        # Create directories
        self.needs_action_path.mkdir(exist_ok=True)
        self.logs_path.mkdir(exist_ok=True)
        
        self.service = None
        self.processed_emails = set()
        self._load_processed_emails()
    
    def authenticate(self):
        """Authenticate with Gmail API"""
        if not GMAIL_AVAILABLE:
            print("❌ Gmail libraries not installed")
            return False
        
        try:
            creds = None
            
            # Load token if exists
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        print(f"❌ Credentials file not found: {self.credentials_file}")
                        print("📝 Download from: https://console.cloud.google.com/")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save token
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            print("✅ Gmail authentication successful")
            return True
            
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            self._log_action("AUTH", "ERROR", str(e))
            return False
    
    def fetch_unread_emails(self):
        """Fetch unread emails from Gmail"""
        if not self.service:
            return []
        
        try:
            # Query for unread emails
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            print(f"📬 Found {len(messages)} unread emails")
            
            return messages
            
        except Exception as e:
            print(f"❌ Error fetching emails: {str(e)}")
            self._log_action("FETCH", "ERROR", str(e))
            return []
    
    def get_email_details(self, message_id):
        """Get full email details"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            # Extract email details
            email_data = {
                'id': message_id,
                'subject': self._get_header(headers, 'Subject'),
                'from': self._get_header(headers, 'From'),
                'to': self._get_header(headers, 'To'),
                'date': self._get_header(headers, 'Date'),
                'body': self._get_email_body(message)
            }
            
            return email_data
            
        except Exception as e:
            print(f"❌ Error getting email details: {str(e)}")
            return None
    
    def _get_header(self, headers, name):
        """Extract header value"""
        for header in headers:
            if header['name'] == name:
                return header['value']
        return "Not Found"
    
    def _get_email_body(self, message):
        """Extract email body"""
        try:
            if 'parts' in message['payload']:
                parts = message['payload']['parts']
                data = parts[0]['body'].get('data', '')
            else:
                data = message['payload']['body'].get('data', '')
            
            if data:
                text = base64.urlsafe_b64decode(data).decode('utf-8')
                return text
            else:
                return "[No content]"
                
        except Exception as e:
            return f"[Body extraction error: {str(e)}]"
    
    def convert_to_markdown(self, email_data):
        """Convert email to markdown format"""
        content = f"""# 📧 Email

## From
{email_data['from']}

## To
{email_data['to']}

## Subject
{email_data['subject']}

## Date
{email_data['date']}

---

## Body

{email_data['body']}

---

**Email ID:** {email_data['id']}  
**Source:** Gmail Watcher  
**Processed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return content
    
    def save_email_as_markdown(self, email_data):
        """Save email as markdown file in Needs_Action"""
        try:
            # Create filename from subject and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            subject = email_data['subject'].replace('/', '_').replace('\\', '_')[:50]
            filename = f"{timestamp}_EMAIL_{subject}.md"
            
            filepath = self.needs_action_path / filename
            
            # Convert to markdown
            markdown_content = self.convert_to_markdown(email_data)
            
            # Save file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Track processed email
            self.processed_emails.add(email_data['id'])
            self._save_processed_emails()
            
            print(f"✅ Saved: {filename}")
            self._log_action("SAVE", "SUCCESS", f"Saved {filename}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving email: {str(e)}")
            self._log_action("SAVE", "ERROR", str(e))
            return False
    
    def mark_email_as_read(self, message_id):
        """Mark email as read in Gmail"""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"⚠️ Could not mark as read: {str(e)}")
            return False
    
    def process_unread_emails(self):
        """Process all unread emails"""
        if not self.service:
            print("❌ Not authenticated")
            return
        
        emails = self.fetch_unread_emails()
        
        for message in emails:
            message_id = message['id']
            
            # Skip if already processed
            if message_id in self.processed_emails:
                continue
            
            # Get email details
            email_data = self.get_email_details(message_id)
            if not email_data:
                continue
            
            # Save as markdown
            if self.save_email_as_markdown(email_data):
                # Mark as read
                self.mark_email_as_read(message_id)
    
    def watch_continuous(self, interval=300):
        """
        Continuously watch for new unread emails
        
        Args:
            interval: Check interval in seconds (default: 5 minutes)
        """
        if not self.service:
            print("❌ Not authenticated")
            return
        
        print(f"\n🔍 Gmail Watcher Started (checking every {interval}s)")
        print("⏹️  Press Ctrl+C to stop\n")
        
        try:
            while True:
                print(f"⏰ Checking for new emails... ({datetime.now().strftime('%H:%M:%S')})")
                self.process_unread_emails()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping Gmail Watcher...")
            self._log_action("WATCHER", "INFO", "Watcher stopped by user")
    
    def _load_processed_emails(self):
        """Load list of already processed emails"""
        try:
            log_file = self.logs_path / "gmail_processed.txt"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    self.processed_emails = set(line.strip() for line in f)
        except Exception as e:
            print(f"⚠️ Could not load processed emails: {str(e)}")
    
    def _save_processed_emails(self):
        """Save list of processed emails"""
        try:
            log_file = self.logs_path / "gmail_processed.txt"
            with open(log_file, 'w') as f:
                for email_id in self.processed_emails:
                    f.write(f"{email_id}\n")
        except Exception as e:
            print(f"⚠️ Could not save processed emails: {str(e)}")
    
    def _log_action(self, action, status, message):
        """Log watcher activity"""
        try:
            log_file = self.logs_path / "gmail_watcher.log"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] {action} | {status} | {message}\n"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"⚠️ Logging error: {str(e)}")


def main():
    """Main entry point"""
    
    print("╔═════════════════════════════════════════╗")
    print("║   📧 GMAIL WATCHER 📧                 ║")
    print("║   Version: 1.0                         ║")
    print("╚═════════════════════════════════════════╝\n")
    
    VAULT_PATH = r"c:\Users\HDD BANK\Desktop\Obsidian Vaults\AI_Employee_Vault"
    
    # Verify path
    if not Path(VAULT_PATH).exists():
        print(f"❌ Vault path does not exist: {VAULT_PATH}")
        return
    
    # Create watcher
    watcher = GmailWatcher(VAULT_PATH)
    
    # Authenticate
    if not watcher.authenticate():
        print("❌ Authentication failed")
        return
    
    # Start watching (check every 5 minutes)
    watcher.watch_continuous(interval=300)


if __name__ == "__main__":
    main()
