"""
Jana Bank parser
"""

import pandas as pd
import re
from typing import Tuple, Dict
from parsers.base_parser import BaseBankParser
from config import JANA_COLUMN_PATTERNS, HEADER_ROWS, BANK_KEYWORDS
from utils import (
    is_valid_party_name, clean_party_name, clean_amount, 
    format_date, determine_debit_credit, split_transaction_description, read_excel_file,
    add_remark_column
)


class JanaParser(BaseBankParser):
    """Parser for Jana Bank statements"""
    
    def __init__(self):
        super().__init__("Jana Bank")
        self.header_row = HEADER_ROWS["Jana Bank"]
    
    def process_file(self, file_path: str) -> pd.DataFrame:
        """Process Jana Bank statement file"""
        try:
            # Read Excel file - data starts from row 28 (supports both .xls and .xlsx)
            df = read_excel_file(file_path, header=self.header_row, dtype=str)
            df = self.clean_dataframe(df)
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Map columns
            column_mapping = self._map_columns(df.columns)
            
            # Process data
            processed_data = []
            for idx, row in df.iterrows():
                if pd.isna(row.get(column_mapping.get('Description', ''))):
                    continue
                
                processed_row = self._process_row(row, column_mapping)
                if processed_row:
                    processed_data.append(processed_row)
            
            df = pd.DataFrame(processed_data)
            
            # Keep only essential columns
            essential_cols = [
                'S.N.', 'Transaction Date', 'Value Date', 'Description', 'Reference No',
                'Withdrawal Amt (INR)', 'Deposit Amt (INR)', 'Balance (INR)', 'Debit/Credit', 
                'Payment Category', 'Party Name1', 'Party Name2'
            ]
            df = df[[col for col in essential_cols if col in df.columns]]
            
            # Add Remark column using strict rule-based classification
            df = add_remark_column(df, "Description", "Payment Category")
            
            return df
            
        except Exception as e:
            raise Exception(f"Error processing Jana Bank statement: {e}")
    
    def parse_transaction_description(self, description: str) -> pd.Series:
        """Parse Jana Bank transaction description"""
        if pd.isna(description) or description.strip() == "":
            return pd.Series(["", "", ""])
        
        desc_clean = description.strip()
        payment_category = ""
        party1 = ""
        party2 = ""
        
        # NEFT Credit Transactions - Format: NEFT CR-BANKCODE-PARTYNAME1-PARTYNAME2-REFERENCE
        if 'NEFT CR' in desc_clean.upper() or (desc_clean.upper().startswith('NEFT') and 'CR' in desc_clean.upper()):
            payment_category = 'NEFT INCOMING'
            # Split by hyphen for NEFT CR transactions
            parts = desc_clean.split('-')
            if len(parts) >= 3:
                # Skip first part (NEFT CR) and second part (bank code), party names are usually in middle parts
                # Format: NEFT CR-BANKCODE-PARTYNAME1-PARTYNAME2-REFERENCE
                potential_parties = []
                for i in range(2, len(parts) - 1):  # Skip first 2 and last (which is usually reference)
                    part = parts[i].strip()
                    if part and is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                        potential_parties.append(part)
                
                # Take the first valid party name as primary
                if potential_parties:
                    party1 = potential_parties[0]
                    # If there's a second party name, use it, otherwise use the first one
                    party2 = potential_parties[1] if len(potential_parties) > 1 else potential_parties[0]
                else:
                    # Try combining parts if single parts don't work
                    for i in range(2, len(parts) - 1):
                        for j in range(i+1, min(len(parts) - 1, i+3)):
                            combined = ' '.join([p.strip() for p in parts[i:j+1]])
                            if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                party1 = combined
                                party2 = combined
                                break
                        if party1:
                            break
        
        # NEFT Debit Transactions
        elif 'NEFT DR' in desc_clean.upper() or (desc_clean.upper().startswith('NEFT') and 'DR' in desc_clean.upper()):
            payment_category = 'NEFT OUTGOING'
            # For NEFT DR transactions, format may vary, try to extract party name
            parts = desc_clean.split('-')
            for part in parts:
                part_clean = part.strip()
                if is_valid_party_name(part_clean) and not any(bank in part_clean.upper() for bank in BANK_KEYWORDS):
                    party1 = part_clean
                    party2 = part_clean
                    break
            
            # Try combining parts if single parts don't work
            if not party1 and len(parts) >= 2:
                for i in range(len(parts)):
                    for j in range(i+1, min(len(parts), i+3)):
                        combined = ' '.join([p.strip() for p in parts[i:j+1]])
                        if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
                            break
                    if party1:
                        break
        
        # IMPS Transactions - Format: IMPS REFERENCE PARTYNAME EXTRA INFO
        elif 'IMPS' in desc_clean.upper():
            payment_category = 'IMPS'
            # Split by spaces
            words = desc_clean.split()
            if len(words) >= 2:
                # Skip "IMPS" and reference number, party name should be after
                # Format: IMPS REFERENCE PARTYNAME ...
                start_idx = 1  # Skip "IMPS"
                # Check if second word is a reference number (mostly digits)
                if len(words) > 1 and re.match(r'^\d+$', words[1]):
                    start_idx = 2  # Skip "IMPS" and reference
                
                # Collect all potential name parts until we hit keywords or patterns like "9999-JFS-HO"
                potential_name_parts = []
                end_idx = len(words)
                for i in range(start_idx, len(words)):
                    word = words[i].upper()
                    # Stop at common transaction keywords
                    if word in ['PAYMENT', 'AGAINST', 'FOR', 'TO', 'FROM', 'REF', 'REFERENCE', 'ID']:
                        end_idx = i
                        break
                    # Stop at patterns like "9999-JFS-HO" (numbers followed by hyphen-separated codes)
                    if re.match(r'^\d+-', word):
                        end_idx = i
                        break
                    # Skip pure numbers, but keep words that might be part of party name
                    if word and not re.match(r'^\d+$', word) and len(word) >= 2:
                        potential_name_parts.append(words[i])  # Use original case
                    elif re.match(r'^\d+$', word) and len(word) >= 4:
                        # Skip long numbers that are likely references
                        continue
                
                if potential_name_parts:
                    # Try all combinations and pick the longest valid one
                    # This handles cases like "PRIDE ENTE PRIDE ENTERPRIS" by preferring longer matches
                    best_party_name = ""
                    best_length = 0
                    
                    # Try single words first
                    for word in potential_name_parts:
                        if is_valid_party_name(word) and not any(bank in word.upper() for bank in BANK_KEYWORDS):
                            if len(word) > best_length:
                                best_party_name = word
                                best_length = len(word)
                    
                    # Try all possible combinations (up to 6 words to handle long names like "PRIDE ENTERPRISES")
                    for i in range(len(potential_name_parts)):
                        for j in range(i+1, min(len(potential_name_parts), i+6)):
                            combined = ' '.join(potential_name_parts[i:j+1])
                            if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                combined_length = len(combined)
                                # Check for obvious duplicates/partial matches (e.g., "PRIDE ENTE PRIDE ENTERPRIS")
                                words_list = combined.upper().split()
                                has_duplicate = len(words_list) != len(set(words_list))
                                
                                # Prefer longer names, but heavily favor non-duplicates
                                # This helps prefer "PRIDE ENTERPRIS" over "PRIDE ENTE PRIDE ENTERPRIS"
                                score = combined_length
                                if not has_duplicate:
                                    # Heavier bonus for non-duplicates to prefer complete names over partial duplicates
                                    score += 20  # Significant bonus for non-duplicates
                                
                                if score > best_length:
                                    best_party_name = combined
                                    best_length = score
                    
                    if best_party_name:
                        party1 = best_party_name
                        party2 = best_party_name
        
        # RTGS Transactions
        elif 'RTGS' in desc_clean.upper():
            payment_category = 'RTGS'
            # Similar to IMPS format
            parts = split_transaction_description(desc_clean)
            for i in range(1, len(parts)):
                potential_party = parts[i]
                if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                    party1 = potential_party
                    party2 = potential_party
                    break
            
            # Try combining parts
            if not party1 and len(parts) >= 2:
                for i in range(1, min(len(parts), 5)):
                    for j in range(i+1, min(len(parts), i+3)):
                        combined = ' '.join(parts[i:j+1])
                        if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
                            break
                    if party1:
                        break
        
        # Internal transfers (jana ca to jana od)
        elif 'JANA CA TO JANA OD' in desc_clean.upper():
            if 'CR' in desc_clean.upper():  # Credit to OD account
                payment_category = 'INTERNAL TRANSFER CREDIT'
                # Extract company name from description
                # Format: "jana ca to jana od Cr - 4515020001253844 - AYEKART RETAIL PRIVATE LIMITED"
                parts = desc_clean.split('-')
                if len(parts) >= 3:
                    company_name = parts[-1].strip()
                    if is_valid_party_name(company_name) and not any(bank in company_name.upper() for bank in BANK_KEYWORDS):
                        party1 = company_name
                        party2 = company_name
                    else:
                        party1 = "INTERNAL TRANSFER"
                        party2 = "INTERNAL TRANSFER"
                else:
                    party1 = "INTERNAL TRANSFER"
                    party2 = "INTERNAL TRANSFER"
            else:  # Debit from OD account
                payment_category = 'INTERNAL TRANSFER DEBIT'
                party1 = "INTERNAL TRANSFER"
                party2 = "INTERNAL TRANSFER"
        
        # Cash transactions
        elif 'CASH' in desc_clean.upper():
            if 'DEPOSIT' in desc_clean.upper() or 'CR' in desc_clean.upper():
                payment_category = 'CASH DEPOSIT'
            else:
                payment_category = 'CASH WITHDRAWAL'
            party1 = ""
            party2 = ""
        
        # Cheque transactions
        elif 'CHQ' in desc_clean.upper() or 'CHEQUE' in desc_clean.upper():
            payment_category = 'CHEQUE'
            parts = split_transaction_description(desc_clean)
            for part in parts:
                if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                    party1 = part
                    party2 = part
                    break
            
            # Try combining parts
            if not party1 and len(parts) >= 2:
                for i in range(len(parts)):
                    for j in range(i+1, min(len(parts), i+3)):
                        combined = ' '.join(parts[i:j+1])
                        if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                            party1 = combined
                            party2 = combined
                            break
                    if party1:
                        break
        
        # Other transactions - Try to extract party name from date-bankcode-reference format
        # Format: 20251001 SBIN225274012699 RADNT
        else:
            payment_category = 'OTHER TRANSACTION'
            words = desc_clean.split()
            # Skip date patterns and bank codes, look for party name
            start_idx = 0
            for i, word in enumerate(words):
                # Skip date patterns (all digits like 20251001)
                if re.match(r'^\d{8}$', word):
                    continue
                # Skip bank codes (like SBIN225274012699)
                if re.match(r'^[A-Z]{3,4}\d+$', word.upper()):
                    continue
                # Found potential start of party name
                start_idx = i
                break
            
            # Extract party name from remaining words
            potential_name_parts = []
            for i in range(start_idx, len(words)):
                word = words[i]
                if word and not re.match(r'^\d+$', word) and len(word) >= 3:
                    potential_name_parts.append(word)
            
            # Try to find valid party name
            for word in potential_name_parts:
                if (is_valid_party_name(word) and 
                    word.upper() not in ['OTHER', 'TRANSACTION', 'PAYMENT', 'BANK'] and
                    not any(bank in word.upper() for bank in BANK_KEYWORDS)):
                    party1 = word
                    party2 = word
                    break
            
            # Try combining parts
            if not party1 and potential_name_parts:
                for i in range(len(potential_name_parts)):
                    for j in range(i+1, min(len(potential_name_parts), i+4)):
                        combined = ' '.join(potential_name_parts[i:j+1])
                        if (is_valid_party_name(combined) and 
                            combined.upper() not in ['OTHER', 'TRANSACTION', 'PAYMENT', 'BANK'] and
                            not any(bank in combined.upper() for bank in BANK_KEYWORDS)):
                            party1 = combined
                            party2 = combined
                            break
                    if party1:
                        break
        
        # Clean party names
        party1 = clean_party_name(party1)
        party2 = clean_party_name(party2)
        
        return pd.Series([payment_category, party1, party2])
    
    def _map_columns(self, columns: list) -> Dict[str, str]:
        """Map column names to standard names"""
        column_mapping = {}
        
        for col in columns:
            col_lower = str(col).lower()
            for standard_name, patterns in JANA_COLUMN_PATTERNS.items():
                if any(pattern in col_lower for pattern in patterns):
                    column_mapping[standard_name] = col
                    break
        
        return column_mapping
    
    def _process_row(self, row: pd.Series, column_mapping: Dict[str, str]) -> Dict:
        """Process a single row of data"""
        # Extract and format dates
        transaction_date = ""
        value_date = ""
        
        if 'Transaction Date' in column_mapping:
            txn_date_str = str(row.get(column_mapping['Transaction Date'], '')).strip()
            transaction_date = format_date(txn_date_str)
        
        if 'Value Date' in column_mapping:
            val_date_str = str(row.get(column_mapping['Value Date'], '')).strip()
            value_date = format_date(val_date_str)
        
        # Extract description
        description = str(row.get(column_mapping.get('Description', ''))).strip()
        
        # Extract amount and clean it
        amount_str = str(row.get(column_mapping.get('Transaction Amount', ''))).strip()
        amount = clean_amount(amount_str)
        
        # Determine debit/credit based on Dr/Cr column
        dr_cr_col = str(row.get(column_mapping.get('Dr/Cr', ''))).strip().upper()
        if dr_cr_col == 'C':
            debit_credit = 'Credit'
            withdrawal_amt = '0'
            deposit_amt = str(amount)
        elif dr_cr_col == 'D':
            debit_credit = 'Debit'
            withdrawal_amt = str(amount)
            deposit_amt = '0'
        else:
            debit_credit = ''
            withdrawal_amt = '0'
            deposit_amt = '0'
        
        # Extract balance and clean it
        balance_str = str(row.get(column_mapping.get('Balance', ''))).strip()
        balance = clean_amount(balance_str)
        
        # Parse payment category and party names from description
        payment_category, party1, party2 = self.parse_transaction_description(description)
        
        # Validate cash transactions based on debit/credit
        # Credit + Cash = CASH DEPOSIT, Debit + Cash = CASH WITHDRAWAL
        if 'CASH' in payment_category.upper():
            if debit_credit == 'Credit':
                payment_category = 'CASH DEPOSIT'
            elif debit_credit == 'Debit':
                payment_category = 'CASH WITHDRAWAL'
        
        # Get reference number
        ref_no = str(row.get(column_mapping.get('Reference No', ''))).strip()
        
        return {
            'S.N.': str(row.get(column_mapping.get('S.N.', ''))),
            'Transaction Date': transaction_date,
            'Value Date': value_date,
            'Description': description,
            'Reference No': ref_no,
            'Withdrawal Amt (INR)': withdrawal_amt,
            'Deposit Amt (INR)': deposit_amt,
            'Balance (INR)': str(balance),
            'Debit/Credit': debit_credit,
            'Payment Category': payment_category,
            'Party Name1': party1,
            'Party Name2': party2
        }
