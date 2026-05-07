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
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A:L").execute()
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
        st.sidebar.header("⚙️ Pengaturan Tampilan")
        
        # FITUR BARU: Opsi Memilih Input yang Muncul
        opsi_biaya = st.sidebar.multiselect(
            "Tampilkan Input Biaya:",
            ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Bahan/Alat"],
            default=["Bensin", "Toll", "Parkir"] # Default yang sering dipakai
        )
        
        st.sidebar.divider()
        update_kop = st.sidebar.file_uploader("Upload Kop Baru", type=['jpg', 'jpeg', 'png'])
        if update_kop:
            img = Image.open(update_kop).convert("RGB")
            img.save(KOP_FILE_PATH, "JPEG")
            st.sidebar.success("Kop diperbarui!")
            st.rerun()
        
        lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 190)
        spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 50, 35)
        kop_exist = os.path.exists(KOP_FILE_PATH)

        st.header("Input Maintenance & Operasional")
        
        with st.form("main_form", clear_on_submit=False):
            if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
            
            c_id1, c_id2 = st.columns(2)
            nama = c_id1.text_input("Nama", value="Asep Wahyu")
            tgl_input = c_id2.date_input("Tanggal", datetime.now())
            
            mesin = st.selectbox("Pilih Mesin:", ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"])
            detail = st.text_area("Detail Pekerjaan:")
            keperluan = f"[{mesin}] {detail}"
            
            st.subheader("💰 Rincian Biaya")
            # Inisialisasi semua variabel dengan 0
            bensin = toll = parkir = makan_teknisi = uang_makan = hotel = bahan_alat = 0
            
            # Tampilkan hanya jika dipilih di Sidebar
            col1, col2 = st.columns(2)
            if "Bensin" in opsi_biaya: bensin = col1.number_input("Bensin", min_value=0)
            if "Toll" in opsi_biaya: toll = col2.number_input("Toll", min_value=0)
            
            col3, col4 = st.columns(2)
            if "Parkir" in opsi_biaya: parkir = col3.number_input("Parkir", min_value=0)
            if "Makan Teknisi" in opsi_biaya: makan_teknisi = col4.number_input("Makan Teknisi", min_value=0)
            
            col5, col6 = st.columns(2)
            if "Uang Makan" in opsi_biaya: uang_makan = col5.number_input("Uang Makan", min_value=0)
            if "Hotel" in opsi_biaya: hotel = col6.number_input("Biaya Hotel", min_value=0)
            
            if "Bahan/Alat" in opsi_biaya: bahan_alat = st.number_input("Pembelian Bahan/Alat", min_value=0)
            
            st.divider()
            lebar_nota = st.slider("Lebar Nota di PDF (mm)", 50, 190, 150)
            bukti_files = st.file_uploader("📸 Foto atau PDF Nota", accept_multiple_files=True, type=['jpg','png','jpeg','pdf'])
            report_file = st.file_uploader("📄 Service Report Utama (PDF)", type=['pdf'])
            
            col_b1, col_b2 = st.columns(2)
            btn_prev = col_b1.form_submit_button("🔍 PREVIEW")
            btn_sub = col_b2.form_submit_button("💾 SIMPAN DATA")

        if btn_prev:
            st.markdown("---")
            st.subheader("📄 Preview Laporan")
            with st.container(border=True):
                if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
                st.markdown("<hr style='border: 1px solid black;'>", unsafe_allow_html=True)
                p_c1, p_c2 = st.columns(2)
                p_c1.write(f"**Tanggal:** {tgl_input}")
                p_c2.write(f"**Oleh:** {nama}")
                st.write(f"**Pekerjaan:** {keperluan}")
                total_prev = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + bahan_alat
                
                # Buat tabel preview dinamis (hanya yang tidak 0)
                data_biaya = []
                for k, v in {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan": uang_makan, "Hotel": hotel, "Bahan/Alat": bahan_alat}.items():
                    if v > 0: data_biaya.append({"Kategori": k, "Biaya": f"{v:,}"})
                data_biaya.append({"Kategori": "**TOTAL**", "Biaya": f"**{total_prev:,}**"})
                st.table(pd.DataFrame(data_biaya))

        if btn_sub:
            with st.spinner("Memproses laporan..."):
                try:
                    total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + bahan_alat
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    
                    # 1. Simpan ke Sheets (Tetap 11 kolom, nilai yang disembunyikan otomatis terisi 0)
                    append_to_sheets([tgl_iso, nama, keperluan, bensin, toll, parkir, makan_teknisi, uang_makan, hotel, bahan_alat, total])
                    
                    # 2. Buat PDF (Hanya menampilkan kategori yang ada isinya)
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
                    
                    pdf.set_font("Arial", "B", 11)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(100, 10, " Kategori Pengeluaran", 1, 0, 'L', True)
                    pdf.cell(60, 10, " Jumlah (Rp)", 1, 1, 'L', True)
                    pdf.set_font("Arial", "", 11)
                    
                    # Hanya cetak di PDF jika biaya > 0
                    biaya_dict = {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan": uang_makan, "Hotel": hotel, "Bahan/Alat": bahan_alat}
                    for label, nilai in biaya_dict.items():
                        if nilai > 0:
                            pdf.cell(100, 8, f" {label}", 1); pdf.cell(60, 8, f" {nilai:,}", 1, 1)
                    
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True)
                    pdf.cell(60, 10, f" {total:,}", 1, 1, 'L', True)
                    
                    # Lampiran Nota
                    temp_images = []
                    nota_pdfs = []
                    if bukti_files:
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(0, 10, "LAMPIRAN NOTA / BUKTI PEMBAYARAN:", ln=True)
                        for i, f in enumerate(bukti_files):
                            if f.type == "application/pdf": nota_pdfs.append(f)
                            else:
                                img = Image.open(f).convert("RGB")
                                tmp = f"n_fix_{i}.jpg"
                                img.save(tmp, "JPEG")
                                temp_images.append(tmp)
                                pdf.image(tmp, x=10, w=lebar_nota)
                                pdf.ln(5)
                    
                    main_temp = "final_output.pdf"
                    pdf.output(main_temp)
                    
                    merger = PdfWriter()
                    merger.append(main_temp)
                    for npdf in nota_pdfs:
                        npdf.seek(0)
                        merger.append(io.BytesIO(npdf.read()))
                    if report_file:
                        report_file.seek(0)
                        merger.append(io.BytesIO(report_file.read()))
                    
                    buf = io.BytesIO()
                    merger.write(buf)
                    
                    if os.path.exists(main_temp): os.remove(main_temp)
                    for t in temp_images:
                        if os.path.exists(t): os.remove(t)
                        
                    st.success("✅ Laporan Berhasil Disimpan!")
                    st.download_button("📥 Download PDF", buf.getvalue(), f"Laporan_{tgl_iso}.pdf")
                except Exception as e:
                    st.error(f"Gagal: {e}")

    with tab2:
        st.header("📊 Analisis Data")
        df = get_all_data()
        if not df.empty:
            # ... (bagian analisis tetap sama)
            st.write(df)
