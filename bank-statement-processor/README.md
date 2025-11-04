# Bank Statement Processor

A well-structured, modular bank statement processor that extracts and cleans transaction data from various bank formats.

## 🏦 Supported Banks

- **ICICI Bank** (Yearly & Monthly formats)
- **AXIS Bank**
- **Jana Bank**
- **RBL Bank**

## ✨ Features

- 🔍 **Smart Party Name Extraction** - Automatically identifies and cleans party names
- 📊 **Payment Category Classification** - Categorizes transactions (NEFT, RTGS, IMPS, etc.)
- 🧹 **Data Cleaning** - Removes bank codes, reference numbers, and unwanted terms
- 📈 **Transaction Analysis** - Shows summary statistics and distributions
- 💾 **Multiple Export Formats** - Download as Excel or CSV
- 🎨 **Modern UI** - Clean, intuitive Streamlit interface

## 🚀 Quick Start

### Installation

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## 📁 Project Structure

```
bank-statement-processor/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── config/               # Configuration files
│   ├── __init__.py
│   └── constants.py      # All constants and mappings
├── parsers/              # Bank-specific parsers
│   ├── __init__.py
│   ├── base_parser.py    # Base parser class
│   ├── icici_parser.py  # ICICI Bank parser
│   ├── axis_parser.py   # AXIS Bank parser
│   ├── jana_parser.py   # Jana Bank parser
│   └── rbl_parser.py    # RBL Bank parser
├── utils/                # Utility functions
│   ├── __init__.py
│   └── helpers.py        # Common helper functions
└── tests/                # Test files (future)
```

## 🔧 Architecture

### Modular Design

- **Base Parser**: Abstract base class defining common interface
- **Bank-Specific Parsers**: Implement parsing logic for each bank
- **Utility Functions**: Reusable helper functions
- **Configuration**: Centralized constants and mappings

### Key Components

1. **ICICIParser**: Handles both yearly and monthly ICICI formats
2. **AXISParser**: Processes AXIS Bank statements
3. **JanaParser**: Processes Jana Bank statements
4. **RBLParser**: Processes RBL Bank statements
5. **Helper Functions**: Data cleaning, validation, and formatting
6. **Configuration**: Bank keywords, column mappings, and constants

## 📊 Usage

1. **Select Bank**: Choose your bank from the dropdown
2. **Upload File**: Upload your Excel bank statement
3. **Review Data**: Check the processed results
4. **Download**: Export the cleaned data

## 🛠️ Development

### Adding New Banks

1. Create a new parser class inheriting from `BaseBankParser`
2. Implement required methods: `process_file()` and `parse_transaction_description()`
3. Add bank configuration to `config/constants.py`
4. Update the main app to include the new parser

### Testing

```bash
# Run tests (when implemented)
python -m pytest tests/
```

## 📝 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

If you encounter any issues or have questions, please open an issue on GitHub.
