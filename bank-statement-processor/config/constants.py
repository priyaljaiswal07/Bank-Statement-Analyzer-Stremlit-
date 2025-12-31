"""
Configuration constants for bank statement processor
"""

# Bank-specific header row configurations
HEADER_ROWS = {
    "ICICI Yearly": 14,
    "ICICI Monthly": 14,
    "AXIS": 20,
    "Jana Bank": 27,
    "RBL Bank": 29
}

# Bank keywords to filter out from party names
BANK_KEYWORDS = [
    'ICICI', 'AXIS', 'CANARA', 'SBI', 'HDFC', 'YES', 'BANK',
    'INDIAN', 'PUNJAB NAT', 'BANDHAN BA', 'BARODA', 'BARODA U.P', 'KOTAK',
    'JAMMU', 'JAMMU AND', 'JAMMU &', 'UNION', 'UCOBANK', 'BANKOFBA'
]

# Transaction types to filter out
TRANSACTION_TYPES = ["MMT", "IMPS", "NEFT", "RTGS", "CMS", "TRF", "CLG", "INF", "INFT"]

# Unwanted terms to filter out from party names
UNWANTED_TERMS = [
    "ATTN", "PAYMENT", "PAY", "F", "H", "HDFC", "ICICI", "SBI", "AXIS", "YES", "BANK", 
    "BANQUE", "BULD", "BANK", "HDFC BANK", "KOTAK MAHINDRA BANK", "MAHINDRA BANK"
]

# Month names to filter out
MONTHS = [
    'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 
    'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER', 'JAN', 'FEB', 
    'MAR', 'APR', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'
]

# Payment category mappings
PAYMENT_CATEGORY_MAP = {
    "CLG": "CHEQUE CLEARING",
    "CASH": "CASH DEPOSIT",
    "INF": "INF TRANSACTION",
    "INFT": "INF TRANSACTION",
    "TRF": "TRANSFER",
    "MMT": "MOBILE MONEY TRANSFER",
    "NEFT": "NEFT",
    "RTGS": "RTGS",
    "IMPS": "IMPS",
    "IFT": "INSTANT FUND TRANSFER",
    "INB/IFT": "INSTANT FUND TRANSFER",
    "INB/RTGS": "RTGS"
}

# ICICI Yearly column names
ICICI_YEARLY_COLUMNS = [
    "S.N.",
    "Tran. Id",
    "Value Date",
    "Transaction Date",
    "Transaction Posted Date and time",
    "Cheque. No./Ref. No.",
    "Transaction Remarks",
    "Withdrawal Amt (INR)",
    "Deposit Amt (INR)",
    "Balance (INR)"
]

# ICICI Monthly column names
ICICI_MONTHLY_COLUMNS = [
    "No.",
    "Transaction ID", 
    "Value Date",
    "Txn Posted Date",
    "ChequeNo.",
    "Description",
    "Cr/Dr",
    "Transaction Amount(INR)", 
    "Available Balance(INR)"
]

# AXIS column mapping patterns
AXIS_COLUMN_PATTERNS = {
    'S.N.': ['s.no', 'sno'],
    'Transaction Date': ['transaction', 'date'],
    'Particulars': ['particular'],
    'Amount(INR)': ['amount'],
    'Debit/Credit': ['debit/cred', 'debit/credit'],
    'Balance(INR)': ['balance']
}

# Jana Bank column mapping patterns
JANA_COLUMN_PATTERNS = {
    'S.N.': ['s.no', 'sno'],
    'Transaction Date': ['transaction date'],
    'Value Date': ['value date'],
    'Description': ['description'],
    'Reference No': ['reference'],
    'Dr/Cr': ['dr/cr'],
    'Transaction Amount': ['transaction amount'],
    'Balance': ['running balance']
}

# RBL Bank column mapping patterns
RBL_COLUMN_PATTERNS = {
    'S.N.': ['s.no', 'sno'],
    'Transaction Date': ['transaction date'],
    'Value Date': ['value date'],
    'Transaction Details': ['transaction details'],
    'Cheque ID': ['cheque id', 'cheque'],
    'Withdrawal Amt': ['withdrawl', 'withdrawal'],
    'Deposit Amt': ['deposit'],
    'Balance': ['balance']
}

# Supported banks
SUPPORTED_BANKS = ["ICICI Yearly", "ICICI Monthly", "AXIS", "Jana Bank", "RBL Bank"]

# File types
SUPPORTED_FILE_TYPES = ["xlsx", "xls"]
