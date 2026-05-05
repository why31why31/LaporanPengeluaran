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
# Pastikan ID ini sesuai dengan file Google Sheets Bapak
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
# Masukkan ID Folder Google Drive Bapak di sini
DRIVE_FOLDER_ID = "MASUKKAN_ID_FOLDER_DRIVE_ANDA" 

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
        valueInputOption="USER_ENTERED", 
        insertDataOption="INSERT_ROWS", 
        body=body
    ).execute()

def upload_to_drive(file_content, file_name):
    service = get_gcp_service('drive', 'v3')
    file_metadata = {
        'name': file_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf')
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# --- 2. ANTARMUKA PENGGUNA ---
st.set_page_config(page_title="Sistem Laporan Wahyudi", layout="centered")

tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Pengeluaran Baru")
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama Personel", value="Wahyudi")
        tgl = st.date_input("Tanggal Maintenance", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan (Kilian/Romaco/Lainnya)")
        
        st.divider()
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        st.write("📂 **Lampiran Dokumen**")
        lebar_nota = st.slider("Atur Lebar Foto Nota di PDF (mm)", 50, 190, 150)
        
        bukti_files = st.file_uploader("📸 Upload Foto Nota (JPG/PNG)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
        report_file = st.file_uploader("📄 Upload Service Report (PDF)", type=['pdf'])
        
        submit = st.form_submit_button("Simpan ke Sheets & Google Drive")

    if submit:
        if not keperluan:
            st.error("Kolom Keperluan wajib diisi!")
        else:
            with st.spinner("Sedang memproses..."):
                try:
                    total = bensin + toll + makan + parkir
                    data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    # 1. Simpan ke Google Sheets
                    append_to_sheets(data_row)
                    
                    # 2. Buat PDF Utama
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                    pdf.line(10, 25, 200, 25)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(50, 8, " - Bensin", 0); pdf.cell(0, 8, f": Rp {bensin:,}", ln=True)
                    pdf.cell(50, 8, " - Toll", 0); pdf.cell(0, 8, f": Rp {toll:,}", ln=True)
                    pdf.cell(50, 8, " - Makan", 0); pdf.cell(0, 8, f": Rp {makan:,}", ln=True)
                    pdf.cell(50, 8, " - Parkir", 0); pdf.cell(0, 8, f": Rp {parkir:,}", ln=True)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(50, 10, "TOTAL BIAYA", 0); pdf.cell(0, 10, f": Rp {total:,}", ln=True)
                    
                    if bukti_files:
                        pdf.add_page()
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for f in bukti_files:
                            tmp_img = f"tmp_{f.name}"
                            with open(tmp_img, "wb") as img_f:
                                img_f.write(f.getbuffer())
                            pdf.image(tmp_img, x=10, w=lebar_nota)
                            os.remove(tmp_img)
                    
                    pdf_bytes = pdf.output()
                    
                    # 3. Gabungkan dengan PDF Report (jika ada)
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file:
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_buffer = io.BytesIO()
                    merger.write(final_buffer)
                    final_pdf_content = final_buffer.getvalue()
                    
                    # 4. Unggah ke Google Drive
                    nama_file_pdf = f"Laporan_{nama}_{tgl}.pdf"
                    upload_to_drive(final_pdf_content, nama_file_pdf)
                    
                    st.success("✅ Berhasil! Data di Sheets terupdate & File PDF tersimpan di Drive.")
                    st.download_button("📥 Download Copy PDF", final_pdf_content, nama_file_pdf, "application/pdf")
                
                except Exception as e:
                    st.error(f"Terjadi kesalahan: {e}")

with tab2:
    st.header("Laporan Kumulatif")
    st.write("Fitur ini menarik data dari Google Sheets.")
    # Kode laporan kumulatif Bapak bisa ditambahkan di sini nanti
