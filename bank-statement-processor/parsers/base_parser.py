"""
Base parser class for bank statement processing
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, List, Tuple, Optional
from config import BANK_KEYWORDS, PAYMENT_CATEGORY_MAP
from utils import (
    is_valid_party_name, clean_party_name, clean_amount, 
    format_date, determine_debit_credit, split_transaction_description
)


class BaseBankParser(ABC):
    """Base class for bank statement parsers"""
    
    def __init__(self, bank_name: str):
        self.bank_name = bank_name
    
    @abstractmethod
    def process_file(self, file_path: str) -> pd.DataFrame:
        """Process bank statement file and return DataFrame"""
        pass
    
    @abstractmethod
    def parse_transaction_description(self, description: str) -> pd.Series:
        """Parse transaction description to extract payment category and party names"""
        pass
    
    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Common dataframe cleaning operations"""
        df = df.dropna(how='all')
        return df
    
    def get_payment_category(self, txn_type: str) -> str:
        """Get payment category from transaction type"""
        return PAYMENT_CATEGORY_MAP.get(txn_type, txn_type)
    
    def extract_party_names(self, parts: List[str]) -> Tuple[str, str]:
        """Extract party names from transaction parts"""
        party1 = ""
        party2 = ""
        
        for part in parts:
            if is_valid_party_name(part) and not any(bank in part.upper() for bank in BANK_KEYWORDS):
                party1 = part
                party2 = part
                break
        
        party1 = clean_party_name(party1)
        party2 = clean_party_name(party2)
        
        return party1, party2
