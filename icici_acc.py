# save as app.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Bank Statement Processor", layout="wide")
st.title("Bank Statement Processor ✅")

# Common functions for both banks - MOVED TO TOP
def is_valid_party_name(name):
    """Check if the name is a valid party name (not a bank code, reference number, etc.)"""
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
                     "BANQUE", "LIMITED", "LTD", "PVT", "PRIVATE", "CO", "COMPANY", "CORP", "CORPORATION",
                     "BULD", "BANK", "HDFC BANK", "KOTAK MAHINDRA BANK", "MAHINDRA BANK"]
    if name_upper in unwanted_terms:
        return False
    
    # Must contain alphabets and be of reasonable length
    if (re.search(r'[A-Za-z]', name) and len(name) >= 4):
        return True
    
    return False

def clean_party_name(name):
    """Clean up party name by removing unwanted patterns"""
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
    bank_names = ['HDFC', 'ICICI', 'SBI', 'AXIS', 'YES', 'BANK', 'BANQUE', 'LIMITED', 
                 'LTD', 'PVT', 'PRIVATE', 'CO', 'COMPANY', 'CORP', 'CORPORATION',
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

def clean_amount(amount_str):
    """Clean amount string by removing commas and other non-numeric characters"""
    if pd.isna(amount_str) or amount_str.strip() == "":
        return "0"
    # Remove commas, spaces, and other non-numeric characters except decimal point
    cleaned = re.sub(r'[^\d.]', '', str(amount_str))
    return cleaned if cleaned else "0"

def parse_axis_particulars_improved(particulars):
    if pd.isna(particulars) or particulars.strip() == "":
        return "", "", ""
    particulars_clean = particulars.strip()
    parts = [p.strip() for p in particulars_clean.split('/') if p.strip()]
    payment_category = ""
    party1 = ""
    party2 = ""
    bank_keywords = [
        'ICICI', 'AXIS', 'CANARA', 'SBI', 'HDFC', 'YES', 'BANK',
        'INDIAN', 'PUNJAB NAT', 'BANDHAN BA', 'BARODA', 'BARODA U.P', 'KOTAK',
        'JAMMU', 'JAMMU AND', 'JAMMU &', 'UNION', 'UCOBANK', 'BANKOFBA'
    ]
    txn_type = ""
    first_part = parts[0].upper() if len(parts) > 0 else ""

    # -----------------------------
    # Detect payment category
    # -----------------------------
    if 'CLG' in first_part:
        txn_type = 'CLG'
        payment_category = 'CHEQUE CLEARING'
    elif 'CASH DEP' in particulars_clean.upper() or 'CASH DEP' in first_part:
        txn_type = 'CASH'
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

    # -----------------------------
    # Extract Party Name
    # -----------------------------
    if txn_type in ['CLG']:
        for part in parts[3:]:
            if is_valid_party_name(part) and not any(bank in part.upper() for bank in bank_keywords):
                party1 = part
                party2 = part
                break
        if party1 == "":
            party1 = ""
            party2 = ""
    elif txn_type in ['CASH']:
        if len(parts) >= 1:
            potential_party = parts[-1]
            if is_valid_party_name(potential_party) and not any(bank in potential_party.upper() for bank in bank_keywords):
                party1 = potential_party
                party2 = potential_party
            else:
                party1 = ""
                party2 = ""
    else:
        for part in parts:
            if is_valid_party_name(part) and not any(bank in part.upper() for bank in bank_keywords):
                party1 = part
                party2 = part
                break

    party1 = clean_party_name(party1)
    party2 = clean_party_name(party2)

    return payment_category, party1, party2


# Bank selection dropdown
bank_option = st.selectbox(
    "Select Bank",
    ["ICICI", "AXIS"],
    help="Choose your bank to process the statement"
)

uploaded_file = st.file_uploader(f"Upload {bank_option} Bank Statement (Excel)", type=["xlsx"])

if uploaded_file:
    st.success("File uploaded successfully!")
    
    if bank_option == "ICICI":
        # ICICI BANK PROCESSING (Your existing code)
        # Read Excel starting row 15 for ICICI
        header_row = 14
        df = pd.read_excel(uploaded_file, header=None, skiprows=header_row + 1, dtype=str)
        df = df.dropna(how='all')

        # Set column names for ICICI
        df.columns = [
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

        # Replace hyphens with slashes for uniformity
        df["Transaction Remarks"] = df["Transaction Remarks"].astype(str).str.replace("-", "/", regex=False)

        # Format dates
        date_cols = ["Value Date", "Transaction Date", "Transaction Posted Date and time"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')

        # Debit/Credit
        def debit_credit(row):
            if row["Deposit Amt (INR)"] and str(row["Deposit Amt (INR)"]).strip() not in ["", "0", "0.0"]:
                return "Credit"
            elif row["Withdrawal Amt (INR)"] and str(row["Withdrawal Amt (INR)"]).strip() not in ["", "0", "0.0"]:
                return "Debit"
            else:
                return ""

        df["Debit/Credit"] = df.apply(debit_credit, axis=1)

        # Parse Payment Category & Party Names
        def parse_remarks(remark):
            if pd.isna(remark) or remark.strip() == "":
                return pd.Series(["", "", ""])
            
            remark = remark.strip()
            remark = remark.replace(" /", "/").replace("/ ", "/")
            remark = re.sub(r"/+", "/", remark)

            # REJECT
            if remark.upper().startswith("REJECT"):
                return pd.Series(["REJECT", "", ""])

            parts = remark.split("/")
            txn_type = parts[0].upper()

            party1 = ""
            party2 = ""

            # INF/INFT Transactions - IMPROVED HANDLING
            if txn_type in ["INF", "INFT"]:
                # Handle INF/NEFT combined format
                if len(parts) >= 2 and parts[1] in ["NEFT", "RTGS", "IMPS"]:
                    # Format: INF/NEFT/REFERENCE/BANKCODE/PARTYNAME
                    if len(parts) >= 5:
                        # The party name is usually in the last part
                        potential_party = parts[-1]
                        if is_valid_party_name(potential_party):
                            party1 = potential_party
                            party2 = potential_party
                        else:
                            # If last part is not valid, try to find a valid party name in other parts
                            for i in range(4, len(parts)):
                                if is_valid_party_name(parts[i]):
                                    party1 = parts[i]
                                    party2 = parts[i]
                                    break
                else:
                    # Original INF logic
                    if len(parts) >= 4:
                        party1 = parts[3]
                        party2 = parts[-1]
            
            # TRF Transactions
            elif txn_type == "TRF":
                if len(parts) >= 2:
                    party1 = parts[1]  # This gets "MODI STORES" or "PARCHUNIWALES"
                    party2 = party1
            
            # Cheque clearing
            elif txn_type == "CLG":
                if len(parts) >= 2:
                    party1 = parts[1]
                    party2 = party1

            # Cash deposits
            elif "CASH" in txn_type:
                if len(parts) >= 2:
                    party2 = parts[-1]

            # MMT/IMPS Transactions
            elif txn_type == "MMT":
                # Handle MMT/IMPS format specifically
                if "IMPS" in remark.upper():
                    imps_parts = remark.split("/")
                    # Look for meaningful party names in the parts
                    for i in range(len(imps_parts)):
                        part = imps_parts[i]
                        if is_valid_party_name(part):
                            party1 = part
                            party2 = part
                            break
                
                # If no party found in MMT/IMPS, use the original logic
                if not party1 and len(parts) >= 3:
                    for i in range(2, len(parts)):
                        current_part = parts[i]
                        if is_valid_party_name(current_part):
                            party1 = current_part
                            party2 = current_part
                            break

            # NEFT, RTGS, IMPS, CMS
            elif txn_type in ["NEFT", "RTGS", "IMPS", "CMS"]:
                if len(parts) >= 3:
                    for i in range(2, len(parts)):
                        current_part = parts[i]
                        if is_valid_party_name(current_part):
                            party1 = current_part
                            party2 = current_part
                            break

            # Cleanup empty or placeholder names
            party1 = clean_party_name(party1)
            party2 = clean_party_name(party2)

            # Map Payment Category
            payment_category_map = {
                "CLG": "CHEQUE CLEARING",
                "CASH": "CASH DEPOSIT",
                "INF": "INF TRANSACTION",
                "INFT": "INF TRANSACTION",
                "TRF": "TRANSFER",
                "MMT": "MOBILE MONEY TRANSFER"
            }
            payment_category = payment_category_map.get(txn_type, txn_type)

            return pd.Series([payment_category, party1, party2])

        df[["Payment Category", "Party Name1", "Party Name2"]] = df["Transaction Remarks"].apply(parse_remarks)

        # Reorder columns
        cols_order = [
            "S.N.",
            "Tran. Id",
            "Value Date",
            "Transaction Date",
            "Transaction Posted Date and time",
            "Cheque. No./Ref. No.",
            "Transaction Remarks",
            "Withdrawal Amt (INR)",
            "Deposit Amt (INR)",
            "Balance (INR)",
            "Debit/Credit",
            "Payment Category",
            "Party Name1",
            "Party Name2"
        ]
        df = df[[c for c in cols_order if c in df.columns]]

    elif bank_option == "AXIS":
        # AXIS BANK PROCESSING - IMPROVED
        st.info("AXIS Bank processing selected")
        
        try:
            # Read Excel file - row 16 contains column names, data starts from row 18
            df = pd.read_excel(uploaded_file, header=15, dtype=str)  # Row 16 is header (0-indexed)
            df = df.dropna(how='all')
            
            # Remove rows with "OPENING BALANCE"
            df = df[~df.astype(str).apply(lambda x: x.str.contains('OPENING BALANCE', case=False, na=False)).any(axis=1)]
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Identify the correct columns based on Axis format
            column_mapping = {}
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 's.no' in col_lower or 'sno' in col_lower:
                    column_mapping['S.N.'] = col
                elif 'transaction' in col_lower and 'date' in col_lower:
                    column_mapping['Transaction Date'] = col
                elif 'particular' in col_lower:
                    column_mapping['Particulars'] = col
                elif 'amount' in col_lower:
                    column_mapping['Amount(INR)'] = col
                elif 'debit/cred' in col_lower or 'debit/credit' in col_lower:
                    column_mapping['Debit/Credit'] = col
                elif 'balance' in col_lower:
                    column_mapping['Balance(INR)'] = col
            
            # Create a standardized dataframe
            processed_data = []
            
            for idx, row in df.iterrows():
                if pd.isna(row.get(column_mapping.get('Particulars', ''))):
                    continue
                    
                # Extract transaction date
                transaction_date = ""
                if 'Transaction Date' in column_mapping:
                    date_str = str(row.get(column_mapping['Transaction Date'], '')).strip()
                    if date_str:
                        try:
                            transaction_date = pd.to_datetime(date_str, errors='coerce', dayfirst=True).strftime('%d/%m/%Y')
                        except:
                            transaction_date = ""
                
                # Extract particulars
                particulars = str(row.get(column_mapping.get('Particulars', ''))).strip()
                
                # Extract amount and clean it
                amount_str = str(row.get(column_mapping.get('Amount(INR)', ''))).strip()
                amount = clean_amount(amount_str)
                
                # Determine debit/credit
                debit_credit_col = str(row.get(column_mapping.get('Debit/Credit', ''))).strip().upper()
                if 'CR' in debit_credit_col:
                    debit_credit = 'Credit'
                    withdrawal_amt = '0'
                    deposit_amt = str(amount)
                elif 'DR' in debit_credit_col:
                    debit_credit = 'Debit'
                    withdrawal_amt = str(amount)
                    deposit_amt = '0'
                else:
                    debit_credit = ''
                    withdrawal_amt = '0'
                    deposit_amt = '0'
                
                # Extract balance and clean it
                balance_str = str(row.get(column_mapping.get('Balance(INR)', ''))).strip()
                balance = clean_amount(balance_str)
                
                # Parse payment category and party names from particulars
                payment_category, party1, party2 = parse_axis_particulars_improved(particulars)
                
                processed_data.append({
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
                })
            
            df = pd.DataFrame(processed_data)
            
            # Keep only essential columns (like ICICI format)
            essential_cols = [
                'S.N.', 'Transaction Date', 'Particulars', 'Withdrawal Amt (INR)', 
                'Deposit Amt (INR)', 'Balance (INR)', 'Debit/Credit', 
                'Payment Category', 'Party Name1', 'Party Name2'
            ]
            df = df[[col for col in essential_cols if col in df.columns]]
            
        except Exception as e:
            st.error(f"Error processing Axis Bank statement: {e}")
            st.write("Raw data columns:", df.columns.tolist() if 'df' in locals() else "No data")
            df = pd.DataFrame()

    # Show processed table
    if not df.empty:
        st.subheader("Processed Data")
        st.dataframe(df)

        # Show sample of extracted party names for verification
        st.subheader("Sample Party Name Extraction")
        if bank_option == "ICICI":
            sample_cols = ["Transaction Remarks", "Party Name1", "Party Name2"]
        else:  # AXIS
            sample_cols = ["Particulars", "Party Name1", "Party Name2"]
        
        sample_data = df[sample_cols].head(10)
        st.dataframe(sample_data)

        # Download processed file
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Processed_Statement")
        processed_data = output.getvalue()

        st.download_button(
            label="Download Processed File",
            data=processed_data,
            file_name=f"{bank_option}_Processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No data processed. Please check your file format.")