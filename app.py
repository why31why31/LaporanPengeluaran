import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# --- 1. KONFIGURASI GOOGLE DRIVE ---
# Masukkan ID Folder dari URL Google Drive Anda
FOLDER_ID_DRIVE = "1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX" 

def get_drive_service():
    # Mengambil kunci dari Streamlit Secrets
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name):
    service = get_drive_service()
    
    # Metadata file
    file_metadata = {
        'name': Laporan_Pengeluaran,
        'parents': [FOLDER_ID_DRIVE]
    }
    
    # Media upload
    media = MediaFileUpload(file_path, resumable=True)
    
    # PROSES UPLOAD
    # Kita mengunggah file ke folder yang sudah Anda bagikan sebelumnya
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    file_id = file.get('id')

    # MEMBERI IZIN AKSES (Agar file terbaca di kuota pemilik folder)
    # Ganti 'email_pribadi_anda@gmail.com' dengan email Gmail Anda
    user_permission = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': 'email_pribadi_anda@gmail.com' 
    }
    
    service.permissions().create(
        fileId=file_id,
        body=user_permission,
        fields='id'
    ).execute()

    return file_id
# --- 2. ANTARMUKA PENGGUNA (UI) ---
st.set_page_config(page_title="Input Pengeluaran Wahyudi", layout="centered")

st.title("📝 Form Pengeluaran Lapangan")
st.info("Input data & foto bukti akan otomatis dikonversi ke PDF dan dikirim ke Google Drive.")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Wahyudi")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan Kantor", placeholder="Misal: Maintenance rutin Kilian Tablet Press")
    
    st.divider()
    col1, col2 = st.columns(2)
    bensin = col1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = col2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = col1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = col2.number_input("Parkir/Lainnya (Rp)", min_value=0, step=1000)
    
    st.divider()
    bukti_files = st.file_uploader("📸 Lampirkan Bukti (Foto/Nota)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    
    submit = st.form_submit_button("Kirim Laporan ke Drive")

# --- 3. LOGIKA PEMROSESAN ---
if submit:
    if not keperluan:
        st.error("Kolom Keperluan wajib diisi!")
    else:
        with st.spinner("Sedang menyusun PDF dan mengunggah..."):
            try:
                total = bensin + toll + makan + parkir
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pdf_name = f"Nota_{nama}_{timestamp}.pdf"
                
                # Buat Dokumen PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "NOTA PENGELUARAN KANTOR", ln=True, align="C")
                pdf.ln(10)
                
                pdf.set_font("Arial", "", 12)
                rincian = [
                    ("Nama", nama), ("Tanggal", str(tgl)), ("Keperluan", keperluan),
                    ("-" * 20, "-" * 20),
                    ("Bensin", f"Rp {bensin:,}"), ("Toll", f"Rp {toll:,}"),
                    ("Makan", f"Rp {makan:,}"), ("Parkir", f"Rp {parkir:,}"),
                    ("TOTAL", f"Rp {total:,}")
                ]
                
                for label, val in rincian:
                    pdf.cell(50, 10, label, 0)
                    pdf.cell(0, 10, f": {val}", 0, ln=True)
                
                # Tambahkan Lampiran Foto ke PDF
                if bukti_files:
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "LAMPIRAN BUKTI", ln=True)
                    pdf.ln(5)
                    
                    for uploaded_file in bukti_files:
                        temp_path = f"temp_{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        # Ukuran gambar disesuaikan agar pas di PDF
                        pdf.image(temp_path, x=10, w=100)
                        pdf.ln(10)
                        os.remove(temp_path) 
                
                pdf.output(pdf_name)
                
                # Upload ke Google Drive
                upload_to_drive(pdf_name, pdf_name)
                
                st.success(f"✅ Berhasil! Laporan '{pdf_name}' sudah tersimpan di Google Drive.")
                st.balloons()
                os.remove(pdf_name) # Hapus file di server cloud agar bersih
                
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
