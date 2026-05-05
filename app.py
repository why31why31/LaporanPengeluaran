import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- KONFIGURASI GOOGLE SHEETS ---
# Masukkan ID Spreadsheet yang Anda buat tadi
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
RANGE_NAME = "Pengeluaran!A1" # Nama sheet dan sel mulai

def get_sheets_service():
    # Mengambil kunci rahasia dari Streamlit Secrets
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('sheets', 'v4', credentials=creds)

def append_to_sheets(data):
    service = get_sheets_service()
    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

# --- ANTARMUKA PENGGUNA (UI) ---
st.set_page_config(page_title="Sistem Input Wahyudi", layout="centered")
st.title("📊 Rekap Pengeluaran Otomatis")
st.write("Data akan langsung masuk ke Google Sheets & PDF bisa di-download.")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Wahyudi")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan (Maintenance/Lainnya)")
    
    st.divider()
    c1, c2 = st.columns(2)
    bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
    
    bukti_files = st.file_uploader("📸 Foto Nota (PDF)", accept_multiple_files=True, type=['jpg','png','jpeg'])
    submit = st.form_submit_button("Simpan Data")

if submit:
    if not keperluan:
        st.error("Isi Keperluan!")
    else:
        try:
            total = bensin + toll + makan + parkir
            data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
            
            # 1. Simpan ke Google Sheets (Data Terkumpul Otomatis)
            append_to_sheets(data_row)
            
            # 2. Buat PDF (Untuk arsip jika butuh)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "NOTA PENGELUARAN", ln=True, align="C")
            pdf.output("temp_nota.pdf")
            
            st.success("✅ Data tersimpan di Google Sheets!")
            st.balloons()
            
            with open("temp_nota.pdf", "rb") as f:
                st.download_button("📥 Download PDF Nota", f, "Nota.pdf")
                
        except Exception as e:
            st.error(f"Gagal: {e}")
