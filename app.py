import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os

# --- KONFIGURASI ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 

def get_sheets_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('sheets', 'v4', credentials=creds)

def append_to_sheets(data):
    service = get_sheets_service()
    body = {'values': [data]}
    # Metode .append akan otomatis mencari baris kosong paling bawah
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Pengeluaran!A1", 
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

# --- UI APP ---
st.set_page_config(page_title="Sistem Laporan Wahyudi")

tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Pengeluaran")
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama", value="Wahyudi")
        tgl = st.date_input("Tanggal", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan")
        
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin", min_value=0)
        toll = c2.number_input("Toll", min_value=0)
        makan = c1.number_input("Makan", min_value=0)
        parkir = c2.number_input("Parkir", min_value=0)
        
        bukti_files = st.file_uploader("Upload Foto Nota", accept_multiple_files=True, type=['jpg','png','jpeg'])
        report_file = st.file_uploader("Upload Service Report (PDF)", type=['pdf'])
        
        submit = st.form_submit_button("Simpan Data")

    if submit:
        try:
            total = bensin + toll + makan + parkir
            # Data yang dikirim ke Sheets
            data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
            
            # Panggil fungsi append
            append_to_sheets(data_row)
            st.success(f"✅ Berhasil! Data untuk '{keperluan}' telah ditambahkan di baris baru.")
        except Exception as e:
            st.error(f"Gagal menyimpan: {e}")

# ... (Tab 2 tetap sama seperti sebelumnya)
