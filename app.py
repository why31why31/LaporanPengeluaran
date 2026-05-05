import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# --- KONFIGURASI GOOGLE DRIVE ---
# Folder ID didapat dari URL folder Google Drive Anda
FOLDER_ID_DRIVE = "https://drive.google.com/drive/folders/1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX?usp=drive_link"

def get_drive_service():
    # Mengambil kunci rahasia dari Streamlit Secrets (aman untuk GitHub)
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name):
    service = get_drive_service()
    file_metadata = {'name': file_name, 'parents': [FOLDER_ID_DRIVE]}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- UI APP ---
st.set_page_config(page_title="Input Pengeluaran Wahyudi", layout="centered")

st.title("🚀 Form Pengeluaran Lapangan")
st.write("Input pengeluaran langsung dari HP ke Google Drive.")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Asep Wahyu")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan")
    
    st.divider()
    col1, col2 = st.columns(2)
    bensin = col1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = col2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = col1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = col2.number_input("Parkir/Lainnya (Rp)", min_value=0, step=1000)
    
    st.divider()
    bukti_files = st.file_uploader("📸 Foto Nota/Bukti", accept_multiple_files=True, type=['jpg', 'jpeg', 'png','pdf'])
    
    submit = st.form_submit_button("Simpan ke Google Drive")

if submit:
    if not keperluan:
        st.error("Mohon isi kolom Keperluan!")
    else:
        with st.spinner("Sedang memproses laporan..."):
            total = bensin + toll + makan + parkir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_name = f"Nota_{nama}_{timestamp}.pdf"
            
            # 1. Generate PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "LAPORAN PENGELUARAN", ln=True, align="C")
            pdf.set_font("Arial", "", 12)
            pdf.ln(10)
            
            data_pdf = [
                ("Nama", nama), ("Tanggal", str(tgl)), ("Keperluan", keperluan),
                ("Bensin", f"Rp {bensin:,}"), ("Toll", f"Rp {toll:,}"),
                ("Makan", f"Rp {makan:,}"), ("Parkir", f"Rp {parkir:,}"),
                ("TOTAL", f"Rp {total:,}")
            ]
            
            for label, val in data_pdf:
                pdf.cell(50, 10, label, 1)
                pdf.cell(0, 10, f" {val}", 1, ln=True)
            
            # 2. Tambahkan Foto ke PDF
            if bukti_files:
                pdf.add_page()
                pdf.cell(0, 10, "LAMPIRAN BUKTI:", ln=True)
                for uploaded_file in bukti_files:
                    temp_path = f"temp_{uploaded_file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    pdf.image(temp_path, x=10, w=100)
                    pdf.ln(5)
                    os.remove(temp_path) # Hapus file sementara
            
            pdf.output(pdf_name)
            
            # 3. Upload ke Google Drive
            try:
                drive_id = upload_to_drive(pdf_name, pdf_name)
                st.success(f"✅ Berhasil! File telah tersimpan di Google Drive.")
                st.balloons()
                os.remove(pdf_name) # Bersihkan server cloud
            except Exception as e:
                st.error(f"Gagal upload ke Drive: {e}")
