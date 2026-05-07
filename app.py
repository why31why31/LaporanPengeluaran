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

# --- 1. KONFIGURASI USER & PASSWORD ---
# Silakan Bapak tambah atau ubah daftar ini sesuai tim Bapak
USERS_CREDENTIALS = {
    "Asep Wahyu": "as1234",
    "Wahyudi": "wahyu789",
    "Teknisi1": "tek123",
    "Admin": "adminfinpac"
}

SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM"
KOP_FILE_PATH = "kop_tetap.jpg"

# --- 2. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
        st.session_state.user_nama = ""
    
    if not st.session_state.password_correct:
        st.header("🔐 Akses Terkunci - PT. Finpac")
        user_input = st.selectbox("Pilih Nama Anda:", list(USERS_CREDENTIALS.keys()))
        pwd_input = st.text_input("Masukkan Password Anda:", type="password")
        
        if st.button("Masuk"):
            if USERS_CREDENTIALS.get(user_input) == pwd_input:
                st.session_state.password_correct = True
                st.session_state.user_nama = user_input
                st.rerun()
            else:
                st.error("Password Salah!")
        return False
    return True

# --- 3. FUNGSI GOOGLE SERVICES ---
def get_gcp_service(service_name, version):
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build(service_name, version, credentials=creds)

def append_to_sheets(nama_user, data):
    service = get_gcp_service('sheets', 'v4')
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get('sheets', [])
    sheet_names = [s.get('properties', {}).get('title') for s in sheets]
    
    # Buat tab baru jika belum ada
    if nama_user not in sheet_names:
        batch_request = {'requests': [{'addSheet': {'properties': {'title': nama_user}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_request).execute()
        header = [["Tanggal", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Bahan/Alat", "Total"]]
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1",
            valueInputOption="USER_ENTERED", body={'values': header}).execute()

    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body).execute()

# --- 4. MULAI APLIKASI ---
if check_password():
    st.set_page_config(page_title="Finpac ServiceApp", layout="wide")
    
    tab1, tab2 = st.tabs(["📝 Input Laporan", "📊 Data Tim"])

    with tab1:
        st.sidebar.header(f"Halo, {st.session_state.user_nama}")
        if st.sidebar.button("Log Out"):
            st.session_state.password_correct = False
            st.rerun()
            
        opsi_biaya = st.sidebar.multiselect(
            "Tampilkan Input Biaya:",
            ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Bahan/Alat"],
            default=["Bensin", "Toll", "Parkir"]
        )
        
        lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 190)
        spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 50, 35)
        kop_exist = os.path.exists(KOP_FILE_PATH)

        with st.form("main_form", clear_on_submit=False):
            if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
            
            c_id1, c_id2 = st.columns(2)
            # Nama terkunci sesuai login
            nama = c_id1.text_input("Nama Pelaksana", value=st.session_state.user_nama, disabled=True)
            tgl_input = c_id2.date_input("Tanggal Tugas", datetime.now())
            
            mesin = st.selectbox("Pilih Mesin:", ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"])
            detail = st.text_area("Detail Pekerjaan:")
            keperluan = f"[{mesin}] {detail}"
            
            st.subheader("💰 Rincian Biaya")
            bensin = toll = parkir = makan_teknisi = uang_makan = hotel = bahan_alat = 0
            
            col_a, col_b = st.columns(2)
            if "Bensin" in opsi_biaya: bensin = col_a.number_input("Bensin", min_value=0)
            if "Toll" in opsi_biaya: toll = col_b.number_input("Toll", min_value=0)
            
            col_c, col_d = st.columns(2)
            if "Parkir" in opsi_biaya: parkir = col_c.number_input("Parkir", min_value=0)
            if "Makan Teknisi" in opsi_biaya: makan_teknisi = col_d.number_input("Makan Teknisi", min_value=0)
            
            if "Uang Makan" in opsi_biaya: uang_makan = st.number_input("Uang Makan Umum", min_value=0)
            if "Hotel" in opsi_biaya: hotel = st.number_input("Biaya Hotel", min_value=0)
            if "Bahan/Alat" in opsi_biaya: bahan_alat = st.number_input("Bahan/Alat", min_value=0)
            
            st.divider()
            lebar_nota = st.slider("Lebar Nota (mm)", 50, 190, 150)
            bukti_files = st.file_uploader("📸 Nota (Foto/PDF)", accept_multiple_files=True, type=['jpg','png','jpeg','pdf'])
            report_file = st.file_uploader("📄 Service Report PDF", type=['pdf'])
            
            btn_sub = st.form_submit_button("💾 SIMPAN & DOWNLOAD")

        if btn_sub:
            with st.spinner("Mengirim laporan..."):
                try:
                    total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + bahan_alat
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    
                    # Simpan ke Tab masing-masing di Spreadsheet
                    append_to_sheets(nama, [tgl_iso, nama, keperluan, bensin, toll, parkir, makan_teknisi, uang_makan, hotel, bahan_alat, total])
                    
                    # Pembuatan PDF (Sama seperti versi sebelumnya)
                    pdf = FPDF()
                    pdf.add_page()
                    if kop_exist:
                        pdf.image(KOP_FILE_PATH, x=(210-lebar_kop)/2, y=10, w=lebar_kop)
                        pdf.ln(spasi_bawah)
                    
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(5)
                    pdf.set_font("Arial", "B", 11); pdf.cell(0, 7, f"Pelaksana: {nama} | Tanggal: {tgl_iso}", ln=True)
                    pdf.set_font("Arial", "", 11); pdf.multi_cell(0, 7, f"Pekerjaan: {keperluan}"); pdf.ln(5)
                    
                    pdf.set_font("Arial", "B", 11); pdf.set_fill_color(240, 240, 240)
                    pdf.cell(100, 10, " Kategori", 1, 0, 'L', True); pdf.cell(60, 10, " Biaya", 1, 1, 'L', True)
                    pdf.set_font("Arial", "", 11)
                    dict_b = {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan": uang_makan, "Hotel": hotel, "Bahan/Alat": bahan_alat}
                    for k, v in dict_b.items():
                        if v > 0: pdf.cell(100, 8, f" {k}", 1); pdf.cell(60, 8, f" {v:,}", 1, 1)
                    pdf.set_font("Arial", "B", 11); pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True); pdf.cell(60, 10, f" {total:,}", 1, 1, 'L', True)
                    
                    temp_n = []
                    nota_pdfs = []
                    if bukti_files:
                        pdf.add_page()
                        pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for i, f in enumerate(bukti_files):
                            if f.type == "application/pdf": nota_pdfs.append(f)
                            else:
                                img = Image.open(f).convert("RGB"); t_n = f"n_usr_{i}.jpg"; img.save(t_n, "JPEG")
                                temp_n.append(t_n); pdf.image(t_n, x=10, w=lebar_nota); pdf.ln(5)
                    
                    main_out = "final_render.pdf"
                    pdf.output(main_out)
                    merger = PdfWriter()
                    merger.append(main_out)
                    for n_pdf in nota_pdfs:
                        n_pdf.seek(0); merger.append(io.BytesIO(n_pdf.read()))
                    if report_file:
                        report_file.seek(0); merger.append(io.BytesIO(report_file.read()))
                    
                    f_buf = io.BytesIO(); merger.write(f_buf)
                    if os.path.exists(main_out): os.remove(main_out)
                    for t in temp_n:
                        if os.path.exists(t): os.remove(t)
                            
                    st.success(f"✅ Berhasil! Data tersimpan di Tab '{nama}'")
                    st.download_button("📥 Download PDF", f_buf.getvalue(), f"Laporan_{nama}_{tgl_iso}.pdf")
                except Exception as e:
                    st.error(f"Gagal: {e}")

    with tab2:
        st.info("Setiap anggota tim hanya dapat mengisi datanya sendiri. Admin dapat melihat rekapitulasi di file Google Sheets.")
