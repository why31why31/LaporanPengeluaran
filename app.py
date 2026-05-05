import streamlit as st
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- 1. KONFIGURASI GOOGLE SHEETS ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 
RANGE_NAME = "Pengeluaran!A1" 

def get_sheets_service():
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

# --- 2. ANTARMUKA PENGGUNA ---
st.set_page_config(page_title="Input Pengeluaran Asep Wahyu", layout="centered")
st.title("📊 Rekap Pengeluaran & Nota PDF")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Asep Wahyu")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan (Misal: Maintenance/Visit)")
    
    st.divider()
    c1, c2 = st.columns(2)
    bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = c2.number_input("Parkir/Lainnya (Rp)", min_value=0, step=1000)
    
    st.divider()
    bukti_files = st.file_uploader("📸 Lampirkan Foto Nota", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    submit = st.form_submit_button("Simpan & Buat PDF")

# --- 3. PROSES DATA ---
if submit:
    if not keperluan:
        st.error("Kolom Keperluan wajib diisi!")
    else:
        with st.spinner("Menyimpan ke Sheets dan menyusun PDF..."):
            try:
                total = bensin + toll + makan + parkir
                data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
                
                # A. SIMPAN KE GOOGLE SHEETS
                append_to_sheets(data_row)
                
                # B. BUAT PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "NOTA PENGELUARAN LAPANGAN", ln=True, align="C")
                pdf.ln(10)
                
                pdf.set_font("Arial", "", 12)
                pdf.cell(50, 10, "Nama", 0); pdf.cell(0, 10, f": {nama}", 0, ln=True)
                pdf.cell(50, 10, "Tanggal", 0); pdf.cell(0, 10, f": {tgl}", 0, ln=True)
                pdf.cell(50, 10, "Keperluan", 0); pdf.multi_cell(0, 10, f": {keperluan}")
                pdf.ln(5)
                pdf.cell(0, 0, "", "T", ln=True) 
                pdf.ln(5)
                
                pdf.cell(50, 10, "Bensin", 0); pdf.cell(0, 10, f": Rp {bensin:,}", 0, ln=True)
                pdf.cell(50, 10, "Toll", 0); pdf.cell(0, 10, f": Rp {toll:,}", 0, ln=True)
                pdf.cell(50, 10, "Makan", 0); pdf.cell(0, 10, f": Rp {makan:,}", 0, ln=True)
                pdf.cell(50, 10, "Parkir", 0); pdf.cell(0, 10, f": Rp {parkir:,}", 0, ln=True)
                
                pdf.set_font("Arial", "B", 12)
                pdf.cell(50, 10, "TOTAL", 0); pdf.cell(0, 10, f": Rp {total:,}", 0, ln=True)
                
                if bukti_files:
                    for f in bukti_files:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 14)
                        pdf.cell(0, 10, f"LAMPIRAN: {f.name}", ln=True)
                        tmp_path = f"temp_{f.name}"
                        with open(tmp_path, "wb") as tmp_file:
                            tmp_file.write(f.getbuffer())
                        pdf.image(tmp_path, x=10, w=180) 
                        os.remove(tmp_path)
                
                # KONVERSI KE BYTES (PENTING!)
                pdf_output = bytes(pdf.output()) 
                
                st.success("✅ Data tersimpan di Google Sheets!")
                st.balloons()
                
                st.download_button(
                    label="📥 Download PDF Nota",
                    data=pdf_output,
                    file_name=f"Nota_{nama}_{tgl}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
