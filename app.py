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
st.set_page_config(page_title="Laporan Maintenance Wahyudi", layout="wide")

tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Data Pengeluaran")
    
    # Gunakan Columns agar layout input lebih efisien
    with st.form("main_form"):
        col_id1, col_id2 = st.columns(2)
        nama = col_id1.text_input("Nama Personel", value="Wahyudi")
        tgl_input = col_id2.date_input("Tanggal Maintenance", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan (Kilian/Romaco/Lainnya)")
        
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        bensin = c1.number_input("Bensin (Rp)", min_value=0, step=1000)
        toll = c2.number_input("Toll (Rp)", min_value=0, step=1000)
        makan = c3.number_input("Makan (Rp)", min_value=0, step=1000)
        parkir = c4.number_input("Parkir (Rp)", min_value=0, step=1000)
        
        st.divider()
        st.write("📂 **Lampiran Dokumen**")
        lebar_nota = st.slider("Atur Lebar Foto Nota di PDF (mm)", 50, 190, 150)
        bukti_files = st.file_uploader("📸 Upload Foto Nota", accept_multiple_files=True, type=['jpg','jpeg','png'])
        report_file = st.file_uploader("📄 Upload PDF Service Report", type=['pdf'])
        
        col_btn1, col_btn2 = st.columns(2)
        btn_preview = col_btn1.form_submit_button("🔍 LIHAT PREVIEW")
        btn_submit = col_btn2.form_submit_button("💾 SIMPAN & CETAK PDF")

    # --- LOGIKA PREVIEW YANG DIMAKSIMALKAN ---
    if btn_preview:
        st.markdown("---")
        st.subheader("📄 Preview Hasil Cetak")
        
        # Simulasi tampilan kertas PDF menggunakan container & border
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>LAPORAN KERJA & BIAYA LAPANGAN</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; border-bottom: 2px solid black; padding-bottom:10px;'>Departemen Maintenance Teknik</p>", unsafe_allow_html=True)
            
            col_pre1, col_pre2 = st.columns(2)
            col_pre1.write(f"**Tanggal:** {tgl_input}")
            col_pre2.write(f"**Oleh:** {nama}")
            st.write(f"**Detail Pekerjaan:** {keperluan}")
            
            st.write("---")
            st.write("**Rincian Biaya:**")
            
            # Tabel Preview agar sama dengan struktur data
            total_val = bensin + toll + makan + parkir
            preview_data = {
                "Kategori": ["Bensin", "Toll", "Makan", "Parkir", "TOTAL"],
                "Jumlah (Rp)": [f"{bensin:,}", f"{toll:,}", f"{makan:,}", f"{parkir:,}", f"**{total_val:,}**"]
            }
            st.table(pd.DataFrame(preview_data))
            
            if bukti_files:
                st.write("**Lampiran Nota:**")
                # Menampilkan preview gambar dengan lebar yang disesuaikan slider
                for f in bukti_files:
                    st.image(f, caption=f.name, width=int(lebar_nota * 3)) # Skala mm ke px
        
        st.info("💡 Periksa kembali detail di atas. Jika sudah sesuai, klik tombol **SIMPAN & CETAK PDF**.")

    # --- LOGIKA SUBMIT ---
    if btn_submit:
        if not keperluan:
            st.error("Detail Pekerjaan wajib diisi!")
        else:
            with st.spinner("Menyimpan ke Sheets..."):
                try:
                    total = bensin + toll + makan + parkir
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    data_row = [tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total]
                    
                    append_to_sheets(data_row)
                    
                    # Generate PDF (Kop & Tabel)
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 5, "Departemen Maintenance Teknik", ln=True, align="C")
                    pdf.line(10, 30, 200, 30)
                    pdf.ln(15)
                    
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 8, f"Tanggal: {tgl_iso}", ln=True)
                    pdf.cell(0, 8, f"Oleh: {nama}", ln=True)
                    pdf.cell(0, 8, f"Detail: {keperluan}", ln=True)
                    pdf.ln(10)
                    
                    # Tabel Biaya di PDF
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(100, 10, "Kategori", 1); pdf.cell(60, 10, "Jumlah (Rp)", 1, ln=True)
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(100, 10, "Bensin", 1); pdf.cell(60, 10, f"{bensin:,}", 1, ln=True)
                    pdf.cell(100, 10, "Toll", 1); pdf.cell(60, 10, f"{toll:,}", 1, ln=True)
                    pdf.cell(100, 10, "Makan", 1); pdf.cell(60, 10, f"{makan:,}", 1, ln=True)
                    pdf.cell(100, 10, "Parkir", 1); pdf.cell(60, 10, f"{parkir:,}", 1, ln=True)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(100, 10, "TOTAL", 1); pdf.cell(60, 10, f"{total:,}", 1, ln=True)
                    
                    if bukti_files:
                        pdf.add_page()
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for f in bukti_files:
                            tmp = f"tmp_{f.name}"
                            with open(tmp, "wb") as img_f: img_f.write(f.getbuffer())
                            pdf.image(tmp, x=10, w=lebar_nota)
                            os.remove(tmp)
                    
                    pdf_bytes = pdf.output()
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file: merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    
                    st.success("✅ Berhasil disimpan!")
                    st.download_button(
                        label="📥 Download Hasil Cetak PDF",
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
                    st.info(f"**Grand Total Periode Ini: Rp {df_filtered['Total'].sum():,}**")
