"""
Utility functions for bank statement processing
"""

import pandas as pd
import re
from typing import Optional, Tuple
import os


def read_excel_file(file_path, **kwargs) -> pd.DataFrame:
    """
    Read Excel file (.xls or .xlsx) with automatic engine detection
    
    Args:
        file_path: Path to Excel file or file-like object
        **kwargs: Additional arguments to pass to pd.read_excel()
        
    Returns:
        pd.DataFrame: DataFrame containing the Excel data
    """
    # If it's a file-like object (like Streamlit upload), try to detect from name or just try both
    if hasattr(file_path, 'name'):
        file_name = file_path.name.lower()
        if file_name.endswith('.xls') and not file_name.endswith('.xlsx'):
            # Old format .xls file
            return pd.read_excel(file_path, engine='xlrd', **kwargs)
        else:
            # .xlsx or default to openpyxl
            return pd.read_excel(file_path, engine='openpyxl', **kwargs)
    elif isinstance(file_path, str):
        # String path
        file_name = file_path.lower()
        if file_name.endswith('.xls') and not file_name.endswith('.xlsx'):
            # Old format .xls file
            return pd.read_excel(file_path, engine='xlrd', **kwargs)
        else:
            # .xlsx or default to openpyxl
            return pd.read_excel(file_path, engine='openpyxl', **kwargs)
    else:
        # Try default (pandas will auto-detect)
        try:
            return pd.read_excel(file_path, **kwargs)
        except Exception:
            # If default fails, try with xlrd for .xls
            try:
                return pd.read_excel(file_path, engine='xlrd', **kwargs)
            except Exception:
                # Last resort: try openpyxl
                return pd.read_excel(file_path, engine='openpyxl', **kwargs)


def is_valid_party_name(name: str) -> bool:
    """
    Check if the name is a valid party name (not a bank code, reference number, etc.)
    
    Args:
        name: The name to validate
        
    Returns:
        bool: True if valid party name, False otherwise
    """
    if pd.isna(name) or name.strip() == "":
        return False
    
    name_upper = name.upper().strip()
    
    # Skip if it's transaction types
    if name_upper in ["MMT", "IMPS", "NEFT", "RTGS", "CMS", "TRF", "CLG", "INF", "INFT"]:
        return False
    
    # Skip if it's single letters or very short codes
    if len(name) <= 3:
        return False
    
    # Skip if it's all numbers
    if re.match(r'^\d+$', name):
        return False
    
    # Skip bank codes and reference numbers (patterns like YESB0NDCB01, SBIN0000646, BULD57)
    if (re.match(r'^[A-Z]{4}\d+$', name) or  # LIKE SBIN0000646
        re.match(r'^[A-Z]{3,4}\d+[A-Z]*\d*$', name) or  # LIKE YESB0NDCB01, BULD57
        re.match(r'^[A-Z]+\d+[A-Z]*$', name)):  # LIKE BULD57907180
        return False
    
    # Skip date-like patterns (17 JULY, 25 DEC, etc.)
    if re.match(r'^\d{1,2}\s+[A-Z]{3,9}\s*$', name, re.IGNORECASE):  # LIKE "17 JULY", "25 DECEMBER"
        return False
    
    # Skip month names alone
    months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 
             'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER', 'JAN', 'FEB', 
             'MAR', 'APR', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    if name_upper in months:
        return False
    
    # Skip common unwanted terms
    unwanted_terms = ["ATTN", "PAYMENT", "PAY", "F", "H", "HDFC", "ICICI", "SBI", "AXIS", "YES", "BANK", 
                     "BANQUE", "BULD", "BANK", "HDFC BANK", "KOTAK MAHINDRA BANK", "MAHINDRA BANK"]
    if name_upper in unwanted_terms:
        return False
    
    # Must contain alphabets and be of reasonable length
    if (re.search(r'[A-Za-z]', name) and len(name) >= 4):
        return True
    
    return False


def clean_party_name(name: str) -> str:
    """
    Clean up party name by removing unwanted patterns
    
    Args:
        name: The name to clean
        
    Returns:
        str: Cleaned party name
    """
    if pd.isna(name) or name.strip() == "":
        return ""
    
    cleaned = name.strip()
    
    # Remove trailing single letters
    cleaned = re.sub(r'\s+[A-Z]$', '', cleaned)
    cleaned = re.sub(r'/[A-Z]$', '', cleaned)
    
    # Remove trailing numbers
    cleaned = re.sub(r'\s*\d+$', '', cleaned)
    
    # Remove any bank codes or reference numbers anywhere in the string
    cleaned = re.sub(r'\b[A-Z]{3,4}\d+[A-Z]*\d*\b', '', cleaned)  # YESB0NDCB01, SBIN0000646
    cleaned = re.sub(r'\b[A-Z]+\d+[A-Z]*\b', '', cleaned)  # BULD57907180
    
    # Remove date patterns (17 JULY, 25 DEC, etc.)
    cleaned = re.sub(r'\b\d{1,2}\s+[A-Z]{3,9}\b', '', cleaned, flags=re.IGNORECASE)
    
    # Remove common bank names and unwanted terms
    bank_names = ['HDFC', 'ICICI', 'SBI', 'AXIS', 'YES', 'BANK', 'BANQUE', 
                 'ATTN', 'PAYMENT', 'PAY', 'BULD', 'KOTAK', 'MAHINDRA', 'HDFC BANK',
                 'KOTAK MAHINDRA BANK', 'MAHINDRA BANK']
    for bank in bank_names:
        cleaned = re.sub(r'\b' + bank + r'\b', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra spaces and special characters
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'^[/\s]+|[/\s]+$', '', cleaned)  # Remove leading/trailing slashes
    
    # Final check - if it's empty or too short after cleaning, return empty
    if (cleaned == "" or 
        len(cleaned) <= 3 or 
        cleaned.upper() in ["ATTN", "PAYMENT", "PAY", "F", "H", "BULD"] or
        not re.search(r'[A-Za-z]', cleaned) or
        # Final check for dates
        re.match(r'^\d{1,2}\s+[A-Z]{3,9}$', cleaned, re.IGNORECASE)):
        return ""
    
    return cleaned


def clean_amount(amount_str: str) -> str:
    """
    Clean amount string by removing commas and other non-numeric characters
    
    Args:
        amount_str: The amount string to clean
        
    Returns:
        str: Cleaned amount string
    """
    if pd.isna(amount_str) or amount_str.strip() == "":
        return "0"
    # Remove commas, spaces, and other non-numeric characters except decimal point
    cleaned = re.sub(r'[^\d.]', '', str(amount_str))
    return cleaned if cleaned else "0"


def format_date(date_str: str) -> str:
    """
    Format date string to DD/MM/YYYY format
    
    Args:
        date_str: The date string to format
        
    Returns:
        str: Formatted date string
    """
    if pd.isna(date_str) or str(date_str).strip() == "":
        return ""
    
    try:
        return pd.to_datetime(date_str, errors='coerce', dayfirst=True).strftime('%d/%m/%Y')
    except:
        return ""


def determine_debit_credit(withdrawal_amt: str, deposit_amt: str) -> str:
    """
    Determine if transaction is debit or credit based on amounts
    
    Args:
        withdrawal_amt: Withdrawal amount
        deposit_amt: Deposit amount
        
    Returns:
        str: "Debit", "Credit", or ""
    """
    withdrawal_clean = clean_amount(withdrawal_amt)
    deposit_clean = clean_amount(deposit_amt)
    
    if deposit_clean and deposit_clean not in ["", "0", "0.0"]:
        return "Credit"
    elif withdrawal_clean and withdrawal_clean not in ["", "0", "0.0"]:
        return "Debit"
    else:
        return ""


def determine_debit_credit_from_cr_dr(cr_dr: str) -> str:
    """
    Determine debit/credit from Cr/Dr column
    
    Args:
        cr_dr: Cr/Dr value
        
    Returns:
        str: "Debit", "Credit", or ""
    """
    if pd.isna(cr_dr):
        return ""
    
    cr_dr_clean = str(cr_dr).strip().upper()
    if cr_dr_clean == "CR":
        return "Credit"
    elif cr_dr_clean == "DR":
        return "Debit"
    else:
        return ""


def split_transaction_description(description: str) -> list:
    """
    Split transaction description into parts, handling various separators
    
    Args:
        description: Transaction description
        
    Returns:
        list: List of description parts
    """
    if pd.isna(description) or description.strip() == "":
        return []
    
    # Replace hyphens with slashes for uniformity
    cleaned = str(description).strip().replace("-", "/")
    cleaned = cleaned.replace(" /", "/").replace("/ ", "/")
    cleaned = re.sub(r"/+", "/", cleaned)
    
    return [part.strip() for part in cleaned.split('/') if part.strip()]


# ============================================================
# Remark Classification Functions
# ============================================================

def normalize_narration(description: str) -> str:
    """
    Normalize narration text for case-insensitive matching.
    Returns uppercase stripped string, or empty string if invalid.
    
    Args:
        description: Transaction description/narration
        
    Returns:
        str: Normalized uppercase string
    """
    if not isinstance(description, str) or not description.strip():
        return ""
    return description.upper().strip()


def extract_cheque_number_from_clg(description: str) -> str:
    """
    Extract cheque number from CLG entry.
    Format: CLG/<cheque_no>/<date>/... or CLG/118647/011125/...
    Returns cheque number padded to 6 digits with leading zeros.
    
    Args:
        description: Transaction description
        
    Returns:
        str: Cheque number padded to 6 digits, or empty string
    """
    if not isinstance(description, str) or not description.strip():
        return ""
    
    description_upper = description.upper().strip()
    
    # Check if it starts with CLG
    if not description_upper.startswith("CLG/"):
        return ""
    
    # Split by /
    parts = description_upper.split("/")
    if len(parts) < 2:
        return ""
    
    # Second part should be the cheque number
    cheque_num_str = parts[1].strip()
    
    # Extract only digits
    cheque_digits = re.sub(r'[^\d]', '', cheque_num_str)
    
    if not cheque_digits:
        return ""
    
    # Pad to 6 digits with leading zeros
    cheque_num_padded = cheque_digits.zfill(6)
    
    return cheque_num_padded


def extract_cheque_number_from_reject(description: str) -> str:
    """
    Extract cheque number from REJECT entry.
    Format: REJECT:18280 or BRN-OW RTN CLG: REJECT:18280:Other reasons
    Returns cheque number padded to 6 digits with leading zeros.
    
    Args:
        description: Transaction description
        
    Returns:
        str: Cheque number padded to 6 digits, or empty string
    """
    if not isinstance(description, str) or not description.strip():
        return ""
    
    description_upper = description.upper().strip()
    
    # Check if it contains REJECT
    if "REJECT" not in description_upper:
        return ""
    
    # Pattern: REJECT:18280 or REJECT:18244
    # Find REJECT: followed by digits
    match = re.search(r'REJECT[:\s]+(\d+)', description_upper)
    if match:
        cheque_digits = match.group(1)
        # Pad to 6 digits with leading zeros
        return cheque_digits.zfill(6)
    
    return ""


def classify_transaction_remark(
    description: str,
    payment_category: str = "",
    rejected_cheque_numbers: set = None
) -> str:
    """
    Classify transaction into Remark categories with STRICT PRIORITY ORDER:
    1. Cheque Reject (Highest Priority)
    2. Collections
    3. Expense
    4. Supplier Payment
    5. NA (Fallback)
    
    Rules must be applied in this exact order to avoid misclassification.
    
    Args:
        description: Transaction description/narration
        payment_category: Payment category (optional)
        rejected_cheque_numbers: Set of rejected cheque numbers (padded to 6 digits)
    
    Returns:
        str: Remark category (one of: 'Cheque Reject', 'Collections', 'Expense', 'Supplier Payment', 'NA')
    """
    # Normalize inputs
    description_upper = normalize_narration(description)
    payment_category_upper = normalize_narration(payment_category)
    
    if not description_upper:
        return "NA"
    
    # ============================================================
    # 1️⃣ CHEQUE REJECT (Highest Priority)
    # ============================================================
    
    # A. Direct keyword match: REJECT in narration or payment category
    if "REJECT" in description_upper or "REJECT" in payment_category_upper:
        return "Cheque Reject"
    
    # B. Cheque number mapping: Check if CLG cheque number matches rejected cheque
    if rejected_cheque_numbers:
        cheque_num = extract_cheque_number_from_clg(description_upper)
        if cheque_num and cheque_num in rejected_cheque_numbers:
            return "Cheque Reject"
    
    # ============================================================
    # 2️⃣ COLLECTIONS
    # ============================================================
    
    # Check if ANY Collections condition matches
    # A. Narration contains UPI
    if "UPI" in description_upper or "UPI" in payment_category_upper:
        return "Collections"
    
    # B. Narration starts with BY CASH
    if description_upper.startswith("BY CASH"):
        return "Collections"
    
    # C. Narration contains CAM and CASH DEP
    if description_upper.startswith("CAM/") and "CASH DEP" in description_upper:
        return "Collections"
    
    # D. Narration starts with CMS/
    if description_upper.startswith("CMS/"):
        return "Collections"
    
    # ============================================================
    # 3️⃣ EXPENSE
    # ============================================================
    
    # Check if ANY Expense condition matches
    # A. Narration contains GIB
    if "GIB" in description_upper:
        return "Expense"
    
    # B. Narration starts with ACH/
    if description_upper.startswith("ACH/"):
        return "Expense"
    
    # C. Narration contains BIL/ONL
    if "BIL/ONL" in description_upper or ("BIL" in description_upper and "ONL" in description_upper):
        return "Expense"
    
    # D. Narration starts with EZY/
    if description_upper.startswith("EZY/"):
        return "Expense"
    
    # E. Cheque return charges (not the rejected cheque itself, but charges)
    # Pattern: "Chq rtn Chg" or variations
    if (re.search(r"CHQ\s*RTN\s*CHG", description_upper) or
        re.search(r"CHQ\s*RETURN\s*CHG", description_upper) or
        re.search(r"CHEQUE\s*RETURN\s*CHG", description_upper)):
        return "Expense"
    
    # ============================================================
    # 4️⃣ SUPPLIER PAYMENT
    # ============================================================
    
    # This rule runs after Expense & Collections checks
    # A. DD/CC ISSUED pattern (clear supplier payment indicator)
    if "DD/CC ISSUED" in description_upper or "DD ISSUED" in description_upper:
        return "Supplier Payment"
    
    # B. Supplier/vendor/company name patterns
    # Look for company indicators (LIMITED, PVT LTD, PRIVATE LIMITED, etc.)
    supplier_keywords = ["DABUR", "LIMITED", "PVT LTD", "PRIVATE LIMITED"]
    if any(keyword in description_upper for keyword in supplier_keywords):
        # Additional validation: should not match Collections or Expense patterns
        # (already checked above, but double-check to be safe)
        if not (description_upper.startswith("CMS/") or 
                description_upper.startswith("CAM/") or
                description_upper.startswith("ACH/") or
                description_upper.startswith("EZY/") or
                "UPI" in description_upper or
                description_upper.startswith("BY CASH") or
                "GIB" in description_upper or
                "BIL/ONL" in description_upper):
            return "Supplier Payment"
    
    # ============================================================
    # 5️⃣ NA (Fallback)
    # ============================================================
    
    # If none of the above rules match, return NA
    return "NA"


def add_remark_column(df: pd.DataFrame, description_column: str, payment_category_column: str = "Payment Category") -> pd.DataFrame:
    """
    Add Remark column to DataFrame using strict rule-based classification.
    Implements cross-row cheque number matching (CLG ↔ REJECT).
    
    Args:
        df: DataFrame with transaction data
        description_column: Name of the column containing transaction descriptions
        payment_category_column: Name of the column containing payment categories
        
    Returns:
        pd.DataFrame: DataFrame with added Remark column
    """
    if description_column not in df.columns:
        # If description column not found, add NA for all rows
        df["Remark"] = "NA"
        return df
    
    # Step 1: Collect and match cheque numbers for Cheque Reject classification
    # This implements cross-row matching: CLG entries matching REJECT entries
    rejected_cheque_numbers = set()
    clg_cheque_numbers = {}  # Map cheque_number -> row_index for CLG entries
    
    # First pass: Collect CLG cheque numbers
    for i, val in enumerate(df[description_column].fillna("")):
        description = str(val)
        cheque_num = extract_cheque_number_from_clg(description)
        if cheque_num:
            clg_cheque_numbers[cheque_num] = i
    
    # Second pass: Collect REJECT cheque numbers and match with CLG
    for i, val in enumerate(df[description_column].fillna("")):
        description = str(val)
        cheque_num = extract_cheque_number_from_reject(description)
        if cheque_num:
            # Add REJECT cheque number to rejected set
            rejected_cheque_numbers.add(cheque_num)
            
            # Check if this REJECT number matches any CLG entry
            if cheque_num in clg_cheque_numbers:
                # Add CLG cheque number to rejected set (both should be marked as Cheque Reject)
                rejected_cheque_numbers.add(cheque_num)
    
    # Step 2: Classify transactions with Remark column (strict priority order)
    remarks = []
    for i, val in enumerate(df[description_column].fillna("")):
        description = str(val)
        payment_cat = str(df.at[i, payment_category_column]) if payment_category_column in df.columns else ""
        remark = classify_transaction_remark(description, payment_cat, rejected_cheque_numbers)
        remarks.append(remark)
    
    df["Remark"] = remarks
    return df
