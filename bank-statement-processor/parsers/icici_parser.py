"""
ICICI Bank parser for both yearly and monthly formats
"""

import pandas as pd
import re
from typing import Tuple
from parsers.base_parser import BaseBankParser
from config import ICICI_YEARLY_COLUMNS, ICICI_MONTHLY_COLUMNS, HEADER_ROWS, BANK_KEYWORDS
from utils import (
    is_valid_party_name, clean_party_name, clean_amount, 
    format_date, determine_debit_credit, determine_debit_credit_from_cr_dr,
    split_transaction_description, read_excel_file, add_remark_column
)


class ICICIParser(BaseBankParser):
    """Parser for ICICI Bank statements (both yearly and monthly formats)"""
    
    def __init__(self, is_monthly: bool = False):
        bank_name = "ICICI Monthly" if is_monthly else "ICICI Yearly"
        super().__init__(bank_name)
        self.is_monthly = is_monthly
        self.columns = ICICI_MONTHLY_COLUMNS if is_monthly else ICICI_YEARLY_COLUMNS
        self.header_row = HEADER_ROWS[bank_name]
    
    def process_file(self, file_path: str) -> pd.DataFrame:
        """Process ICICI bank statement file"""
        # Read Excel file (supports both .xls and .xlsx)
        df = read_excel_file(file_path, header=None, skiprows=self.header_row + 1, dtype=str)
        df = self.clean_dataframe(df)
        
        # Check if we have the right number of columns
        if len(df.columns) != len(self.columns):
            raise ValueError(f"Expected {len(self.columns)} columns but got {len(df.columns)}. "
                           f"Please check if this is the correct {self.bank_name} format.")
        
        # Set column names
        df.columns = self.columns
        
        # Replace hyphens with slashes for uniformity
        description_col = "Description" if self.is_monthly else "Transaction Remarks"
        df[description_col] = df[description_col].astype(str).str.replace("-", "/", regex=False)
        
        # Format dates
        if self.is_monthly:
            date_cols = ["Value Date", "Txn Posted Date"]
        else:
            date_cols = ["Value Date", "Transaction Date", "Transaction Posted Date and time"]
        
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(format_date)
        
        # Determine Debit/Credit
        if self.is_monthly:
            df["Debit/Credit"] = df["Cr/Dr"].apply(determine_debit_credit_from_cr_dr)
        else:
            df["Debit/Credit"] = df.apply(
                lambda row: determine_debit_credit(row["Withdrawal Amt (INR)"], row["Deposit Amt (INR)"]), 
                axis=1
            )
        
        # Parse Payment Category & Party Names
        df[["Payment Category", "Party Name1", "Party Name2"]] = df[description_col].apply(
            self.parse_transaction_description
        )
        
        # Validate cash transactions based on debit/credit
        # Credit + Cash = CASH DEPOSIT, Debit + Cash = CASH WITHDRAWAL
        cash_mask = df["Payment Category"].str.contains("CASH", case=False, na=False)
        df.loc[cash_mask & (df["Debit/Credit"] == "Credit"), "Payment Category"] = "CASH DEPOSIT"
        df.loc[cash_mask & (df["Debit/Credit"] == "Debit"), "Payment Category"] = "CASH WITHDRAWAL"
        
        # For monthly format, create Withdrawal/Deposit columns
        if self.is_monthly:
            df[["Withdrawal Amt (INR)", "Deposit Amt (INR)"]] = df.apply(
                self._get_withdrawal_deposit_monthly, axis=1
            )
        
        # Add Remark column using strict rule-based classification
        description_col = "Description" if self.is_monthly else "Transaction Remarks"
        df = add_remark_column(df, description_col, "Payment Category")
        
        return self._reorder_columns(df)
    
    def parse_transaction_description(self, description: str) -> pd.Series:
        """Parse ICICI transaction description"""
        if pd.isna(description) or description.strip() == "":
            return pd.Series(["", "", ""])
        
        parts = split_transaction_description(description)
        if not parts:
            return pd.Series(["", "", ""])
        
        # Handle REJECT transactions
        if parts[0].upper().startswith("REJECT"):
            return pd.Series(["REJECT", "", ""])
        
        txn_type = parts[0].upper()
        party1 = ""
        party2 = ""
        
        # INF/INFT Transactions
        if txn_type in ["INF", "INFT"]:
            party1, party2 = self._parse_inf_transaction(parts)
        
        # TRF Transactions
        elif txn_type == "TRF":
            party1, party2 = self._parse_trf_transaction(parts)
        
        # Cheque clearing
        elif txn_type == "CLG":
            party1, party2 = self._parse_clg_transaction(parts)
        
        # Cash deposits
        elif "CASH" in txn_type:
            party1, party2 = self._parse_cash_transaction(parts)
        
        # MMT/IMPS Transactions
        elif txn_type == "MMT":
            party1, party2 = self._parse_mmt_transaction(parts, description)
        
        # NEFT, RTGS, IMPS, CMS
        elif txn_type in ["NEFT", "RTGS", "IMPS", "CMS"]:
            party1, party2 = self._parse_standard_transaction(parts)
        
        # Clean party names
        party1 = clean_party_name(party1)
        party2 = clean_party_name(party2)
        
        # If party1 looks like a reference code or invalid, use party2 or try to extract better name
        def looks_like_reference_code(name: str) -> bool:
            """Check if name looks like a reference code rather than a party name"""
            if not name or len(name) < 3:
                return True
            name_clean = name.strip()
            # All digits
            if name_clean.isdigit():
                return True
            # Long alphanumeric codes
            if len(name_clean) > 15 and name_clean.isalnum():
                return True
            # Very short codes
            if len(name_clean) <= 3:
                return True
            # Contains many special characters or looks like a hash
            if len([c for c in name_clean if not c.isalnum() and c != ' ']) > len(name_clean) * 0.3:
                return True
            return False
        
        # If party1 is invalid, try to use party2 or extract from description again
        if looks_like_reference_code(party1) or not is_valid_party_name(party1):
            if party2 and not looks_like_reference_code(party2) and is_valid_party_name(party2):
                # Use party2 as party1
                party1 = party2
            elif not party1 or looks_like_reference_code(party1):
                # Try to extract a better name from the description
                # Look for parts that might be party names
                for i in range(len(parts) - 1, 0, -1):  # Start from end
                    part = parts[i].strip()
                    if part and not looks_like_reference_code(part):
                        if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                            if not party1 or looks_like_reference_code(party1):
                                party1 = part
                                if not party2:
                                    party2 = part
                            break
        
        # Ensure party2 is set if party1 is valid
        if party1 and not party2:
            party2 = party1
        elif party2 and not party1:
            party1 = party2
        
        # Get payment category
        payment_category = self.get_payment_category(txn_type)
        
        return pd.Series([payment_category, party1, party2])
    
    def _parse_inf_transaction(self, parts: list) -> Tuple[str, str]:
        """Parse INF/INFT transaction"""
        # Format examples:
        # INF/INFT/REFERENCE1/REFERENCE2/PARTY_NAME
        # INF/INFT/REFERENCE/PARTIAL_NAME/PARTY_NAME
        # INF/NEFT/REFERENCE/BANKCODE/PARTYNAME
        
        def is_reference_code(part: str) -> bool:
            """Check if a part looks like a reference code (not a party name)"""
            part_clean = part.strip()
            # All digits
            if part_clean.isdigit():
                return True
            # Long alphanumeric codes (like 61SDcgKgGU5RB7VpmKzIWe786286)
            if len(part_clean) > 15 and part_clean.isalnum():
                return True
            # Very short codes (1-3 chars)
            if len(part_clean) <= 3:
                return True
            return False
        
        if len(parts) >= 2 and parts[1] in ["NEFT", "RTGS", "IMPS"]:
            # Format: INF/NEFT/REFERENCE/BANKCODE/PARTYNAME
            # Skip transaction type and bank codes, look for party name from index 3 onwards
            for i in range(3, len(parts)):
                potential_party = parts[i].strip()
                if potential_party and not is_reference_code(potential_party):
                    if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                        return potential_party, potential_party
            
            # Try combining parts if single parts don't work
            if len(parts) >= 4:
                party_parts = []
                for i in range(3, len(parts)):
                    part = parts[i].strip()
                    if part and not is_reference_code(part):
                        party_parts.append(part)
                
                if party_parts:
                    # Try all combinations
                    for i in range(len(party_parts)):
                        for j in range(i+1, min(len(party_parts), i+3)):
                            combined = ' '.join(party_parts[i:j+1])
                            if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                return combined, combined
        else:
            # Format: INF/INFT/REFERENCE1/REFERENCE2/PARTY_NAME or INF/INFT/REFERENCE/PARTIAL/PARTY_NAME
            # Start from the end and work backwards to find party name
            # Party name is usually at the end, after reference codes
            party_parts = []
            
            # Collect potential party name parts from the end
            for i in range(len(parts) - 1, 1, -1):  # Start from end, skip INF/INFT
                part = parts[i].strip()
                if not part:
                    continue
                
                # If we hit a reference code, we've likely passed the party name
                if is_reference_code(part):
                    break
                
                # Check if it looks like a party name
                if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                    party_parts.insert(0, part)  # Insert at beginning to maintain order
                elif len(part) >= 4 and not part.isdigit() and any(c.isalpha() for c in part):
                    # Might be a partial party name, include it
                    party_parts.insert(0, part)
            
            # If we found party parts, use them
            if party_parts:
                # Try the last part first (most likely to be complete)
                if is_valid_party_name(party_parts[-1]) and not any(bank in party_parts[-1].upper() for bank in BANK_KEYWORDS):
                    return party_parts[-1], party_parts[-1]
                
                # Try combining all collected parts
                combined = ' '.join(party_parts)
                if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                    return combined, combined
                
                # If combined doesn't validate but looks reasonable, return it anyway
                if combined and len(combined) >= 4:
                    return combined, combined
            
            # Fallback: Try forward search from index 2
            for i in range(2, len(parts)):
                potential_party = parts[i].strip()
                if potential_party and not is_reference_code(potential_party):
                    if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                        return potential_party, potential_party
            
            # Try combining parts forward
            if len(parts) >= 3:
                valid_parts = [p.strip() for p in parts[2:] if p.strip() and not is_reference_code(p.strip())]
                if valid_parts:
                    for i in range(len(valid_parts)):
                        for j in range(i+1, min(len(valid_parts), i+3)):
                            combined = ' '.join(valid_parts[i:j+1])
                            if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                                return combined, combined
                    
                    # Last resort: return the last valid part if it looks reasonable
                    if valid_parts[-1] and len(valid_parts[-1]) >= 4:
                        return valid_parts[-1], valid_parts[-1]
        
        return "", ""
    
    def _parse_trf_transaction(self, parts: list) -> Tuple[str, str]:
        """Parse TRF transaction"""
        # Format: TRF/PARTY_NAME or TRF/REFERENCE/PARTY_NAME
        for i in range(1, len(parts)):
            potential_party = parts[i]
            if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                return potential_party, potential_party
        
        # Try combining parts
        if len(parts) >= 2:
            for i in range(1, min(len(parts), 4)):
                for j in range(i+1, min(len(parts), i+3)):
                    combined = ' '.join(parts[i:j+1])
                    if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                        return combined, combined
        return "", ""
    
    def _parse_clg_transaction(self, parts: list) -> Tuple[str, str]:
        """Parse CLG (cheque clearing) transaction"""
        # Format: CLG/PARTY_NAME/CHEQUE_NUMBER/BANK_CODE/DATE
        # Party name is at index 1 (right after CLG)
        if len(parts) >= 2:
            party_name = parts[1].strip()
            
            # Party name might be a single word or multi-word (e.g., "VICKY AGARWAL", "ROYAL MART")
            # First validate the party name at index 1
            if is_valid_party_name(party_name) and not any(bank in party_name.upper() for bank in BANK_KEYWORDS):
                return party_name, party_name
            
            # If validation fails, check if it's because it's a multi-word name that needs checking
            # Split by spaces and validate each part, or use the whole thing if it looks reasonable
            if party_name and len(party_name) >= 3:
                # Check if it's not a cheque number (all digits) or very short code
                if not party_name.isdigit() and len(party_name) > 3:
                    # Check if it contains spaces (multi-word name)
                    if ' ' in party_name:
                        # Multi-word name - validate it
                        words = party_name.split()
                        # If all words are reasonable length and contain letters
                        if all(len(word) >= 2 and any(c.isalpha() for c in word) for word in words):
                            if not any(bank in party_name.upper() for bank in BANK_KEYWORDS):
                                return party_name, party_name
                    else:
                        # Single word - return if it's reasonable
                        if not any(bank in party_name.upper() for bank in BANK_KEYWORDS):
                            return party_name, party_name
            
            # If index 1 doesn't work, try combining index 1 with index 2 (in case party name spans multiple parts)
            # But only if index 2 doesn't look like a cheque number
            if len(parts) >= 3:
                next_part = parts[2].strip()
                # Check if next part is likely a cheque number (all digits) or bank code (3 chars)
                is_cheque_or_code = next_part.isdigit() or (len(next_part) <= 3 and next_part.isalnum())
                
                if not is_cheque_or_code:
                    # Try combining
                    combined = f"{party_name} {next_part}"
                    if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                        return combined, combined
        
        return "", ""
    
    def _parse_cash_transaction(self, parts: list) -> Tuple[str, str]:
        """Parse cash deposit transaction"""
        # Cash transactions usually don't have party names, but try to extract if available
        for i in range(1, len(parts)):
            potential_party = parts[i]
            if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in BANK_KEYWORDS):
                return potential_party, potential_party
        return "", ""
    
    def _parse_mmt_transaction(self, parts: list, description: str) -> Tuple[str, str]:
        """Parse MMT transaction"""
        # Handle MMT/IMPS format specifically
        if "IMPS" in description.upper():
            imps_parts = split_transaction_description(description)
            for i in range(len(imps_parts)):
                part = imps_parts[i]
                if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                    return part, part
            
            # Try combining parts
            for i in range(len(imps_parts)):
                for j in range(i+1, min(len(imps_parts), i+3)):
                    combined = ' '.join(imps_parts[i:j+1])
                    if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                        return combined, combined
        
        # If no party found in MMT/IMPS, use the original logic
        for i in range(2, len(parts)):
            current_part = parts[i]
            if is_valid_party_name(current_part) and not any(bank in current_part.upper() for bank in BANK_KEYWORDS):
                return current_part, current_part
        
        # Try combining parts
        if len(parts) >= 3:
            for i in range(2, min(len(parts), 5)):
                for j in range(i+1, min(len(parts), i+3)):
                    combined = ' '.join(parts[i:j+1])
                    if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                        return combined, combined
        
        return "", ""
    
    def _parse_standard_transaction(self, parts: list) -> Tuple[str, str]:
        """Parse standard transactions (NEFT, RTGS, IMPS, CMS)"""
        # Format: TXN_TYPE/BANKCODE/REFERENCE/PARTY_NAME or TXN_TYPE/PARTY_NAME/...
        # Skip first part (transaction type) and try to find party name
        for i in range(1, len(parts)):
            current_part = parts[i]
            if is_valid_party_name(current_part) and not any(bank in current_part.upper() for bank in BANK_KEYWORDS):
                return current_part, current_part
        
        # Try combining parts if single parts don't work (for multi-word party names)
        if len(parts) >= 3:
            for i in range(1, min(len(parts), 5)):  # Check up to 5 parts
                for j in range(i+1, min(len(parts), i+3)):  # Combine up to 3 words
                    combined = ' '.join(parts[i:j+1])
                    if is_valid_party_name(combined) and not any(bank in combined.upper() for bank in BANK_KEYWORDS):
                        return combined, combined
        return "", ""
    
    def _get_withdrawal_deposit_monthly(self, row) -> pd.Series:
        """Get withdrawal/deposit amounts for monthly format"""
        amount_str = str(row["Transaction Amount(INR)"]).strip()
        amount = clean_amount(amount_str)
        
        if row["Debit/Credit"] == "Debit":
            return pd.Series([amount, "0"])
        elif row["Debit/Credit"] == "Credit":
            return pd.Series(["0", amount])
        else:
            return pd.Series(["0", "0"])
    
    def _reorder_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reorder columns based on format"""
        if self.is_monthly:
            cols_order = [
                "No.", "Transaction ID", "Value Date", "Txn Posted Date", "ChequeNo.",
                "Description", "Withdrawal Amt (INR)", "Deposit Amt (INR)", 
                "Available Balance(INR)", "Debit/Credit", "Payment Category", 
                "Party Name1", "Party Name2", "Remark"
            ]
        else:
            cols_order = [
                "S.N.", "Tran. Id", "Value Date", "Transaction Date", 
                "Transaction Posted Date and time", "Cheque. No./Ref. No.",
                "Transaction Remarks", "Withdrawal Amt (INR)", "Deposit Amt (INR)",
                "Balance (INR)", "Debit/Credit", "Payment Category", 
                "Party Name1", "Party Name2", "Remark"
            ]
        
        return df[[c for c in cols_order if c in df.columns]]
