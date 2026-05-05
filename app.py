import streamlit as st
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter, PdfReader
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
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
st.set_page_config(page_title="Input Laporan Asep Wahyu", layout="centered")
st.title("📊 Rekap Pengeluaran & Service Report")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama Personel", value="Asep Wahyu")
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
    
    # SLIDER UNTUK MENGATUR UKURAN NOTA (Fitur Baru)
    lebar_nota = st.slider("Atur Lebar Foto Nota di PDF (mm)", 50, 190, 150)
    
    bukti_files = st.file_uploader("📸 Upload Foto Nota (JPG/PNG)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    report_file = st.file_uploader("📄 Upload Service Report (PDF)", type=['pdf'])
    
    submit = st.form_submit_button("Simpan & Buat Laporan")

# --- 3. PROSES DATA ---
if submit:
    if not keperluan:
        st.error("Isi detail pekerjaan!")
    else:
        with st.spinner("Memproses..."):
            try:
                total = bensin + toll + makan + parkir
                data_row = [str(tgl), nama, keperluan, bensin, toll, makan, parkir, total]
                
                # A. SIMPAN KE SHEETS
                append_to_sheets(data_row)
                
                # B. BUAT PDF UTAMA
                pdf_utama = FPDF()
                pdf_utama.add_page()
                
                # Kop Surat Profesional
                pdf_utama.set_font("Arial", "B", 14)
                pdf_utama.cell(0, 7, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                pdf_utama.set_font("Arial", "", 10)
                pdf_utama.cell(0, 5, f"Oleh: {nama} | Tanggal: {tgl}", ln=True, align="C")
                pdf_utama.line(10, 25, 200, 25)
                pdf_utama.ln(10)
                
                # Ringkasan Biaya
                pdf_utama.set_font("Arial", "B", 12)
                pdf_utama.cell(0, 10, "Ringkasan Pengeluaran:", ln=True)
                pdf_utama.set_font("Arial", "", 12)
                pdf_utama.cell(0, 8, f"- Total Biaya: Rp {total:,}", ln=True)
                pdf_utama.ln(5)
                
                # Lampiran Foto dengan Ukuran yang Diatur
                if bukti_files:
                    pdf_utama.add_page()
                    pdf_utama.set_font("Arial", "B", 12)
                    pdf_utama.cell(0, 10, "LAMPIRAN FOTO NOTA:", ln=True)
                    pdf_utama.ln(5)
                    
                    for f in bukti_files:
                        tmp_img = f"tmp_{f.name}"
                        with open(tmp_img, "wb") as img_f:
                            img_f.write(f.getbuffer())
                        
                        # MENGGUNAKAN VARIABEL lebar_nota DARI SLIDER
                        pdf_utama.image(tmp_img, x=10, w=lebar_nota)
                        pdf_utama.ln(10)
                        os.remove(tmp_img)
                
                pdf_bytes = pdf_utama.output()
                
                # C. GABUNGKAN DENGAN PDF REPORT
                merger = PdfWriter()
                merger.append(io.BytesIO(pdf_bytes))
                
                if report_file:
                    merger.append(io.BytesIO(report_file.read()))
                
                final_buffer = io.BytesIO()
                merger.write(final_buffer)
                
                st.success("✅ Data tersimpan di Google Sheets!")
                st.download_button(
                    label="📥 Download Laporan Akhir",
                    data=final_buffer.getvalue(),
                    file_name=f"Laporan_{nama}_{tgl}.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Gagal: {e}")
