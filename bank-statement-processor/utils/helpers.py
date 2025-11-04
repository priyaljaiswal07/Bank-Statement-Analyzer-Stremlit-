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
