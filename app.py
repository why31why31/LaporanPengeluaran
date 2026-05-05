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
    
    with st.form("main_form"):
        # Bagian Atas: Identitas & Kop
        st.write("🏢 **Identitas & Kop Surat**")
        col_kop1, col_kop2 = st.columns([1, 2])
        logo_file = col_kop1.file_uploader("Upload Gambar Kop/Logo", type=['jpg','jpeg','png'])
        lebar_kop = col_kop2.slider("Atur Lebar Kop di PDF (mm)", 50, 190, 190)
        
        st.divider()
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

    # --- LOGIKA PREVIEW ---
    if btn_preview:
        st.markdown("---")
        with st.container(border=True):
            # Header Gambar di Preview
            if logo_file:
                st.image(logo_file, width=int(lebar_kop * 3))
            else:
                st.markdown("<h2 style='text-align: center;'>LAPORAN KERJA & BIAYA</h2>", unsafe_allow_html=True)
            
            st.markdown("<hr style='border: 1px solid black;'>", unsafe_allow_html=True)
            
            p_col1, p_col2 = st.columns(2)
            p_col1.write(f"**Tanggal:** {tgl_input}")
            p_col2.write(f"**Oleh:** {nama}")
            st.write(f"**Detail:** {keperluan}")
            
            total_val = bensin + toll + makan + parkir
            prev_df = pd.DataFrame({
                "Item": ["Bensin", "Toll", "Makan", "Parkir", "TOTAL"],
                "Biaya (Rp)": [f"{bensin:,}", f"{toll:,}", f"{makan:,}", f"{parkir:,}", f"**{total_val:,}**"]
            })
            st.table(prev_df)
            
            if bukti_files:
                st.write("**Lampiran Nota:**")
                for f in bukti_files:
                    st.image(f, width=int(lebar_nota * 2.5))
        st.info("💡 Cek preview di atas. Jika sudah pas, klik **SIMPAN & CETAK PDF**.")

    # --- LOGIKA SUBMIT ---
    if btn_submit:
        if not keperluan:
            st.error("Detail Pekerjaan wajib diisi!")
        else:
            with st.spinner("Sedang memproses..."):
                try:
                    total = bensin + toll + makan + parkir
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets([tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total])
                    
                    # 2. Buat PDF
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Cek Kop Gambar
                    if logo_file:
                        tmp_kop = f"kop_{logo_file.name}"
                        with open(tmp_kop, "wb") as f_kop: f_kop.write(logo_file.getbuffer())
                        # Posisikan Kop di Tengah
                        pdf.image(tmp_kop, x=(210-lebar_kop)/2, y=10, w=lebar_kop)
                        pdf.ln(lebar_kop/3 + 5) # Spasi dinamis berdasarkan tinggi logo
                        os.remove(tmp_kop)
                    else:
                        pdf.set_font("Arial", "B", 16)
                        pdf.cell(0, 10, "LAPORAN KERJA & BIAYA LAPANGAN", ln=True, align="C")
                    
                    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", "", 12)
                    pdf.cell(0, 8, f"Tanggal: {tgl_iso}", ln=True)
                    pdf.cell(0, 8, f"Oleh: {nama}", ln=True)
                    pdf.cell(0, 8, f"Pekerjaan: {keperluan}", ln=True)
                    pdf.ln(5)
                    
                    # Tabel Biaya
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(100, 10, "Kategori", 1); pdf.cell(60, 10, "Jumlah (Rp)", 1, ln=True)
                    pdf.set_font("Arial", "", 11)
                    pdf.cell(100, 8, "Bensin", 1); pdf.cell(60, 8, f"{bensin:,}", 1, ln=True)
                    pdf.cell(100, 8, "Toll", 1); pdf.cell(60, 8, f"{toll:,}", 1, ln=True)
                    pdf.cell(100, 8, "Makan", 1); pdf.cell(60, 8, f"{makan:,}", 1, ln=True)
                    pdf.cell(100, 8, "Parkir", 1); pdf.cell(60, 8, f"{parkir:,}", 1, ln=True)
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(100, 10, "TOTAL", 1); pdf.cell(60, 10, f"{total:,}", 1, ln=True)
                    
                    if bukti_files:
                        pdf.add_page()
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for f in bukti_files:
                            tmp_nota = f"tmp_{f.name}"
                            with open(tmp_nota, "wb") as f_img: f_img.write(f.getbuffer())
                            pdf.image(tmp_nota, x=10, w=lebar_nota)
                            os.remove(tmp_nota)
                    
                    pdf_bytes = pdf.output()
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    if report_file: merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf = io.BytesIO()
                    merger.write(final_pdf)
                    
                    st.success("✅ Berhasil Disimpan!")
                    st.download_button(label="📥 Download PDF", data=final_pdf.getvalue(), file_name=f"Laporan_{tgl_iso}.pdf", mime="application/pdf")
                except Exception as e:
                    st.error(f"Gagal: {e}")

# --- TAB 2: KUMULATIF ---
with tab2:
    st.header("Rekap Pengeluaran")
    tgl_range = st.date_input("Pilih Rentang Tanggal", value=(datetime.now(), datetime.now()))
    if st.button("🔍 Tampilkan Rekap"):
        df = get_all_data()
        if not df.empty:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce').dt.date
            if len(tgl_range) == 2:
                start, end = tgl_range
                df_filtered = df[(df['Tanggal'] >= start) & (df['Tanggal'] <= end)]
                st.dataframe(df_filtered, use_container_width=True)
                df_filtered['Total'] = pd.to_numeric(df_filtered['Total'], errors='coerce').fillna(0)
                st.info(f"**Grand Total: Rp {df_filtered['Total'].sum():,}**")
