# Configuration file for the Etsy Management Software
import os

# Email Configuration
EMAIL_IMAP_SERVER = os.environ.get("EMAIL_IMAP_SERVER", "imap.gmail.com")
EMAIL_USERNAME = os.environ.get("EMAIL_USERNAME", "your-email@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "your-app-password")
ALLOWED_SENDERS = [
    "noreply@etsy.com",
    "orders@etsy.com",
    "marketplace@etsy.com"
]
LAST_SCRAPE_FILE = "data/last_scrape.txt"

# Google Sheets Configuration (Optional)
GOOGLE_SHEETS_CREDENTIALS_PATH = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")

# File Upload Configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'gif'}

# Application Configuration
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# OCR Configuration - Cloud deployment typically doesn't have tesseract
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "/usr/bin/tesseract") 