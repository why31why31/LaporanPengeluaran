import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os

# --- 1. KONFIGURASI ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"

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
        headers = [h.strip() for h in values[0]]
        return pd.DataFrame(values[1:], columns=headers)
    except:
        return pd.DataFrame()

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Laporan Maintenance Wahyudi", layout="centered")

tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Data Pengeluaran")
    
    with st.form("main_form"):
        nama = st.text_input("Nama Personel", value="Wahyudi")
        tgl_input = st.date_input("Tanggal Maintenance", datetime.now())
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
        bukti_files = st.file_uploader("📸 Upload Foto Nota", accept_multiple_files=True, type=['jpg','jpeg','png'])
        report_file = st.file_uploader("📄 Upload PDF Service Report", type=['pdf'])
        
        # Menggunakan kolom untuk tombol Preview dan Simpan
        col_btn1, col_btn2 = st.columns(2)
        btn_preview = col_btn1.form_submit_button("🔍 Preview Dulu")
        btn_submit = col_btn2.form_submit_button("💾 Simpan & Buat PDF")

    # --- LOGIKA PREVIEW ---
    if btn_preview:
        st.subheader("👀 Preview Laporan")
        total_preview = bensin + toll + makan + parkir
        st.write(f"**Tanggal:** {tgl_input}")
        st.write(f"**Keperluan:** {keperluan}")
        st.write(f"**Rincian Biaya:** Rp {total_preview:,}")
        
        if bukti_files:
            st.write(f"📸 {len(bukti_files)} Foto Nota terlampir.")
            for f in bukti_files:
                st.image(f, width=200)
        if report_file:
            st.write("📄 Service Report PDF terlampir.")
        
        st.info("Jika data sudah benar, silakan klik tombol **Simpan & Buat PDF** di atas.")

    # --- LOGIKA SUBMIT ---
    if btn_submit:
        if not keperluan:
            st.error("Detail Pekerjaan wajib diisi!")
        else:
            with st.spinner("Menyimpan data..."):
                try:
                    total = bensin + toll + makan + parkir
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    data_row = [tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    append_to_sheets(data_row)
                    
                    # Generate PDF
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                    pdf.line(10, 25, 200, 25)
                    pdf.ln(10)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 8, f"Tanggal: {tgl_iso}", ln=True)
                    pdf.cell(0, 8, f"Oleh: {nama}", ln=True)
                    pdf.cell(0, 8, f"Detail: {keperluan}", ln=True)
                    pdf.cell(0, 8, f"Total: Rp {total:,}", ln=True)
                    
                    if bukti_files:
                        pdf.add_page()
                        for f in bukti_files:
                            tmp = f"tmp_{f.name}"
                            with open(tmp, "wb") as img_f: img_f.write(f.getbuffer())
                            pdf.image(tmp, x=10, w=lebar_nota)
                            os.remove(tmp)
                    
                    pdf_bytes = pdf.output()
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file: 
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    
                    st.success("✅ Data berhasil disimpan!")
                    st.download_button(
                        label="📥 Download Laporan PDF",
                        data=final_pdf.getvalue(),
                        file_name=f"Laporan_{nama}_{tgl_iso}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Gagal: {e}")

# --- TAB 2: KUMULATIF ---
with tab2:
    st.header("Rekap Pengeluaran")
    tgl_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.now(), datetime.now()), key="range_lap")
    
    if st.button("🔍 Tampilkan Rekap"):
        df = get_all_data()
        if not df.empty:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce').dt.date
            if len(tgl_range) == 2:
                start, end = tgl_range
                df_filtered = df[(df['Tanggal'] >= start) & (df['Tanggal'] <= end)]
                if not df_filtered.empty:
                    st.dataframe(df_filtered, use_container_width=True)
                    df_filtered['Total'] = pd.to_numeric(df_filtered['Total'], errors='coerce').fillna(0)
                    st.info(f"**Total Pengeluaran Periode Ini: Rp {df_filtered['Total'].sum():,}**")
