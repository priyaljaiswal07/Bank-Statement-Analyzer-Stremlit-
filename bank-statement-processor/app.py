"""
Main Streamlit application for Bank Statement Processor
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from typing import Optional

from parsers import ICICIParser, AXISParser, JanaParser, RBLParser
from config import SUPPORTED_BANKS, SUPPORTED_FILE_TYPES


def main():
    """Main application function"""
    # Page configuration
    st.set_page_config(
        page_title="Bank Statement Processor", 
        layout="wide",
        page_icon="🏦"
    )
    
    # Title and description
    st.title("🏦 Bank Statement Processor")
    st.markdown("""
    Upload your bank statement and get processed data with extracted party names, 
    payment categories, and clean transaction details.
    """)
    
    # Sidebar for bank selection
    with st.sidebar:
        st.header("📋 Configuration")
        bank_option = st.selectbox(
            "Select Bank",
            SUPPORTED_BANKS,
            help="Choose your bank to process the statement"
        )
        
        st.markdown("---")
        st.markdown("### 📊 Supported Features")
        st.markdown("""
        - ✅ ICICI Bank (Yearly & Monthly)
        - ✅ AXIS Bank
        - ✅ Jana Bank
        - ✅ RBL Bank
        - ✅ Party Name Extraction
        - ✅ Payment Category Classification
        - ✅ Transaction Type Detection
        - ✅ Excel Export
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📁 Upload {bank_option} Statement")
        uploaded_file = st.file_uploader(
            f"Choose Excel file for {bank_option}",
            type=SUPPORTED_FILE_TYPES,
            help=f"Upload your {bank_option} bank statement in Excel format (.xlsx or .xls)"
        )
    
    with col2:
        st.subheader("ℹ️ Instructions")
        st.markdown("""
        1. **Select your bank** from the dropdown
        2. **Upload Excel file** of your statement
        3. **Review processed data** in the table below
        4. **Download** the processed file
        """)
    
    # Process file if uploaded
    if uploaded_file:
        try:
            with st.spinner(f"Processing {bank_option} statement..."):
                # Create appropriate parser
                parser = create_parser(bank_option)
                
                # Process the file
                df = parser.process_file(uploaded_file)
                
                if not df.empty:
                    st.success("✅ File processed successfully!")
                    display_results(df, bank_option, uploaded_file.name)
                else:
                    st.warning("⚠️ No data found in the uploaded file. Please check the file format.")
                    
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.markdown("**Detailed Error Information:**")
            st.code(str(e))
            st.markdown("**Troubleshooting:**")
            st.markdown("- Ensure the file is in the correct Excel format")
            st.markdown("- Check that the file contains transaction data")
            st.markdown("- Verify the bank selection matches your file")
            st.markdown("- For ICICI Monthly: Ensure file has 9 columns")
            st.markdown("- For ICICI Yearly: Ensure file has 10 columns")


def create_parser(bank_option: str):
    """Create appropriate parser based on bank selection"""
    if bank_option == "ICICI Yearly":
        return ICICIParser(is_monthly=False)
    elif bank_option == "ICICI Monthly":
        return ICICIParser(is_monthly=True)
    elif bank_option == "AXIS":
        return AXISParser()
    elif bank_option == "Jana Bank":
        return JanaParser()
    elif bank_option == "RBL Bank":
        return RBLParser()
    else:
        raise ValueError(f"Unsupported bank: {bank_option}")


def display_results(df: pd.DataFrame, bank_option: str, filename: str):
    """Display processed results and download option"""
    
    # Display processed data
    st.subheader("📊 Processed Data")
    
    # Show summary statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Transactions", len(df))
    with col2:
        credit_count = len(df[df["Debit/Credit"] == "Credit"])
        st.metric("Credit Transactions", credit_count)
    with col3:
        debit_count = len(df[df["Debit/Credit"] == "Debit"])
        st.metric("Debit Transactions", debit_count)
    with col4:
        unique_parties = len(df[df["Party Name1"] != ""]["Party Name1"].unique())
        st.metric("Unique Parties", unique_parties)
    
    # Display dataframe
    st.dataframe(df, use_container_width=True)
    
    # Show sample of extracted party names
    st.subheader("🔍 Sample Party Name Extraction")
    
    # Determine which columns to show based on bank type
    if bank_option in ["ICICI Yearly", "ICICI Monthly"]:
        description_col = "Description" if bank_option == "ICICI Monthly" else "Transaction Remarks"
        sample_cols = [description_col, "Party Name1", "Party Name2"]
    elif bank_option == "AXIS":
        sample_cols = ["Particulars", "Party Name1", "Party Name2"]
    elif bank_option == "Jana Bank":
        sample_cols = ["Description", "Party Name1", "Party Name2"]
    else:  # RBL Bank
        sample_cols = ["Transaction Details", "Party Name1", "Party Name2"]
    
    sample_data = df[sample_cols].head(10)
    st.dataframe(sample_data, use_container_width=True)
    
    # Download section
    st.subheader("💾 Download Processed File")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Download as Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Processed_Statement")
        processed_data = output.getvalue()
        
        st.download_button(
            label="📥 Download Excel File",
            data=processed_data,
            file_name=f"{bank_option.replace(' ', '_')}_Processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col2:
        # Download as CSV
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV File",
            data=csv_data,
            file_name=f"{bank_option.replace(' ', '_')}_Processed.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # Show payment category distribution
    if "Payment Category" in df.columns:
        st.subheader("📈 Payment Category Distribution")
        category_counts = df["Payment Category"].value_counts()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.bar_chart(category_counts)
        
        with col2:
            st.write("**Top Categories:**")
            for category, count in category_counts.head(5).items():
                st.write(f"• {category}: {count}")


if __name__ == "__main__":
    main()
