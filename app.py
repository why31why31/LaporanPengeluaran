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

# --- 1. KONFIGURASI API ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
DRIVE_FOLDER_ID = "1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX"

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

def get_all_data():
    try:
        service = get_gcp_service('sheets', 'v4')
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A:H").execute()
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
        # Membuat DataFrame dan membersihkan spasi pada header
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception:
        return pd.DataFrame()

def upload_to_drive(file_content, file_name):
    try:
        service = get_gcp_service('drive', 'v3')
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf', resumable=False)
        service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
    except Exception as e:
        st.warning(f"Gagal simpan ke Drive (tetap tersimpan di Sheets): {e}")

# --- 2. Tampilan Aplikasi ---
st.set_page_config(page_title="Laporan Maintenance Wahyudi", layout="centered")

# Inisialisasi Tab agar tidak hilang
tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

# --- TAB 1: INPUT ---
with tab1:
    st.header("Input Data Maintenance")
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama Personel", value="Wahyudi")
        tgl_input = st.date_input("Tanggal Maintenance", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan")
        
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        bukti_files = st.file_uploader("📸 Foto Nota", accept_multiple_files=True, type=['jpg','jpeg','png'])
        report_file = st.file_uploader("📄 Service Report (PDF)", type=['pdf'])
        
        submit = st.form_submit_button("Simpan Data & Buat PDF")

    if submit:
        if not keperluan:
            st.error("Kolom Keperluan wajib diisi!")
        else:
            with st.spinner("Sedang memproses..."):
                try:
                    total = bensin + toll + makan + parkir
                    # FORMAT TANGGAL: Menggunakan format YYYY-MM-DD agar Sheets mengenalinya sebagai Date
                    tgl_fix = tgl_input.strftime('%Y-%m-%d')
                    data_row = [tgl_fix, nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets(data_row)
                    
                    # 2. Buat PDF Dasar
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA", ln=True, align="C")
                    pdf.ln(10)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 10, f"Tanggal: {tgl_fix}", ln=True)
                    pdf.cell(0, 10, f"Keperluan: {keperluan}", ln=True)
                    pdf.cell(0, 10, f"Total Biaya: Rp {total:,}", ln=True)
                    
                    # Lampirkan foto jika ada
                    if bukti_files:
                        pdf.add_page()
                        for f in bukti_files:
                            tmp_img = f"tmp_{f.name}"
                            with open(tmp_img, "wb") as img_f:
                                img_f.write(f.getbuffer())
                            pdf.image(tmp_img, x=10, w=150)
                            os.remove(tmp_img)
                    
                    pdf_bytes = pdf.output()
                    
                    # 3. Gabung PDF jika ada report
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file:
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    content = final_pdf.getvalue()
                    
                    # 4. Simpan ke Drive
                    upload_to_drive(content, f"Laporan_{nama}_{tgl_fix}.pdf")
                    
                    st.success(f"✅ Berhasil! Data tanggal {tgl_fix} tersimpan.")
                    st.download_button("📥 Download PDF", content, f"Laporan_{tgl_fix}.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- TAB 2: KUMULATIF ---
with tab2:
    st.header("Rekap Laporan Per Periode")
    tgl_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.now(), datetime.now()), key="range_laporan")
    
    if st.button("Tampilkan Rekap"):
        df = get_all_data()
        if not df.empty:
            # Konversi kolom tanggal agar bisa difilter
            df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.date
            
            if len(tgl_range) == 2:
                mulai, selesai = tgl_range
                mask = (df['Tanggal'] >= mulai) & (df['Tanggal'] <= selesai)
                df_filtered = df.loc[mask]
                
                if not df_filtered.empty:
                    st.dataframe(df_filtered, use_container_width=True)
                    # Tombol download csv sederhana sebagai opsi tambahan
                    csv = df_filtered.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Excel/CSV", csv, "rekap.csv", "text/csv")
                else:
                    st.warning("Tidak ada data pada rentang tanggal tersebut.")
