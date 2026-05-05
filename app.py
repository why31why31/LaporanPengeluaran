import streamlit as st
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- 1. KONFIGURASI GOOGLE SHEETS ---
# Gunakan ID Spreadsheet Anda
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 
# Pastikan nama tab adalah "Pengeluaran"
RANGE_NAME = "Pengeluaran!A1" 

def get_sheets_service():
    # Mengambil kredensial dari Streamlit Secrets
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

# --- 2. ANTARMUKA PENGGUNA (UI) ---
st.set_page_config(page_title="Input Pengeluaran Wahyudi", layout="centered")

st.title("📊 Rekap Pengeluaran & Nota PDF")
st.info("Data otomatis tersimpan ke Google Sheets. PDF dapat diunduh setelah simpan.")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Wahyudi")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan (Misal: Maintenance Kilian/Romaco)")
    
    st.divider()
    c1, c2 = st.columns(2)
    bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = c2.number_input("Parkir/Lainnya (Rp)", min_value=0, step=1000)
    
    st.divider()
    bukti_files = st.file_uploader("📸 Lampirkan Foto Nota", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    
    submit = st.form_submit_button("Simpan ke Sheets & Buat PDF")

# --- 3. PROSES DATA ---
if submit:
    if not keperluan:
        st.error("Kolom Keperluan tidak boleh kosong!")
    else:
        with st.spinner("Sedang memproses..."):
            try:
                total = bensin + toll + makan + parkir
                data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
                
                # A. SIMPAN KE GOOGLE SHEETS
                append_to_sheets(data_row)
                
                # B. BUAT PDF RINCIAN
                pdf = FPDF()
                pdf.add_page()
                
                # Header PDF
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "NOTA PENGELUARAN LAPANGAN", ln=True, align="C")
                pdf.ln(10)
                
                # Isi PDF
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
                pdf.cell(50, 10, "Parkir/Lainnya", 0); pdf.cell(0, 10, f": Rp {parkir:,}", 0, ln=True)
                
                pdf.set_font("Arial", "B", 12)
                pdf.cell(50, 10, "TOTAL", 0); pdf.cell(0, 10, f": Rp {total:,}", 0, ln=True)
                
                # C. TAMBAHKAN FOTO KE PDF
                if bukti_files:
                    for f in bukti_files:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 14)
                        pdf.cell(0, 10, f"LAMPIRAN BUKTI: {f.name}", ln=True)
                        pdf.ln(5)
                        
                        tmp_path = f"temp_{f.name}"
                        with open(tmp_path, "wb") as tmp_file:
                            tmp_file.write(f.getbuffer())
                        
                        pdf.image(tmp_path, x=10, w=180) 
                        os.remove(tmp_path)
                
                # Perbaikan: pdf.output() pada fpdf2 sudah mengembalikan bytes
                pdf_output = pdf.output() 
                
                st.success("✅ Data berhasil masuk ke Google Sheets!")
                st.balloons()
                
                # Tombol Download PDF
                st.download_button(
                    label="📥 Download PDF Nota & Foto",
                    data=pdf_output,
                    file_name=f"Nota_{nama}_{tgl}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Terjadi kesalahan teknis: {e}")
