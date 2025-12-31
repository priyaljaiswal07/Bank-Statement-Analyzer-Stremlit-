"""
RBL Bank parser
"""

import pandas as pd
import re
from typing import Tuple, Dict
from parsers.base_parser import BaseBankParser
from config import RBL_COLUMN_PATTERNS, HEADER_ROWS, BANK_KEYWORDS
from utils import (
    is_valid_party_name, clean_party_name, clean_amount, 
    format_date, determine_debit_credit, split_transaction_description, read_excel_file,
    add_remark_column
)


class RBLParser(BaseBankParser):
    """Parser for RBL Bank statements"""
    
    def __init__(self):
        super().__init__("RBL Bank")
        self.header_row = HEADER_ROWS["RBL Bank"]
    
    def process_file(self, file_path) -> pd.DataFrame:
        """Process RBL Bank statement file"""
        try:
            # First, try to find the header row by reading a few rows
            # Read more rows to find the header
            df_temp = read_excel_file(file_path, header=None, nrows=35, dtype=str)
            
            # Look for the row that contains column headers
            header_row_idx = None
            header_keywords = ['transaction date', 'transaction details', 'cheque', 'value date', 'withdrawl', 'deposit', 'balance']
            
            for idx in range(min(35, len(df_temp))):
                row_values = [str(val).lower().strip() for val in df_temp.iloc[idx].values if pd.notna(val)]
                # Check if this row contains header keywords
                matches = sum(1 for keyword in header_keywords if any(keyword in val for val in row_values))
                if matches >= 3:  # Found at least 3 header keywords
                    header_row_idx = idx
                    break
            
            # If header row found, use it; otherwise use the configured header row
            if header_row_idx is not None:
                actual_header_row = header_row_idx
            else:
                actual_header_row = self.header_row
            
            # Read Excel file with the correct header row
            df = read_excel_file(file_path, header=actual_header_row, dtype=str)
            df = self.clean_dataframe(df)
            
            # Check if dataframe is empty
            if df.empty:
                raise ValueError(f"Empty dataframe after reading file. Please check if header row {actual_header_row} is correct.")
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Map columns
            column_mapping = self._map_columns(df.columns)
            
            # Check if essential columns are found
            required_columns = ['Transaction Details', 'Transaction Date']
            missing_columns = [col for col in required_columns if col not in column_mapping]
            
            if missing_columns:
                # Try reading without header and manually setting columns
                df_no_header = read_excel_file(file_path, header=None, skiprows=actual_header_row, dtype=str)
                df_no_header = self.clean_dataframe(df_no_header)
                
                # Try to find header row in the skipped data
                if actual_header_row > 0:
                    header_df = read_excel_file(file_path, header=None, nrows=actual_header_row+1, dtype=str)
                    for idx in range(actual_header_row, -1, -1):
                        if idx < len(header_df):
                            row_values = [str(val).lower().strip() for val in header_df.iloc[idx].values if pd.notna(val)]
                            matches = sum(1 for keyword in header_keywords if any(keyword in val for val in row_values))
                            if matches >= 3:
                                # Set column names from this row
                                if len(header_df.iloc[idx]) >= len(df_no_header.columns):
                                    df_no_header.columns = [str(val).strip() for val in header_df.iloc[idx].values[:len(df_no_header.columns)]]
                                    df = df_no_header
                                    df.columns = [str(col).strip() for col in df.columns]
                                    column_mapping = self._map_columns(df.columns)
                                    missing_columns = [col for col in required_columns if col not in column_mapping]
                                    if not missing_columns:
                                        break
                
                if missing_columns:
                    raise ValueError(
                        f"Required columns not found: {missing_columns}. "
                        f"Available columns: {list(df.columns)}. "
                        f"Please check if this is an RBL Bank statement file."
                    )
            
            # Process data
            processed_data = []
            serial_number = 1
            for idx, row in df.iterrows():
                # Check if Transaction Details exists and is not empty
                txn_details_col = column_mapping.get('Transaction Details')
                if not txn_details_col or pd.isna(row.get(txn_details_col)) or str(row.get(txn_details_col)).strip() == "":
                    continue
                
                processed_row = self._process_row(serial_number, row, column_mapping)
                if processed_row:
                    processed_data.append(processed_row)
                    serial_number += 1
            
            if not processed_data:
                raise ValueError(
                    f"No transaction data found. Please check if the file contains transaction rows. "
                    f"Found columns: {list(df.columns)}"
                )
            
            df = pd.DataFrame(processed_data)
            
            # Keep only essential columns
            essential_cols = [
                'S.N.', 'Transaction Date', 'Value Date', 'Transaction Details',
                'Withdrawal Amt (INR)', 'Deposit Amt (INR)', 'Balance (INR)', 'Debit/Credit', 
                'Payment Category', 'Party Name1', 'Party Name2'
            ]
            df = df[[col for col in essential_cols if col in df.columns]]
            
            # Add Remark column using strict rule-based classification
            df = add_remark_column(df, "Transaction Details", "Payment Category")
            
            return df
            
        except Exception as e:
            raise Exception(f"Error processing RBL Bank statement: {e}")
    
    def parse_transaction_description(self, transaction_details: str) -> pd.Series:
        """Parse RBL Bank transaction details"""
        if pd.isna(transaction_details) or transaction_details.strip() == "":
            return pd.Series(["", "", ""])
        
        details_clean = transaction_details.strip()
        payment_category = ""
        party1 = ""
        party2 = ""
        
        # Handle IMPS transactions that don't use "/" separator (e.g., "IMPS 529010219903 FROM SCOOTSY LOGISTICS PVT")
        # Check this FIRST before splitting by "/"
        if 'IMPS' in details_clean.upper() and '/' not in details_clean:
            payment_category = 'IMPS'
            # Split by spaces for IMPS transactions without "/"
            words = details_clean.split()
            
            # Find "FROM" keyword and extract party name after it
            from_idx = -1
            for i, word in enumerate(words):
                if word.upper() == 'FROM' and i < len(words) - 1:
                    from_idx = i + 1
                    break
            
            if from_idx > 0:
                # Extract ALL party name words starting from "FROM" - don't break early
                # Collect all words after "FROM" to get the complete company name
                party_parts = []
                for i in range(from_idx, len(words)):
                    word = words[i]
                    # Skip reference numbers (all digits) and common transaction keywords
                    if not re.match(r'^\d+$', word) and word.upper() not in ['TO', 'BY', 'VIA', 'FOR', 'PAYMENT']:
                        party_parts.append(word)
                
                # Use the complete party name if we collected parts
                if party_parts:
                    combined = ' '.join(party_parts)
                    # More lenient check - just ensure it has letters and reasonable length
                    if len(combined) >= 4 and any(c.isalpha() for c in combined):
                        # Check if it's not just a bank keyword
                        combined_upper = combined.upper()
                        if not any(bank in combined_upper for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
            else:
                # No "FROM" keyword, try to extract from words after IMPS and reference number
                start_idx = 1  # Skip "IMPS"
                # Check if second word is a reference number (all digits)
                if len(words) > 1 and re.match(r'^\d+$', words[1]):
                    start_idx = 2  # Skip "IMPS" and reference
                
                # Collect potential party name parts
                party_parts = []
                for i in range(start_idx, len(words)):
                    word = words[i]
                    # Skip common keywords and reference numbers
                    if word.upper() not in ['FROM', 'TO', 'BY', 'VIA'] and not re.match(r'^\d+$', word):
                        party_parts.append(word)
                        # Try validating as we build
                        combined = ' '.join(party_parts)
                        if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
                            break
                
                # If we collected parts but didn't validate with strict check, use them anyway if reasonable
                if not party1 and party_parts:
                    combined = ' '.join(party_parts)
                    # More lenient check - just ensure it has letters and reasonable length
                    if len(combined) >= 4 and any(c.isalpha() for c in combined):
                        # Check if it's not just a bank keyword
                        combined_upper = combined.upper()
                        if not any(bank in combined_upper for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
            
            # Final fallback
            if not party1:
                party1 = "IMPS TRANSFER"
                party2 = "IMPS TRANSFER"
        
        # For other transactions, split by "/" and process
        else:
            parts = split_transaction_description(details_clean)
            
            # CMS/RTGS Transactions - Handle both CMS/RTGS and CMS/RTGSKIYA cases
            if len(parts) >= 1:
                first_part = parts[0].upper()
            
            # Check for CMS/RTGS pattern (could be CMS followed by RTGS, or CMS/RTGSKIYA...)
            if first_part == 'CMS' and len(parts) >= 2:
                second_part = parts[1].upper()
                
                if second_part == 'RTGS':
                    payment_category = 'RTGS'
                    # Format: CMS/RTGS/PARTY_NAME/BANK/REFERENCE
                    if len(parts) >= 3:
                        potential_party = parts[2]
                        if is_valid_party_name(potential_party):
                            party1 = potential_party
                            party2 = potential_party
                        else:
                            # Try to find valid party name in other parts
                            for i in range(2, len(parts)):
                                if is_valid_party_name(parts[i]):
                                    party1 = parts[i]
                                    party2 = parts[i]
                                    break
                    if not party1:
                        party1 = "RTGS TRANSFER"
                        party2 = "RTGS TRANSFER"
                elif second_part.startswith('RTGS'):
                    # Handle case like CMS/RTGSKIYA ENTERPRISES/...
                    payment_category = 'RTGS'
                    # Second part contains RTGS prefix, try to extract party name from it or next parts
                    potential_party = parts[1][4:] if len(parts[1]) > 4 else ""  # Remove "RTGS" prefix
                    if potential_party and is_valid_party_name(potential_party):
                        party1 = potential_party.strip()
                        party2 = potential_party.strip()
                    else:
                        # Try next parts
                        for i in range(1, len(parts)):
                            if is_valid_party_name(parts[i]):
                                party1 = parts[i]
                                party2 = parts[i]
                                break
                    if not party1:
                        party1 = "RTGS TRANSFER"
                        party2 = "RTGS TRANSFER"
                else:
                    # Regular CMS transaction
                    payment_category = 'CMS'
                    if len(parts) >= 2:
                        potential_party = parts[1]
                        if is_valid_party_name(potential_party):
                            party1 = potential_party
                            party2 = potential_party
                        else:
                            party1 = "CMS TRANSACTION"
                            party2 = "CMS TRANSACTION"
            
            # RTGS Transactions (standalone RTGS, not CMS/RTGS)
            elif first_part == 'RTGS':
                payment_category = 'RTGS'
                # Format: RTGS/BANKCODE/REFERENCE/PARTY_NAME or RTGS/PARTY_NAME/BANK/REFERENCE
                # Try to find party name starting from index 1
                for i in range(1, len(parts)):
                    potential_party = parts[i]
                    if is_valid_party_name(potential_party):
                        party1 = potential_party
                        party2 = potential_party
                        break
                if not party1:
                    party1 = "RTGS TRANSFER"
                    party2 = "RTGS TRANSFER"
            
            # NEFT Transactions
            elif first_part == 'NEFT':
                payment_category = 'NEFT'
                # Try to find party name starting from index 1
                for i in range(1, len(parts)):
                    potential_party = parts[i]
                    if is_valid_party_name(potential_party):
                        party1 = potential_party
                        party2 = potential_party
                        break
                if not party1:
                    party1 = "NEFT TRANSFER"
                    party2 = "NEFT TRANSFER"
            
            # IMPS Transactions
            elif first_part == 'IMPS':
                payment_category = 'IMPS'
                # Try to find party name in the parts
                for i in range(1, len(parts)):
                    potential_party = parts[i]
                    if is_valid_party_name(potential_party):
                        party1 = potential_party
                        party2 = potential_party
                        break
                if not party1:
                    party1 = "IMPS TRANSFER"
                    party2 = "IMPS TRANSFER"
            
            # Cash transactions
            elif 'CASH' in details_clean.upper():
                if 'DEPOSIT' in details_clean.upper():
                    payment_category = 'CASH DEPOSIT'
                else:
                    payment_category = 'CASH WITHDRAWAL'
                party1 = "CASH TRANSACTION"
                party2 = "CASH TRANSACTION"
            
            # Cheque transactions
            elif 'CHQ' in details_clean.upper() or 'CHEQUE' in details_clean.upper():
                payment_category = 'CHEQUE'
                party1 = "CHEQUE TRANSACTION"
                party2 = "CHEQUE TRANSACTION"
            
            else:
                # Default category - try to extract party name from the entire string
                payment_category = 'OTHER TRANSACTION'
                words = details_clean.split()
                for word in words:
                    if is_valid_party_name(word):
                        party1 = word
                        party2 = word
                        break
                if not party1:
                    party1 = "OTHER"
                    party2 = "OTHER"
        
        # Clean party names - but be careful not to remove valid company suffixes like "PVT", "LTD", etc.
        # Only clean if we have a valid party name to avoid losing information
        if party1 and party1 != "IMPS TRANSFER" and party1 != "NEFT TRANSFER" and party1 != "RTGS TRANSFER" and party1 != "CMS TRANSACTION":
            # For IMPS transactions with "FROM" keyword, preserve the full name including suffixes
            if payment_category == 'IMPS' and 'FROM' in details_clean.upper():
                # Only do light cleaning - remove extra spaces and special chars, but keep company suffixes
                party1 = party1.strip()
                party2 = party2.strip()
                # Remove extra spaces
                party1 = re.sub(r'\s+', ' ', party1).strip()
                party2 = re.sub(r'\s+', ' ', party2).strip()
            else:
                # For other transactions, use standard cleaning
                party1 = clean_party_name(party1)
                party2 = clean_party_name(party2)
        else:
            # For fallback names, use standard cleaning
            party1 = clean_party_name(party1)
            party2 = clean_party_name(party2)
        
        return pd.Series([payment_category, party1, party2])
    
    def _map_columns(self, columns: list) -> Dict[str, str]:
        """Map column names to standard names"""
        column_mapping = {}
        
        for col in columns:
            col_lower = str(col).lower().strip()
            
            # More flexible matching for each column type
            if not column_mapping.get('S.N.') and any(pattern in col_lower for pattern in ['s.no', 'sno', 'sl', 'sl.', 'serial']):
                column_mapping['S.N.'] = col
            
            if not column_mapping.get('Transaction Date') and any(pattern in col_lower for pattern in ['transaction date', 'trans date', 'date', 'txn date']):
                column_mapping['Transaction Date'] = col
            
            if not column_mapping.get('Value Date') and any(pattern in col_lower for pattern in ['value date', 'val date']):
                column_mapping['Value Date'] = col
            
            if not column_mapping.get('Transaction Details') and any(pattern in col_lower for pattern in ['transaction details', 'transaction detail', 'particulars', 'description', 'narration', 'details']):
                column_mapping['Transaction Details'] = col
            
            if not column_mapping.get('Withdrawal Amt') and any(pattern in col_lower for pattern in ['withdrawl', 'withdrawal', 'debit', 'dr', 'withdraw']):
                column_mapping['Withdrawal Amt'] = col
            
            if not column_mapping.get('Deposit Amt') and any(pattern in col_lower for pattern in ['deposit', 'credit', 'cr']):
                column_mapping['Deposit Amt'] = col
            
            if not column_mapping.get('Balance') and any(pattern in col_lower for pattern in ['balance', 'bal', 'running balance', 'closing balance']):
                column_mapping['Balance'] = col
        
        return column_mapping
    
    def _process_row(self, serial_number: int, row: pd.Series, column_mapping: Dict[str, str]) -> Dict:
        """Process a single row of data"""
        # Extract and format dates
        transaction_date = ""
        value_date = ""
        
        if 'Transaction Date' in column_mapping:
            txn_date_str = str(row.get(column_mapping['Transaction Date'], '')).strip()
            transaction_date = format_date(txn_date_str)
        else:
            # Try to find date in any column if Transaction Date mapping not found
            for col in row.index:
                if 'date' in str(col).lower():
                    txn_date_str = str(row.get(col, '')).strip()
                    transaction_date = format_date(txn_date_str)
                    if transaction_date:
                        break
        
        if 'Value Date' in column_mapping:
            val_date_str = str(row.get(column_mapping['Value Date'], '')).strip()
            value_date = format_date(val_date_str)
        
        # Skip if no transaction date
        if not transaction_date:
            return None
        
        # Extract transaction details - this is required
        txn_details_col = column_mapping.get('Transaction Details', '')
        if not txn_details_col:
            return None
        
        transaction_details = str(row.get(txn_details_col, '')).strip()
        if not transaction_details or transaction_details.lower() in ['nan', 'none', '']:
            return None
        
        # Extract amounts and determine debit/credit
        withdrawal_str = ""
        deposit_str = ""
        
        if 'Withdrawal Amt' in column_mapping:
            withdrawal_str = str(row.get(column_mapping['Withdrawal Amt'], '')).strip()
        else:
            # Try to find withdrawal/debit column
            for col in row.index:
                col_lower = str(col).lower()
                if any(term in col_lower for term in ['withdraw', 'debit', 'dr']):
                    withdrawal_str = str(row.get(col, '')).strip()
                    break
        
        if 'Deposit Amt' in column_mapping:
            deposit_str = str(row.get(column_mapping['Deposit Amt'], '')).strip()
        else:
            # Try to find deposit/credit column
            for col in row.index:
                col_lower = str(col).lower()
                if any(term in col_lower for term in ['deposit', 'credit', 'cr']):
                    deposit_str = str(row.get(col, '')).strip()
                    break
        
        withdrawal_amt = clean_amount(withdrawal_str)
        deposit_amt = clean_amount(deposit_str)
        
        # Determine debit/credit based on withdrawal/deposit amounts
        debit_credit = determine_debit_credit(withdrawal_amt, deposit_amt)
        
        # Extract balance and clean it
        balance_str = ""
        if 'Balance' in column_mapping:
            balance_str = str(row.get(column_mapping['Balance'], '')).strip()
        else:
            # Try to find balance column
            for col in row.index:
                col_lower = str(col).lower()
                if 'balance' in col_lower or 'bal' in col_lower:
                    balance_str = str(row.get(col, '')).strip()
                    break
        
        balance = clean_amount(balance_str)
        
        # Parse payment category and party names from transaction details
        payment_category, party1, party2 = self.parse_transaction_description(transaction_details)
        
        # Validate cash transactions based on debit/credit
        # Credit + Cash = CASH DEPOSIT, Debit + Cash = CASH WITHDRAWAL
        if 'CASH' in payment_category.upper():
            if debit_credit == 'Credit':
                payment_category = 'CASH DEPOSIT'
            elif debit_credit == 'Debit':
                payment_category = 'CASH WITHDRAWAL'
        
        return {
            'S.N.': str(serial_number),
            'Transaction Date': transaction_date,
            'Value Date': value_date if value_date else transaction_date,  # Use transaction date as fallback
            'Transaction Details': transaction_details,
            'Withdrawal Amt (INR)': withdrawal_amt,
            'Deposit Amt (INR)': deposit_amt,
            'Balance (INR)': str(balance) if balance else "0",
            'Debit/Credit': debit_credit,
            'Payment Category': payment_category,
            'Party Name1': party1,
            'Party Name2': party2
        }

