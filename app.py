import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os
import plotly.express as px
from PIL import Image

# --- 1. KONFIGURASI & LOGIN ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
KOP_FILE_PATH = "kop_tetap.jpg"
PASSWORD_APP = "as1234" 

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.header("🔐 Akses Terkunci")
        pwd = st.text_input("Masukkan Password Laporan:", type="password")
        if st.button("Masuk"):
            if pwd == PASSWORD_APP:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Password Salah!")
        return False
    return True

# --- 2. FUNGSI GOOGLE SERVICES ---
def get_gcp_service(service_name, version):
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build(service_name, version, credentials=creds)

def append_to_sheets(data):
    service = get_gcp_service('sheets', 'v4')
    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A1",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body
    ).execute()

def get_all_data():
    try:
        service = get_gcp_service('sheets', 'v4')
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A:H").execute()
        values = result.get('values', [])
        if not values: return pd.DataFrame()
        headers = [h.strip() for h in values[0]]
        return pd.DataFrame(values[1:], columns=headers)
    except: return pd.DataFrame()

def delete_sheet_row(row_index):
    service = get_gcp_service('sheets', 'v4')
    request = {'deleteDimension': {'range': {'sheetId': 0, 'dimension': 'ROWS', 'startIndex': row_index, 'endIndex': row_index + 1}}}
    service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': [request]}).execute()

# --- 3. MULAI APLIKASI ---
if check_password():
    st.set_page_config(page_title="Super Laporan Asep Wahyu", layout="wide")
    
    tab1, tab2 = st.tabs(["📝 Input Harian", "📊 Analisis & Kumulatif"])

    with tab1:
        st.sidebar.header("⚙️ Pengaturan Kop")
        update_kop = st.sidebar.file_uploader("Upload Kop Baru", type=['jpg', 'jpeg', 'png'])
        if update_kop:
            img = Image.open(update_kop).convert("RGB")
            img.save(KOP_FILE_PATH, "JPEG")
            st.sidebar.success("Kop diperbarui!")
            st.rerun()
        
        lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 190)
        spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 50, 35)
        kop_exist = os.path.exists(KOP_FILE_PATH)

        st.header("Input Maintenance")
        with st.form("main_form", clear_on_submit=True):
            if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
            
            c_id1, c_id2 = st.columns(2)
            nama = c_id1.text_input("Nama", value="Asep Wahyu")
            tgl_input = c_id2.date_input("Tanggal", datetime.now())
            
            mesin = st.selectbox("Pilih Mesin:", ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"])
            detail = st.text_area("Detail Pekerjaan:")
            keperluan = f"[{mesin}] {detail}"
            
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            bensin = c1.number_input("Bensin", min_value=0)
            toll = c2.number_input("Toll", min_value=0)
            makan = c3.number_input("Makan", min_value=0)
            parkir = c4.number_input("Parkir", min_value=0)
            
            st.divider()
            lebar_nota = st.slider("Lebar Nota (mm)", 50, 190, 150)
            # Pastikan variabel ini tidak tertukar
            bukti_files = st.file_uploader("📸 Upload Foto Nota", accept_multiple_files=True, type=['jpg','png','jpeg'])
            report_file = st.file_uploader("📄 Upload Service Report (PDF)", type=['pdf'])
            
            col_b1, col_b2 = st.columns(2)
            btn_prev = col_b1.form_submit_button("🔍 PREVIEW")
            btn_sub = col_b2.form_submit_button("💾 SIMPAN DATA")

        if btn_prev:
            st.subheader("Preview Laporan")
            with st.container(border=True):
                if kop_exist: st.image(KOP_FILE_PATH, width=400)
                st.write(f"**Tanggal:** {tgl_input} | **Mesin:** {mesin}")
                st.write(f"**Pekerjaan:** {detail}")
                st.table(pd.DataFrame({"Item": ["Bensin", "Toll", "Makan", "Parkir"], 
                                      "Biaya": [f"Rp {bensin:,}", f"Rp {toll:,}", f"Rp {makan:,}", f"Rp {parkir:,}"]}))

        if btn_sub:
            with st.spinner("Sedang memproses laporan..."):
                try:
                    total = bensin + toll + makan + parkir
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets([tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total])
                    
                    # 2. Buat PDF Dasar
                    pdf = FPDF()
                    pdf.add_page()
                    if kop_exist:
                        pdf.image(KOP_FILE_PATH, x=10, y=10, w=lebar_kop)
                        pdf.ln(spasi_bawah)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 12)
                    pdf.cell(0, 10, f"LAPORAN MAINTENANCE {mesin.upper()}", ln=True)
                    pdf.set_font("Arial", "", 11)
                    pdf.cell(0, 7, f"Tanggal: {tgl_iso} | Pelaksana: {nama}", ln=True)
                    pdf.multi_cell(0, 7, f"Detail Pekerjaan: {detail}")
                    pdf.ln(5)
                    pdf.cell(100, 8, "Total Biaya Operasional", 1); pdf.cell(60, 8, f"Rp {total:,}", 1, ln=True)
                    
                    # 3. Proses Lampiran Nota
                    if bukti_files:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for i, f in enumerate(bukti_files):
                            img_nota = Image.open(f).convert("RGB")
                            tmp_name = f"nota_temp_{i}.jpg" # Nama unik agar tidak bentrok
                            img_nota.save(tmp_name, "JPEG")
                            pdf.image(tmp_name, x=10, w=lebar_nota)
                            os.remove(tmp_name)
                    
                    # 4. Penggabungan PDF (Main PDF + Service Report)
                    pdf_output = pdf.output()
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_output))
                    
                    if report_file:
                        # Reset pointer file agar terbaca dari awal
                        report_file.seek(0)
                        merger.append(io.BytesIO(report_file.read()))
                    
                    final_pdf_buffer = io.BytesIO()
                    merger.write(final_pdf_buffer)
                    
                    st.success("✅ Data dan Report Berhasil Disimpan!")
                    st.download_button(
                        label="📥 Download Hasil Akhir PDF",
                        data=final_pdf_buffer.getvalue(),
                        file_name=f"Laporan_{mesin}_{tgl_iso}.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Terjadi kesalahan teknis: {e}")

    with tab2:
        st.header("📊 Analisis & Kumulatif")
        # ... (Bagian Analisis tetap sama seperti sebelumnya)
