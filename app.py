import streamlit as st
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

# --- 1. KONFIGURASI ---
# Gunakan ID folder Anda (Pastikan Service Account sudah jadi EDITOR di folder ini)
FOLDER_ID_DRIVE = "1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX" 

# MASUKKAN EMAIL GMAIL PRIBADI ANDA DI SINI
EMAIL_PEMILIK_DRIVE = "why31why31@gmail.com"

def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name):
    service = get_drive_service()
    
    # Metadata file
    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID_DRIVE]
    }
    
    media = MediaFileUpload(file_path, resumable=True)
    
    # PROSES UPLOAD
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    file_id = file.get('id')

    # --- BAGIAN PENTING: MENGATASI QUOTA ERROR ---
    # Kita tambahkan izin 'writer' ke email Anda agar file 
    # langsung masuk ke jatah penyimpanan (kuota) akun Anda.
    try:
        permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': EMAIL_PEMILIK_DRIVE
        }
        service.permissions().create(
            fileId=file_id,
            body=permission,
            fields='id'
        ).execute()
    except Exception as e:
        st.warning(f"File terunggah, tapi gagal menyambungkan kuota: {e}")

    return file_id

# --- 2. ANTARMUKA (UI) ---
st.set_page_config(page_title="Form Pengeluaran Lapangan", layout="centered")

st.title("📂 Input Pengeluaran & Nota")
st.write("Laporan otomatis dikirim ke Google Drive dalam format PDF.")

with st.form("input_form", clear_on_submit=True):
    nama = st.text_input("Nama", value="Wahyudi")
    tgl = st.date_input("Tanggal", datetime.now())
    keperluan = st.text_area("Keperluan Kantor")
    
    st.divider()
    c1, c2 = st.columns(2)
    bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
    toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
    makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
    parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
    
    st.divider()
    bukti_files = st.file_uploader("📸 Ambil Foto Nota", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    
    submit = st.form_submit_button("Kirim ke Google Drive")

# --- 3. PROSES DATA ---
if submit:
    if not keperluan:
        st.error("Mohon isi bagian Keperluan!")
    else:
        with st.spinner("Sedang memproses laporan..."):
            try:
                total = bensin + toll + makan + parkir
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                pdf_name = f"Laporan_{nama}_{ts}.pdf"
                
                # Buat PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, "NOTA PENGELUARAN KANTOR", ln=True, align="C")
                pdf.ln(10)
                
                pdf.set_font("Arial", "", 12)
                data_list = [
                    ("Nama", nama), ("Tanggal", str(tgl)), ("Keperluan", keperluan),
                    ("-" * 30, "-" * 30),
                    ("Bensin", f"Rp {bensin:,}"), ("Toll", f"Rp {toll:,}"),
                    ("Makan", f"Rp {makan:,}"), ("Parkir", f"Rp {parkir:,}"),
                    ("TOTAL", f"Rp {total:,}")
                ]
                
                for label, val in data_list:
                    pdf.cell(50, 10, label, 0)
                    pdf.cell(0, 10, f": {val}", 0, ln=True)
                
                # Tambahkan Foto
                if bukti_files:
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "LAMPIRAN BUKTI", ln=True)
                    for f in bukti_files:
                        tmp = f"tmp_{f.name}"
                        with open(tmp, "wb") as file_tmp:
                            file_tmp.write(f.getbuffer())
                        pdf.image(tmp, x=10, w=100)
                        pdf.ln(5)
                        os.remove(tmp)
                
                pdf.output(pdf_name)
                
                # Upload ke Drive
                upload_to_drive(pdf_name, pdf_name)
                
                st.success(f"✅ Berhasil! File '{pdf_name}' sudah ada di Drive.")
                st.balloons()
                os.remove(pdf_name)
                
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")
