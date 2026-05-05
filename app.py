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
DRIVE_FOLDER_ID = "1ITsQrx3hQe6XxSWs_j7G8t7pmFKdwZoX"
EMAIL_OWNER = "why31why31@gmail.com" # <--- GANTI DENGAN EMAIL BAPAK

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
        if not values: return pd.DataFrame()
        return pd.DataFrame(values[1:], columns=values[0])
    except:
        return pd.DataFrame()

def upload_to_drive(file_content, file_name):
    try:
        service = get_gcp_service('drive', 'v3')
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/pdf', resumable=False)
        
        # Buat file
        file = service.files().create(body=file_metadata, media_body=media, fields='id', supportsAllDrives=True).execute()
        file_id = file.get('id')
        
        # Coba pindahkan kepemilikan agar tidak memakan kuota Service Account
        try:
            permission = {'type': 'user', 'role': 'owner', 'emailAddress': EMAIL_OWNER}
            service.permissions().create(fileId=file_id, body=permission, transferOwnership=True, supportsAllDrives=True).execute()
        except:
            # Jika gagal transfer owner (biasanya karena kebijakan admin), file tetap ada di folder
            pass
        return file_id
    except Exception as e:
        st.warning(f"File gagal diunggah otomatis ke Drive (Error: {e}), silakan download manual di bawah.")
        return None

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Sistem Laporan Asep Wahyu", layout="centered")

# Tab didefinisikan di level paling atas agar tidak hilang
tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

# --- TAB 1: INPUT ---
with tab1:
    st.header("Input Data Pengeluaran")
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama Personel", value="Asep Wahyu")
        tgl_input = st.date_input("Tanggal", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan")
        
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        bukti_files = st.file_uploader("📸 Upload Foto Nota", accept_multiple_files=True, type=['jpg','jpeg','png'])
        report_file = st.file_uploader("📄 Upload PDF Service Report", type=['pdf'])
        
        submit = st.form_submit_button("💾 Simpan & Buat PDF")

    if submit:
        if not keperluan:
            st.error("Detail Pekerjaan wajib diisi!")
        else:
            with st.spinner("Sedang memproses..."):
                try:
                    total = bensin + toll + makan + parkir
                    # Perbaikan format tanggal agar dibaca 'Date' oleh Sheets
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    data_row = [tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets(data_row)
                    
                    # 2. Buat PDF
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA", ln=True, align="C")
                    pdf.line(10, 25, 200, 25)
                    pdf.ln(10)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 8, f"Tanggal: {tgl_iso}", ln=True)
                    pdf.cell(0, 8, f"Oleh: {nama}", ln=True)
                    pdf.cell(0, 8, f"Keperluan: {keperluan}", ln=True)
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 8, f"Total Pengeluaran: Rp {total:,}", ln=True)
                    
                    # Lampiran Foto
                    if bukti_files:
                        pdf.add_page()
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for f in bukti_files:
                            tmp = f"tmp_{f.name}"
                            with open(tmp, "wb") as img_f: img_f.write(f.getbuffer())
                            pdf.image(tmp, x=10, w=160)
                            os.remove(tmp)
                    
                    pdf_bytes = pdf.output()
                    
                    # 3. Gabung dengan Report PDF
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file: merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    content = final_pdf.getvalue()
                    
                    # 4. Upload ke Drive
                    upload_to_drive(content, f"Laporan_{nama}_{tgl_iso}.pdf")
                    
                    st.success(f"✅ Data tersimpan di Sheets & PDF diunggah ke Drive.")
                    st.download_button("📥 Download Copy PDF", content, f"Laporan_{tgl_iso}.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"Gagal: {e}")

# --- TAB 2: KUMULATIF ---
with tab2:
    st.header("Rekap Pengeluaran")
    tgl_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.now(), datetime.now()), key="range_lap")
    
    if st.button("🔍 Tampilkan Data"):
        df = get_all_data()
        if not df.empty:
            # Konversi kolom tanggal ke format datetime agar bisa difilter
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce').dt.date
            if len(tgl_range) == 2:
                start, end = tgl_range
                df_filtered = df[(df['Tanggal'] >= start) & (df['Tanggal'] <= end)]
                if not df_filtered.empty:
                    st.dataframe(df_filtered, use_container_width=True)
                    # Menghitung Grand Total
                    df_filtered['Total'] = pd.to_numeric(df_filtered['Total'], errors='coerce').fillna(0)
                    st.info(f"**Total Pengeluaran Periode Ini: Rp {df_filtered['Total'].sum():,}**")
                else:
                    st.warning("Data tidak ditemukan pada rentang tanggal ini.")
        else:
            st.error("Database Sheets kosong atau tidak dapat diakses.")
