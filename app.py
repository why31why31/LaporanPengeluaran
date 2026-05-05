import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os

# --- 1. KONFIGURASI GOOGLE SHEETS ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 

def get_sheets_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('sheets', 'v4', credentials=creds)

def get_all_data():
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A:H").execute()
    values = result.get('values', [])
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])

def append_to_sheets(data):
    service = get_sheets_service()
    body = {'values': [data]}
    # Gunakan .append agar data baru masuk ke baris kosong paling bawah (tidak menimpa)
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Pengeluaran!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()

# --- 2. ANTARMUKA PENGGUNA (TABS) ---
st.set_page_config(page_title="Sistem Laporan Asep Wahyu", layout="centered")

# Memastikan ada dua Tab: Input Harian dan Laporan Kumulatif
tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

# --- TAB 1: INPUT HARIAN ---
with tab1:
    st.header("Input Pengeluaran Baru")
    with st.form("main_form", clear_on_submit=True):
        nama_input = st.text_input("Nama Personel", value="Asep Wahyu")
        tgl_input = st.date_input("Tanggal Maintenance", datetime.now())
        keperluan_input = st.text_area("Detail Pekerjaan (Kilian/Romaco/Lainnya)")
        
        st.divider()
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c1.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c2.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        st.write("📂 **Lampiran Dokumen**")
        lebar_nota = st.slider("Atur Lebar Foto Nota di PDF (mm)", 50, 190, 150)
        
        # Tombol Upload Nota (Foto)
        bukti_files = st.file_uploader("📸 Upload Foto Nota (JPG/PNG)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
        # Tombol Upload Service Report (PDF)
        report_file = st.file_uploader("📄 Upload Service Report (PDF)", type=['pdf'])
        
        submit = st.form_submit_button("Simpan Data & Buat Laporan")

    if submit:
        if not keperluan_input:
            st.error("Isi detail pekerjaan!")
        else:
            with st.spinner("Memproses data..."):
                try:
                    total = bensin + toll + makan + parkir
                    data_row = [str(tgl_input), nama_input, keperluan_input, bensin, toll, makan, parkir, total]
                    
                    # 1. Simpan ke Sheets (Menambah ke bawah)
                    append_to_sheets(data_row)
                    
                    # 2. Buat PDF Rincian
                    pdf_utama = FPDF()
                    pdf_utama.add_page()
                    pdf_utama.set_font("Arial", "B", 14)
                    pdf_utama.cell(0, 10, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                    pdf_utama.line(10, 25, 200, 25)
                    pdf_utama.ln(10)
                    
                    pdf_utama.set_font("Arial", "", 12)
                    pdf_utama.cell(50, 8, " - Bensin", 0); pdf_utama.cell(0, 8, f": Rp {bensin:,}", ln=True)
                    pdf_utama.cell(50, 8, " - Toll", 0); pdf_utama.cell(0, 8, f": Rp {toll:,}", ln=True)
                    pdf_utama.cell(50, 8, " - Makan", 0); pdf_utama.cell(0, 8, f": Rp {makan:,}", ln=True)
                    pdf_utama.cell(50, 8, " - Parkir", 0); pdf_utama.cell(0, 8, f": Rp {parkir:,}", ln=True)
                    pdf_utama.set_font("Arial", "B", 12)
                    pdf_utama.cell(50, 10, "TOTAL BIAYA", 0); pdf_utama.cell(0, 10, f": Rp {total:,}", ln=True)
                    
                    # 3. Tambahkan Foto Nota ke PDF Utama
                    if bukti_files:
                        pdf_utama.add_page()
                        pdf_utama.cell(0, 10, "LAMPIRAN FOTO NOTA:", ln=True)
                        for f in bukti_files:
                            tmp_img = f"tmp_{f.name}"
                            with open(tmp_img, "wb") as img_f:
                                img_f.write(f.getbuffer())
                            pdf_utama.image(tmp_img, x=10, w=lebar_nota)
                            pdf_utama.ln(10)
                            os.remove(tmp_img)
                    
                    pdf_bytes = pdf_utama.output()
                    
                    # 4. Gabungkan dengan Service Report (PDF)
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file:
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_buffer = io.BytesIO()
                    merger.write(final_buffer)
                    
                    st.success("✅ Data tersimpan di baris baru!")
                    st.download_button(
                        label="📥 Download Laporan Lengkap",
                        data=final_buffer.getvalue(),
                        file_name=f"Laporan_{tgl_input}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Gagal: {e}")

# --- TAB 2: LAPORAN KUMULATIF ---
with tab2:
    st.header("Generate Laporan Per Periode")
    tgl_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.now(), datetime.now()), key="range_laporan")
    
    if len(tgl_range) == 2:
        tgl_mulai, tgl_selesai = tgl_range
        if st.button("Siapkan PDF Kumulatif"):
            df = get_all_data()
            if not df.empty:
                df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.date
                mask = (df['Tanggal'] >= tgl_mulai) & (df['Tanggal'] <= tgl_selesai)
                df_filtered = df.loc[mask]
                
                if not df_filtered.empty:
                    st.dataframe(df_filtered)
                    
                    pdf_kom = FPDF()
                    pdf_kom.add_page()
                    pdf_kom.set_font("Arial", "B", 14)
                    pdf_kom.cell(0, 10, f"REKAP {tgl_mulai} - {tgl_selesai}", ln=True, align="C")
                    
                    pdf_output = bytes(pdf_kom.output())
                    st.download_button("📥 Download Rekap Kumulatif", pdf_output, f"Rekap_{tgl_mulai}.pdf", "application/pdf")
                else:
                    st.warning("Tidak ada data ditemukan.")
