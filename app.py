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
        
        # Form dengan clear_on_submit=False agar data tidak hilang saat Preview
        with st.form("main_form", clear_on_submit=False):
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
            bukti_files = st.file_uploader("📸 Foto Nota", accept_multiple_files=True, type=['jpg','png','jpeg'])
            report_file = st.file_uploader("📄 Service Report (PDF)", type=['pdf'])
            
            col_b1, col_b2 = st.columns(2)
            btn_prev = col_b1.form_submit_button("🔍 PREVIEW")
            btn_sub = col_b2.form_submit_button("💾 SIMPAN DATA")

        # LOGIKA PREVIEW (Sejajar dengan kolom tombol di dalam tab1)
        if btn_prev:
            st.markdown("---")
            st.subheader("📄 Preview Hasil Cetak")
            with st.container(border=True):
                if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
                st.markdown("<hr style='border: 1px solid black;'>", unsafe_allow_html=True)
                p_c1, p_c2 = st.columns(2)
                p_c1.write(f"**Tanggal:** {tgl_input}")
                p_c2.write(f"**Oleh:** {nama}")
                st.write(f"**Pekerjaan:** {keperluan}")
                total_prev = bensin + toll + makan + parkir
                st.table(pd.DataFrame({"Item": ["Bensin", "Toll", "Makan", "Parkir", "TOTAL"], 
                                      "Biaya (Rp)": [f"{bensin:,}", f"{toll:,}", f"{makan:,}", f"{parkir:,}", f"**{total_prev:,}**"]}))

        # LOGIKA SUBMIT (Sejajar dengan btn_prev)
        if btn_sub:
            with st.spinner("Sedang memproses laporan..."):
                try:
                    total = bensin + toll + makan + parkir
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    
                    # 1. Simpan ke Sheets
                    append_to_sheets([tgl_iso, nama, keperluan, bensin, toll, makan, parkir, total])
                    
                    # 2. Buat PDF Utama
                    pdf = FPDF()
                    pdf.add_page()
                    if kop_exist:
                        pdf.image(KOP_FILE_PATH, x=(210-lebar_kop)/2, y=10, w=lebar_kop)
                        pdf.set_y(10 + (lebar_kop/4) + 5)
                        pdf.ln(spasi_bawah / 2)
                    
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(95, 7, f"Tanggal: {tgl_iso}", 0)
                    pdf.cell(95, 7, f"Oleh: {nama}", 0, ln=True)
                    pdf.set_font("Arial", "", 11)
                    pdf.multi_cell(0, 7, f"Detail Pekerjaan: {keperluan}")
                    pdf.ln(5)
                    
                    # Tabel PDF
                    pdf.set_font("Arial", "B", 11)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(100, 10, " Kategori", 1, 0, 'L', True)
                    pdf.cell(60, 10, " Jumlah (Rp)", 1, 1, 'L', True)
                    pdf.set_font("Arial", "", 11)
                    pdf.cell(100, 8, " Bensin", 1); pdf.cell(60, 8, f" {bensin:,}", 1, 1)
                    pdf.cell(100, 8, " Toll", 1); pdf.cell(60, 8, f" {toll:,}", 1, 1)
                    pdf.cell(100, 8, " Makan", 1); pdf.cell(60, 8, f" {makan:,}", 1, 1)
                    pdf.cell(100, 8, " Parkir", 1); pdf.cell(60, 8, f" {parkir:,}", 1, 1)
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True)
                    pdf.cell(60, 10, f" {total:,}", 1, 1, 'L', True)
                    
                    # Lampiran Nota
                    temp_nota_files = []
                    if bukti_files:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for i, f in enumerate(bukti_files):
                            img_nota = Image.open(f).convert("RGB")
                            tmp_n = f"final_n_{i}.jpg"
                            img_nota.save(tmp_n, "JPEG")
                            temp_nota_files.append(tmp_n)
                            pdf.image(tmp_n, x=10, w=lebar_nota)
                            pdf.ln(5)
                    
                    # Render Final
                    main_p_temp = "render_temp.pdf"
                    pdf.output(main_p_temp)
                    
                    merger = PdfWriter()
                    merger.append(main_p_temp)
                    if report_file:
                        report_file.seek(0)
                        merger.append(report_file)
                    
                    f_buffer = io.BytesIO()
                    merger.write(f_buffer)
                    
                    if os.path.exists(main_p_temp): os.remove(main_p_temp)
                    for tn in temp_nota_files:
                        if os.path.exists(tn): os.remove(tn)
                        
                    st.success("✅ Berhasil!")
                    st.download_button("📥 Download PDF", f_buffer.getvalue(), f"Laporan_{tgl_iso}.pdf")
                except Exception as e:
                    st.error(f"Gagal: {e}")

    with tab2:
        st.header("📊 Analisis Data")
        df = get_all_data()
        if not df.empty:
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
            fig = px.bar(df, x='Tanggal', y='Total', color='Nama', title="Tren Pengeluaran")
            st.plotly_chart(fig, use_container_width=True)
            st.divider()
            for i, row in df.iterrows():
                c_d1, c_d2 = st.columns([0.8, 0.2])
                c_d1.write(f"**{row['Tanggal'].date()}** - {row['Keperluan']} - Rp {row['Total']:,}")
                if c_d2.button("🗑️ Hapus", key=f"del_{i}"):
                    delete_sheet_row(i + 1)
                    st.rerun()
