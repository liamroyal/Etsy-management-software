# 🛍️ Order Management Platform

A comprehensive business operations platform for managing orders, products, shipping carriers, and productivity tasks. Built with Flask and featuring a modern sidebar navigation interface.

## ✨ Features

### 📊 Data Management
- **Excel Upload**: Process order data from Excel files (.xlsx, .xls) with automatic Google Sheets sync
- **Bulk Orders**: Process multiple orders with format: `Product Name | Quantity | Customer Email`
- **Tracking Updates**: Bulk update tracking numbers for existing orders

### 🤖 Automation
- **Email Scanner**: Automated email scanning for order detection with configurable settings
- **Real-time Processing**: Automatic duplicate handling and data validation

### 📦 Catalog Management
- **Product Catalog**: Complete CRUD operations for product inventory
- **OCR Integration**: Extract products from screenshots using Tesseract OCR
- **Sourcing Information**: Track fulfillment links and agent details
- **Image Management**: Upload and manage product images

### 🚚 Shipping Carriers
- **Carrier Database**: Searchable database of shipping carriers
- **Etsy Approval Tracking**: Visual indicators for Etsy-approved carriers
- **Example Tracking Numbers**: Reference tracking number formats
- **Full CRUD Operations**: Add, edit, delete carriers

### 📝 Productivity
- **Notes & Todos**: Task management with completion confirmation
- **Card-based Interface**: Modern todo cards with edit/delete functionality
- **Active Task Counter**: Real-time counter in navigation

## 🛠️ Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Storage**: JSON-based persistence
- **OCR**: Tesseract OCR for screenshot processing
- **Integration**: Google Sheets API
- **UI**: Modern responsive design with sidebar navigation

## 📁 Project Structure

```
internal_app/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── services/             # Business logic services
│   ├── carrier_service.py    # Shipping carrier management
│   ├── email_service.py      # Email processing
│   ├── excel_service.py      # Excel file processing
│   ├── google_sheets_service.py # Google Sheets integration
│   ├── ocr_service.py        # OCR functionality
│   ├── product_service.py    # Product management
│   └── todo_service.py       # Todo/notes management
├── templates/            # HTML templates
│   └── index.html           # Main application template
├── static/              # Static assets
│   └── product_images/      # Product image storage
├── data/               # JSON data files
│   ├── carriers.json       # Carrier database
│   ├── products.json       # Product catalog
│   └── todos.json          # Todo/notes data
└── uploads/            # Temporary file uploads
```

## 🚀 Setup Instructions

### Prerequisites
- Python 3.7+
- Tesseract OCR (for screenshot processing)
- Google Sheets API credentials (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd internal_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Tesseract OCR** (macOS with Homebrew)
   ```bash
   brew install tesseract
   ```

4. **Set up Google Sheets (Optional)**
   - Create a Google Cloud project
   - Enable Google Sheets API
   - Download `credentials.json` to project root
   - Update `config.py` with your spreadsheet ID

5. **Create configuration file**
   ```bash
   cp config.py.example config.py
   # Edit config.py with your settings
   ```

6. **Run the application**
   ```bash
   python3 app.py
   ```

7. **Access the application**
   - Open your browser to `http://localhost:5000`
   - If port 5000 is in use (macOS AirPlay), the app will prompt for an alternative port

## 🎨 User Interface

### Navigation Sections
- **Data Management**: Excel Upload, Bulk Orders
- **Automation**: Email Scanner
- **Catalog**: Products, Shipping Carriers
- **Productivity**: Notes & Todos

### Key Features
- **Responsive Design**: Works on desktop and mobile
- **Real-time Search**: Filter products and carriers
- **Modal Dialogs**: Edit items without page refresh
- **Flash Messages**: Instant feedback for user actions
- **Progress Indicators**: Visual counters for todos and carriers

## 📊 Data Management

### Excel Upload Format
The system expects Excel files with order data including:
- Order numbers
- Customer information
- Product details
- Tracking numbers (optional)

### Bulk Order Format
```
Product Name | Quantity | Customer Email
Handmade Scarf | 2 | customer1@email.com
Wooden Bowl | 1 | customer2@email.com
```

### Tracking Update Format
```
#3695239669 UK216203823YP
#3695239670 UK216203824YP
```

## 🔧 Configuration

Key configuration options in `config.py`:
- Google Sheets credentials and spreadsheet ID
- Email IMAP settings
- Upload folder paths
- OCR settings

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is proprietary software for internal business operations.

## 🆘 Support

For support and questions, please contact the development team.

---

**Version**: 1.0.0 - Full Feature Release
**Last Updated**: December 2024
