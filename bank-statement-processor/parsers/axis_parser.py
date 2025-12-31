"""
AXIS Bank parser
"""

import pandas as pd
import re
from typing import Tuple, Dict
from parsers.base_parser import BaseBankParser
from config import AXIS_COLUMN_PATTERNS, HEADER_ROWS, BANK_KEYWORDS
from utils import (
    is_valid_party_name, clean_party_name, clean_amount, 
    format_date, determine_debit_credit, split_transaction_description, read_excel_file,
    add_remark_column
)



class AXISParser(BaseBankParser):
    """Parser for AXIS Bank statements"""
    
    def __init__(self):
        super().__init__("AXIS")
        self.header_row = HEADER_ROWS["AXIS"]
    
    def process_file(self, file_path: str) -> pd.DataFrame:
        """Process AXIS bank statement file"""
        try:
            # Read Excel file (supports both .xls and .xlsx)
            # Header is at row 20 (1-indexed), data starts at row 22 (1-indexed)
            # Convert to 0-indexed: header at row 19, data starts at row 21
            # Row 21 (0-indexed) is empty, so we'll drop it after reading
            header_row_0_indexed = self.header_row - 1  # Row 20 (1-indexed) = Row 19 (0-indexed)
            df = read_excel_file(file_path, header=header_row_0_indexed, dtype=str)
            # Drop the first row (row 21, which is empty) so data starts from row 22
            if not df.empty:
                df = df.iloc[1:].reset_index(drop=True)
            df = self.clean_dataframe(df)
            
            # Check if dataframe is empty after reading
            if df.empty:
                # Try reading without header to find the correct header row
                df_temp = read_excel_file(file_path, header=None, nrows=30, dtype=str)
                # Look for header row by checking for column keywords
                header_keywords = ['particular', 'transaction', 'date', 'amount', 'debit', 'credit', 'balance']
                for idx in range(min(30, len(df_temp))):
                    row_values = [str(val).lower().strip() for val in df_temp.iloc[idx].values if pd.notna(val)]
                    matches = sum(1 for keyword in header_keywords if any(keyword in val for val in row_values))
                    if matches >= 3:  # Found at least 3 header keywords
                        # Try reading with this header row
                        df = read_excel_file(file_path, header=idx, dtype=str)
                        df = self.clean_dataframe(df)
                        break
                
                if df.empty:
                    raise ValueError("Could not find data in the file. Please check if this is a valid AXIS Bank statement.")
            
            # Remove rows with "OPENING BALANCE"
            df = df[~df.astype(str).apply(
                lambda x: x.str.contains('OPENING BALANCE', case=False, na=False)
            ).any(axis=1)]
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Map columns
            column_mapping = self._map_columns(df.columns)
            
            # Validate required columns are found
            required_columns = ['Particulars', 'Transaction Date']
            missing_columns = [col for col in required_columns if col not in column_mapping]
            if missing_columns:
                available_cols = list(df.columns)
                raise ValueError(
                    f"Required columns not found: {missing_columns}. "
                    f"Available columns: {available_cols}. "
                    f"Please check if this is an AXIS Bank statement file."
                )
            
            # Process data
            processed_data = []
            for idx, row in df.iterrows():
                # Check if Particulars column exists and has data
                particulars_col = column_mapping.get('Particulars', '')
                if not particulars_col:
                    continue
                    
                if pd.isna(row.get(particulars_col, '')) or str(row.get(particulars_col, '')).strip() == '':
                    continue
                
                processed_row = self._process_row(row, column_mapping)
                if processed_row:
                    processed_data.append(processed_row)
            
            if not processed_data:
                raise ValueError(
                    f"No transaction data found. Please check if the file contains transaction rows. "
                    f"Found columns: {list(df.columns)}. "
                    f"Column mapping: {column_mapping}"
                )
            
            df = pd.DataFrame(processed_data)
            
            # Keep only essential columns
            essential_cols = [
                'S.N.', 'Transaction Date', 'Particulars', 'Withdrawal Amt (INR)', 
                'Deposit Amt (INR)', 'Balance (INR)', 'Debit/Credit', 
                'Payment Category', 'Party Name1', 'Party Name2'
            ]
            df = df[[col for col in essential_cols if col in df.columns]]
            
            # Add Remark column using strict rule-based classification
            df = add_remark_column(df, "Particulars", "Payment Category")
            
            return df
            
        except Exception as e:
            raise Exception(f"Error processing AXIS Bank statement: {e}")
    
    def parse_transaction_description(self, particulars: str) -> pd.Series:
        """Parse AXIS transaction particulars"""
        if pd.isna(particulars) or particulars.strip() == "":
            return pd.Series(["", "", ""])
        
        particulars_clean = particulars.strip()
        parts = [p.strip() for p in particulars_clean.split('/') if p.strip()]
        
        payment_category = ""
        party1 = ""
        party2 = ""
        txn_type = ""
        first_part = parts[0].upper() if len(parts) > 0 else ""
        
        # Detect payment category
        if 'CLG' in first_part:
            txn_type = 'CLG'
            payment_category = 'CHEQUE CLEARING'
        elif 'MOB' in first_part or (len(parts) > 1 and 'TPFT' in parts[1].upper()):
            txn_type = 'MOB'
            payment_category = 'MOBILE TRANSFER'
        elif 'CASH' in particulars_clean.upper():
            txn_type = 'CASH'
            # Default to CASH DEPOSIT, will be validated later based on debit/credit
            if 'WITHDRAW' in particulars_clean.upper() or 'WD' in particulars_clean.upper():
                payment_category = 'CASH WITHDRAWAL'
            else:
                payment_category = 'CASH DEPOSIT'
        elif 'NEFT' in first_part:
            txn_type = 'NEFT'
            payment_category = 'NEFT'
        elif 'TRF' in first_part:
            txn_type = 'TRF'
            payment_category = 'TRANSFER'
        elif 'MMT' in first_part:
            txn_type = 'MMT'
            payment_category = 'MOBILE TRANSFER'
        elif 'IFT' in first_part:
            txn_type = 'IFT'
            payment_category = 'INSTANT FUND TRANSFER'
        elif 'RTGS' in first_part:
            txn_type = 'RTGS'
            payment_category = 'RTGS'
        elif 'IMPS' in first_part or (len(parts) > 1 and 'P2A' in parts[1].upper()):
            txn_type = 'IMPS'
            payment_category = 'IMPS'
        elif 'INB' in first_part:
            if len(parts) > 1:
                if 'IFT' in parts[1].upper():
                    txn_type = 'INB/IFT'
                    payment_category = 'INSTANT FUND TRANSFER'
                elif 'RTGS' in parts[1].upper():
                    txn_type = 'INB/RTGS'
                    payment_category = 'RTGS'
        
        # Extract Party Name
        party1, party2 = self._extract_party_names(parts, txn_type)
        
        # Clean party names, but be careful not to remove valid parts like "Bank" in "State Bank"
        # Only do light cleaning for CLG transactions to preserve full party names
        if txn_type == 'CLG':
            # For CLG, just trim and clean up extra spaces, don't remove words
            if party1:
                party1 = ' '.join(party1.split()).strip()
            if party2:
                party2 = ' '.join(party2.split()).strip()
        else:
            # For other transaction types, use standard cleaning
            party1 = clean_party_name(party1)
            party2 = clean_party_name(party2)
        
        return pd.Series([payment_category, party1, party2])
    
    def _map_columns(self, columns: list) -> Dict[str, str]:
        """Map column names to standard names"""
        column_mapping = {}
        
        for col in columns:
            col_lower = str(col).lower().strip()
            for standard_name, patterns in AXIS_COLUMN_PATTERNS.items():
                if any(pattern in col_lower for pattern in patterns):
                    # Only map if not already mapped
                    if standard_name not in column_mapping:
                        column_mapping[standard_name] = col
                    break
        
        # Additional fallback mappings for common variations
        if 'Particulars' not in column_mapping:
            for col in columns:
                col_lower = str(col).lower().strip()
                if 'particular' in col_lower or 'narration' in col_lower or 'description' in col_lower:
                    column_mapping['Particulars'] = col
                    break
        
        if 'Transaction Date' not in column_mapping:
            for col in columns:
                col_lower = str(col).lower().strip()
                if 'date' in col_lower and 'transaction' in col_lower:
                    column_mapping['Transaction Date'] = col
                    break
                elif 'date' in col_lower and 'value' not in col_lower:
                    column_mapping['Transaction Date'] = col
                    break
        
        if 'Amount(INR)' not in column_mapping:
            for col in columns:
                col_lower = str(col).lower().strip()
                if 'amount' in col_lower:
                    column_mapping['Amount(INR)'] = col
                    break
        
        if 'Debit/Credit' not in column_mapping:
            for col in columns:
                col_lower = str(col).lower().strip()
                if 'debit' in col_lower or 'credit' in col_lower or 'dr' in col_lower or 'cr' in col_lower:
                    column_mapping['Debit/Credit'] = col
                    break
        
        if 'Balance(INR)' not in column_mapping:
            for col in columns:
                col_lower = str(col).lower().strip()
                if 'balance' in col_lower:
                    column_mapping['Balance(INR)'] = col
                    break
        
        return column_mapping
    
    def _process_row(self, row: pd.Series, column_mapping: Dict[str, str]) -> Dict:
        """Process a single row of data"""
        # Extract transaction date
        transaction_date = ""
        if 'Transaction Date' in column_mapping:
            date_str = str(row.get(column_mapping['Transaction Date'], '')).strip()
            transaction_date = format_date(date_str)
        
        # Try to get date from other date columns if Transaction Date not found
        if not transaction_date or transaction_date == "":
            # Try Value Date or any column with 'date' in name
            for col in row.index:
                if 'date' in str(col).lower():
                    date_str = str(row.get(col, '')).strip()
                    transaction_date = format_date(date_str)
                    if transaction_date:
                        break
        
        # Skip rows without transaction date (but be lenient - only skip if we have no date info at all)
        if not transaction_date or transaction_date == "":
            # Still try to process if we have particulars and amount
            pass  # Don't skip yet, check particulars first
        
        # Extract particulars
        particulars = str(row.get(column_mapping.get('Particulars', ''))).strip()
        
        # Skip if no particulars
        if not particulars or particulars.lower() in ['nan', 'none', '']:
            return None
        
        # Extract amount and clean it
        amount_str = str(row.get(column_mapping.get('Amount(INR)', ''))).strip()
        amount = clean_amount(amount_str)
        
        # Determine debit/credit
        debit_credit = ''
        withdrawal_amt = '0'
        deposit_amt = '0'
        
        if 'Debit/Credit' in column_mapping:
            debit_credit_col = str(row.get(column_mapping.get('Debit/Credit', ''))).strip().upper()
            if 'CR' in debit_credit_col:
                debit_credit = 'Credit'
                withdrawal_amt = '0'
                deposit_amt = str(amount)
            elif 'DR' in debit_credit_col:
                debit_credit = 'Debit'
                withdrawal_amt = str(amount)
                deposit_amt = '0'
        
        # Fallback: Try to determine from withdrawal/deposit columns if Debit/Credit column not found
        if not debit_credit:
            # Check for separate withdrawal and deposit columns
            for col in row.index:
                col_lower = str(col).lower()
                if 'withdraw' in col_lower or 'debit' in col_lower:
                    withdraw_str = str(row.get(col, '')).strip()
                    withdraw_amt = clean_amount(withdraw_str)
                    if withdraw_amt and withdraw_amt != '0':
                        debit_credit = 'Debit'
                        withdrawal_amt = withdraw_amt
                        deposit_amt = '0'
                        break
                elif 'deposit' in col_lower or 'credit' in col_lower:
                    deposit_str = str(row.get(col, '')).strip()
                    deposit_amt_val = clean_amount(deposit_str)
                    if deposit_amt_val and deposit_amt_val != '0':
                        debit_credit = 'Credit'
                        withdrawal_amt = '0'
                        deposit_amt = deposit_amt_val
                        break
            
            # If still not determined, use amount and assume it's based on context
            if not debit_credit and amount and amount != '0':
                # Default to Debit if we can't determine
                debit_credit = 'Debit'
                withdrawal_amt = str(amount)
                deposit_amt = '0'
        
        # Extract balance and clean it
        balance_str = str(row.get(column_mapping.get('Balance(INR)', ''))).strip()
        balance = clean_amount(balance_str)
        
        # Parse payment category and party names from particulars
        payment_category, party1, party2 = self.parse_transaction_description(particulars)
        
        # Validate cash transactions based on debit/credit
        # Credit + Cash = CASH DEPOSIT, Debit + Cash = CASH WITHDRAWAL
        if 'CASH' in payment_category.upper():
            if debit_credit == 'Credit':
                payment_category = 'CASH DEPOSIT'
            elif debit_credit == 'Debit':
                payment_category = 'CASH WITHDRAWAL'
        
        # Use empty string for transaction date if not found (don't skip the row)
        if not transaction_date:
            transaction_date = ""
        
        return {
            'S.N.': str(row.get(column_mapping.get('S.N.', ''))),
            'Transaction Date': transaction_date,
            'Particulars': particulars,
            'Withdrawal Amt (INR)': withdrawal_amt,
            'Deposit Amt (INR)': deposit_amt,
            'Balance (INR)': str(balance),
            'Debit/Credit': debit_credit,
            'Payment Category': payment_category,
            'Party Name1': party1,
            'Party Name2': party2
        }
    
    def _extract_party_names(self, parts: list, txn_type: str) -> Tuple[str, str]:
        """Extract party names based on transaction type"""
        party1 = ""
        party2 = ""
        
        def is_reference_code(part: str) -> bool:
            """Check if a part looks like a reference code"""
            if not part or len(part.strip()) == 0:
                return True
            part_clean = part.strip()
            # All digits (cheque numbers, dates like 161025, account numbers)
            if part_clean.isdigit():
                return True
            # Very short codes (1-3 chars)
            if len(part_clean) <= 3:
                return True
            # Long alphanumeric codes (account numbers, references)
            if len(part_clean) > 12 and part_clean.isalnum():
                return True
            return False
        
        def is_bank_name(part: str) -> bool:
            """Check if a part looks like a bank name"""
            if not part:
                return False
            part_upper = part.upper().strip()
            
            # Check against known bank keywords
            for bank_keyword in BANK_KEYWORDS:
                if bank_keyword.upper() in part_upper or part_upper in bank_keyword.upper():
                    return True
            
            # Common bank name patterns
            bank_patterns = [
                r'^STATE\s+BANK',
                r'^BANK\s+OF',
                r'^BANK\s+OF\s+[A-Z]+',  # Bank Of Baroda, Bank Of India, etc.
                r'^[A-Z]+\s+BANK$',  # Any word followed by "BANK" at the end
                r'^HDFC',
                r'^ICICI',
                r'^AXIS',
                r'^SBI',
                r'^KOTAK',
                r'^YES\s+BANK',
                r'^UNION\s+BANK',
                r'^CANARA\s+BANK',
            ]
            
            for pattern in bank_patterns:
                if re.match(pattern, part_upper):
                    return True
            
            return False
        
        if txn_type in ['CLG']:
            # CLG format: CLG/CHEQUE_NUM/DATE/PARTY_NAME or CLG/CHEQUE_NUM/REFERENCE/PARTY_NAME
            # Examples: CLG/966427/151025/State Bank/SUNRISE FPPDFOOD AND
            #           CLG/000043/151025/Bank Of Ba/MAA GAYATRI ENTERPRI
            #           CLG/002184/161025/Kotak Mahi/
            # Party name is usually at index 3 or later
            # Filter out reference codes (cheque numbers, dates) AND bank names
            party_parts = []
            
            for i in range(3, len(parts)):
                part = parts[i].strip()
                if not part or is_reference_code(part):
                    continue
                
                # Check if this part is a bank name - skip it
                if is_bank_name(part):
                    continue
                
                # This part is not a bank name, add it to party parts
                party_parts.append(part)
            
            if party_parts:
                # Combine all non-bank-name parts (the actual party name)
                combined_all = ' '.join(party_parts)
                combined_all = ' '.join(combined_all.split())  # Clean up extra spaces
                
                if combined_all and len(combined_all) >= 4 and re.search(r'[A-Za-z]', combined_all):
                    # Don't accept if it's just a bank code pattern
                    if not re.match(r'^[A-Z]{3,4}\d+[A-Z]*\d*$', combined_all):
                        party1 = combined_all
                        party2 = combined_all
            
            # Fallback: if nothing found after filtering bank names, check if first part is not a bank name
            if not party1 and len(parts) >= 4:
                for i in range(3, len(parts)):
                    part = parts[i].strip()
                    if part and not is_reference_code(part) and not is_bank_name(part):
                        if len(part) >= 4 and re.search(r'[A-Za-z]', part):
                            party1 = part
                            party2 = part
                            break
                            
        elif txn_type in ['MOB']:
            # MOB/TPFT format: MOB/TPFT/PARTY_NAME/REFERENCE
            # Skip MOB (index 0) and TPFT (index 1), party name should be at index 2
            if len(parts) >= 3:
                # Skip MOB and TPFT, get party name
                party_name = parts[2].strip()
                # Check if it's not a reference code
                if not is_reference_code(party_name):
                    if is_valid_party_name(party_name) and not any(bank in party_name.upper() for bank in BANK_KEYWORDS):
                        party1 = party_name
                        party2 = party_name
                    elif len(party_name) >= 4:  # If it looks reasonable
                        party1 = party_name
                        party2 = party_name
                    else:
                        # Try combining with next parts if party name spans multiple parts
                        party_parts = [party_name]
                        for i in range(3, min(len(parts), 5)):  # Check up to 2 more parts
                            next_part = parts[i].strip()
                            if next_part and not is_reference_code(next_part):
                                party_parts.append(next_part)
                                combined = ' '.join(party_parts)
                                if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                    party1 = combined
                                    party2 = combined
                                    break
                        
        elif txn_type in ['CASH']:
            # Cash transactions - try last part or extract from description
            if len(parts) >= 1:
                potential_party = parts[-1].strip()
                if potential_party and not is_reference_code(potential_party):
                    if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                        party1 = potential_party
                        party2 = potential_party
        else:
            # For other transaction types (NEFT, RTGS, IMPS, etc.)
            # Skip first part (transaction type) and find party name
            # Also skip known transaction type indicators in second position
            skip_indices = [0]  # Always skip transaction type
            if len(parts) > 1:
                # Skip TPFT, IFT, RTGS etc if they appear in second position
                second_part = parts[1].upper().strip()
                if second_part in ['TPFT', 'IFT', 'RTGS', 'NEFT', 'IMPS']:
                    skip_indices.append(1)
            
            for i in range(1, len(parts)):
                if i in skip_indices:
                    continue
                part = parts[i].strip()
                if part and not is_reference_code(part):
                    if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                        party1 = part
                        party2 = part
                        break
            
            # Try combining parts if single parts don't work
            if not party1 and len(parts) >= 2:
                valid_parts = []
                for i in range(1, len(parts)):
                    if i not in skip_indices:
                        part = parts[i].strip()
                        if part and not is_reference_code(part):
                            valid_parts.append(part)
                
                if valid_parts:
                    for i in range(min(len(valid_parts), 5)):
                        for j in range(i+1, min(len(valid_parts), i+3)):
                            combined = ' '.join(valid_parts[i:j+1])
                            if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                party1 = combined
                                party2 = combined
                                break
                        if party1:
                            break
        
        return party1, party2
