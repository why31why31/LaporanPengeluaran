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
from PIL import Image

# --- 1. KONFIGURASI ---
USERS_CREDENTIALS = {
    "Asep Wahyu": "as1234",
    "Wahyu": "wahyu123",
    "Rangga": "rangga123",
    "Ali": "ali123",
    "Karim": "karim123",
    "Admin": "adminfinpac"
}

SPREADSHEET_ID = "1IX6TAhHaf1rwJyQKY9MkMXaN1zVye24TyVgmma8YIU8"
# Folder ini harus sudah di-share ke email Service Account sebagai 'Editor'
PARENT_FOLDER_ID = "1zU_b_6865osGILgOsY_usiM6LrR6IbFE" 
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

def upload_to_gdrive(file_buffer, file_name):
    try:
        service = get_gcp_service('drive', 'v3')
        
        # Metadata menyertakan 'parents' agar menggunakan kuota folder Bapak
        file_metadata = {
            'name': file_name,
            'parents': [PARENT_FOLDER_ID]
        }
        
        media = MediaIoBaseUpload(file_buffer, mimetype='application/pdf', resumable=True)
        
        # Eksekusi dengan supportsAllDrives=True untuk folder shared/pribadi
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        return file.get('id')
    except Exception as e:
        if "storageQuotaExceeded" in str(e):
            st.error("⚠️ Kuota Penuh: Pastikan Folder Drive sudah di-share ke email Service Account sebagai Editor.")
        else:
            st.error(f"Gagal upload ke Drive: {e}")
        return None

def append_to_sheets(nama_user, data):
    service = get_gcp_service('sheets', 'v4')
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_names = [s.get('properties', {}).get('title') for s in spreadsheet.get('sheets', [])]
    
    if nama_user not in sheet_names:
        batch_request = {'requests': [{'addSheet': {'properties': {'title': nama_user}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_request).execute()
        header = [["Tanggal", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan (Luar Kota)", "Hotel", "Bahan/Alat", "Total"]]
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1",
            valueInputOption="USER_ENTERED", body={'values': header}).execute()

    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={'values': [data]}).execute()

def get_user_data(nama_user):
    try:
        service = get_gcp_service('sheets', 'v4')
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:L").execute()
        values = result.get('values', [])
        if not values or len(values) < 2: return pd.DataFrame()
        return pd.DataFrame(values[1:], columns=values[0])
    except: return pd.DataFrame()

def delete_user_row(nama_user, row_index):
    service = get_gcp_service('sheets', 'v4')
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_id = next(s['properties']['sheetId'] for s in spreadsheet['sheets'] if s['properties']['title'] == nama_user)
    request = {'deleteDimension': {'range': {'sheetId': sheet_id, 'dimension': 'ROWS', 'startIndex': row_index, 'endIndex': row_index + 1}}}
    service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': [request]}).execute()

# --- 4. MULAI APLIKASI ---
if check_password():
    st.set_page_config(page_title="Finpac ServiceApp", layout="wide")
    tab1, tab2 = st.tabs(["📝 Input Laporan", "📊 Riwayat & Rincian"])

    with tab1:
        st.sidebar.header(f"Halo, {st.session_state.user_nama}")
        if st.sidebar.button("Log Out"):
            st.session_state.password_correct = False
            st.rerun()
            
        opsi_biaya = st.sidebar.multiselect("Pilih Input:", ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan (Luar Kota)", "Hotel", "Bahan/Alat"], default=["Bensin", "Toll", "Parkir"])
        lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 190); spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 50, 35)
        kop_exist = os.path.exists(KOP_FILE_PATH)

        with st.form("main_form", clear_on_submit=False):
            if kop_exist: st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
            c_id1, c_id2 = st.columns(2)
            nama = c_id1.text_input("Nama Pelaksana", value=st.session_state.user_nama, disabled=True)
            tgl_input = c_id2.date_input("Tanggal Tugas", datetime.now())
            mesin = st.selectbox("Pilih Mesin:", ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"])
            detail = st.text_area("Detail Pekerjaan:")
            keperluan = f"[{mesin}] {detail}"
            
            bensin = toll = parkir = makan_teknisi = uang_makan = hotel = bahan_alat = 0
            col_a, col_b = st.columns(2)
            if "Bensin" in opsi_biaya: bensin = col_a.number_input("Bensin", min_value=0)
            if "Toll" in opsi_biaya: toll = col_b.number_input("Toll", min_value=0)
            col_c, col_d = st.columns(2)
            if "Parkir" in opsi_biaya: parkir = col_c.number_input("Parkir", min_value=0)
            if "Makan Teknisi" in opsi_biaya: makan_teknisi = col_d.number_input("Makan Teknisi", min_value=0)
            if "Uang Makan (Luar Kota)" in opsi_biaya: uang_makan = st.number_input("Uang Makan (Luar Kota)", min_value=0)
            if "Hotel" in opsi_biaya: hotel = st.number_input("Biaya Hotel", min_value=0)
            if "Bahan/Alat" in opsi_biaya: bahan_alat = st.number_input("Bahan/Alat", min_value=0)
            
            bukti_files = st.file_uploader("📸 Nota", accept_multiple_files=True, type=['jpg','png','jpeg','pdf'])
            report_file = st.file_uploader("📄 Service Report", type=['pdf'])
            btn_sub = st.form_submit_button("💾 SIMPAN & UPLOAD")

        if btn_sub:
            with st.spinner("Proses simpan dan upload..."):
                try:
                    total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + bahan_alat
                    tgl_iso = tgl_input.strftime('%Y-%m-%d')
                    append_to_sheets(nama, [tgl_iso, nama, keperluan, bensin, toll, parkir, makan_teknisi, uang_makan, hotel, bahan_alat, total])
                    
                    pdf = FPDF(); pdf.add_page()
                    if kop_exist:
                        pdf.image(KOP_FILE_PATH, x=(210-lebar_kop)/2, y=10, w=lebar_kop); pdf.ln(spasi_bawah)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y()); pdf.ln(5)
                    pdf.set_font("Arial", "B", 11); pdf.cell(0, 7, f"Pelaksana: {nama} | Tanggal: {tgl_iso}", ln=True)
                    pdf.set_font("Arial", "", 11); pdf.multi_cell(0, 7, f"Pekerjaan: {keperluan}"); pdf.ln(5)
                    
                    pdf.set_font("Arial", "B", 11); pdf.set_fill_color(240, 240, 240)
                    pdf.cell(100, 10, " Kategori", 1, 0, 'L', True); pdf.cell(60, 10, " Biaya", 1, 1, 'L', True)
                    pdf.set_font("Arial", "", 11)
                    dict_b = {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan (Luar Kota)": uang_makan, "Hotel": hotel, "Bahan/Alat": bahan_alat}
                    for k, v in dict_b.items():
                        if v > 0: pdf.cell(100, 8, f" {k}", 1); pdf.cell(60, 8, f" {v:,}", 1, 1)
                    pdf.set_font("Arial", "B", 11); pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True); pdf.cell(60, 10, f" {total:,}", 1, 1, 'L', True)
                    
                    temp_n = []; nota_pdfs = []
                    if bukti_files:
                        pdf.add_page(); pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True)
                        for i, f in enumerate(bukti_files):
                            if f.type == "application/pdf": nota_pdfs.append(f)
                            else:
                                img = Image.open(f).convert("RGB"); t_n = f"n_usr_{i}.jpg"; img.save(t_n, "JPEG")
                                temp_n.append(t_n); pdf.image(t_n, x=10, w=150); pdf.ln(5)
                    
                    main_out = "temp_render.pdf"; pdf.output(main_out)
                    merger = PdfWriter(); merger.append(main_out)
                    for n_pdf in nota_pdfs:
                        n_pdf.seek(0); merger.append(io.BytesIO(n_pdf.read()))
                    if report_file:
                        report_file.seek(0); merger.append(io.BytesIO(report_file.read()))
                    
                    f_buf = io.BytesIO(); merger.write(f_buf); f_buf.seek(0)
                    
                    # --- EKSEKUSI UPLOAD ---
                    drive_id = upload_to_gdrive(f_buf, f"Laporan_{nama}_{tgl_iso}.pdf")
                    
                    if os.path.exists(main_out): os.remove(main_out)
                    for t in temp_n:
                        if os.path.exists(t): os.remove(t)
                            
                    if drive_id:
                        st.success(f"✅ Tersimpan di Sheets & Google Drive!")
                    st.download_button("📥 Download PDF Manual", f_buf.getvalue(), f"Laporan_{nama}_{tgl_iso}.pdf")
                except Exception as e: st.error(f"Gagal: {e}")

    with tab2:
        st.header(f"📊 Riwayat & Rincian: {st.session_state.user_nama}")
        df = get_user_data(st.session_state.user_nama)
        if not df.empty:
            df_display = df.iloc[::-1].reset_index()
            for i, row in df_display.iterrows():
                with st.expander(f"📅 {row.get('Tanggal', 'N/A')} - {row.get('Keperluan', 'N/A')}"):
                    v_makan = row.get('Uang Makan (Luar Kota)', row.get('Uang Makan (Luar kota)', row.get('Uang Makan', 0)))
                    v_total = row.get('Total', row.get('total', 0))
                    rincian = {
                        "Kategori": ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan (Luar Kota)", "Hotel", "Bahan/Alat", "TOTAL"],
                        "Nominal": [row.get('Bensin',0), row.get('Toll',0), row.get('Parkir',0), row.get('Makan Teknisi',0), v_makan, row.get('Hotel',0), row.get('Bahan/Alat',0), f"**{v_total}**"]
                    }
                    st.table(pd.DataFrame(rincian))
                    if st.button(f"🗑️ Hapus {row.get('Tanggal', i)}", key=f"del_{row['index']}"):
                        delete_user_row(st.session_state.user_nama, int(row['index']) + 1)
                        st.success("Data dihapus!"); st.rerun()
