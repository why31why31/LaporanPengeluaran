import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import os

# --- 1. KONFIGURASI ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
DRIVE_FOLDER_ID = "1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX" # ID Folder Bapak

def get_gcp_service(service_name, version):
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build(service_name, version, credentials=creds)

def append_to_sheets(data):
    service = get_gcp_service('sheets', 'v4')
    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, 
        range="Pengeluaran!A1",
        valueInputOption="USER_ENTERED", # Memaksa format tanggal/angka dikenali Sheets
        insertDataOption="INSERT_ROWS", 
        body=body
    ).execute()

def upload_to_drive(file_content, file_name):
    try:
        service = get_gcp_service('drive', 'v3')
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf', resumable=False)
        service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
    except Exception as e:
        st.warning(f"Catatan: PDF tidak terupload ke Drive (Cek kuota/izin), tapi data Sheets aman. Error: {e}")

# --- 2. ANTARMUKA PENGGUNA ---
st.set_page_config(page_title="Sistem Laporan Wahyudi", layout="centered")
tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Pengeluaran Baru")
    # Form harus membungkus semua input dan tombol submit
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama Personel", value="Wahyudi")
        tgl = st.date_input("Tanggal Maintenance", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan (Kilian/Romaco/Lainnya)")
        
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        bukti_files = st.file_uploader("📸 Foto Nota", accept_multiple_files=True, type=['jpg','jpeg','png'])
        report_file = st.file_uploader("📄 Service Report (PDF)", type=['pdf'])
        
        # Variabel 'submit' dibuat di sini
        submit = st.form_submit_button("Simpan & Buat Laporan")

    # Logika 'if submit' harus berada di dalam 'with tab1'
    if submit:
        if not keperluan:
            st.error("Kolom Keperluan wajib diisi!")
        else:
            with st.spinner("Sedang memproses..."):
                try:
                    total = bensin + toll + makan + parkir
                    # Perbaikan Format Tanggal agar dikenali Sheets
                    tgl_iso = tgl.strftime('%Y-%m-%d')
                    data_row = [tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets(data_row)
                    
                    # 2. Proses PDF (Sama seperti sebelumnya)
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA", ln=True, align="C")
                    pdf.line(10, 25, 200, 25)
                    pdf.ln(10)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(50, 8, f"Bensin: Rp {bensin:,}", ln=True)
                    pdf.cell(50, 8, f"Toll: Rp {toll:,}", ln=True)
                    pdf.cell(50, 10, f"TOTAL: Rp {total:,}", ln=True)
                    
                    # Gabung lampiran jika ada
                    pdf_bytes = pdf.output()
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file:
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    content = final_pdf.getvalue()
                    
                    # 3. Upload ke Drive
                    upload_to_drive(content, f"Laporan_{nama}_{tgl_iso}.pdf")
                    
                    st.success("✅ Data berhasil masuk ke Google Sheets!")
                    st.download_button("📥 Download PDF", content, f"Laporan_{tgl_iso}.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Terjadi kesalahan sistem: {e}")

with tab2:
    st.header("Laporan Kumulatif")
    # (Bapak bisa memasukkan kode filter tanggal di sini nanti)
