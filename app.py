import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os
from PIL import Image
import re

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
KOP_FILE_PATH = "kop_tetap.jpg"

# --- 2. FUNGSI GOOGLE SHEETS ---
def get_gcp_service(service_name, version):
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build(service_name, version, credentials=creds)

def append_to_sheets(nama_user, data):
    try:
        service = get_gcp_service('sheets', 'v4')
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_names = [s.get('properties', {}).get('title') for s in spreadsheet.get('sheets', [])]
        
        if nama_user not in sheet_names:
            batch_request = {'requests': [{'addSheet': {'properties': {'title': nama_user}}}]}
            service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_request).execute()
            header = [["Tanggal", "Customer", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link GDrive", "Status Bayar"]]
            service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1", valueInputOption="USER_ENTERED", body={'values': header}).execute()

        service.spreadsheets().values().append(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1", valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={'values': [data]}).execute()
    except Exception as e:
        st.error(f"Gagal simpan ke Sheets: {e}")

def get_user_data(nama_user):
    try:
        service = get_gcp_service('sheets', 'v4')
        # Ambil seluruh baris data dari kolom A sampai N
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:N").execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2: 
            return pd.DataFrame()
        
        # 14 Kolom wajib
        max_cols = 14
        processed_values = []
        
        # Ambil header standar agar tidak bentrok dengan data lama di Sheets
        header = ["Tanggal", "Customer", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link GDrive", "Status Bayar"]
        
        # Proses setiap baris di Sheets secara aman
        for row in values[1:]:
            # Jika ada baris kosong, lewati
            if not row or row[0] == "":
                continue
            # Jika jumlah kolom kurang dari 14, tambahkan string kosong sampai pas 14 kolom
            while len(row) < max_cols:
                row.append("")
            # Batasi hanya mengambil maksimal 14 kolom pertama
            processed_values.append(row[:max_cols])
            
        if not processed_values:
            return pd.DataFrame()
            
        df = pd.DataFrame(processed_values, columns=header)
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        # Buang baris jika tanggal gagal terbaca
        df = df.dropna(subset=['Tanggal'])
        df = df.sort_values(by='Tanggal', ascending=False)
        return df
    except Exception as e:
        # Menampilkan log error jika ada kendala pembacaan data structure
        st.error(f"Gagal memproses data riwayat: {e}")
        return pd.DataFrame()

def update_gdrive_link(nama_user, row_index, link, label):
    try:
        service = get_gcp_service('sheets', 'v4')
        formula = f'=HYPERLINK("{link}"; "{label}")'
        target_range = f"'{nama_user}'!M{row_index}"
        body = {'values': [[formula]]}
        service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=target_range, valueInputOption="USER_ENTERED", body=body).execute()
        return True
    except Exception as e:
        st.error(f"Gagal update link: {e}")
        return False

def update_payment_status(nama_user, row_index, status_text):
    try:
        service = get_gcp_service('sheets', 'v4')
        target_range = f"'{nama_user}'!N{row_index}"
        body = {'values': [[status_text]]}
        service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=target_range, valueInputOption="USER_ENTERED", body=body).execute()
        return True
    except Exception as e:
        st.error(f"Gagal update status bayar: {e}")
        return False

def delete_user_row(nama_user, row_index):
    try:
        service = get_gcp_service('sheets', 'v4')
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_id = next(s['properties']['sheetId'] for s in spreadsheet['sheets'] if s['properties']['title'] == nama_user)
        request = {'deleteDimension': {'range': {'sheetId': sheet_id, 'dimension': 'ROWS', 'startIndex': row_index, 'endIndex': row_index + 1}}}
        service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': [request]}).execute()
    except Exception as e:
        st.error(f"Gagal hapus baris: {e}")

# --- 3. SISTEM LOGIN ---
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

# --- 4. APLIKASI UTAMA ---
if check_password():
    st.set_page_config(page_title="Finpac ServiceApp", layout="wide")
    
    st.sidebar.header(f"Halo, {st.session_state.user_nama}")
    if st.sidebar.button("Log Out"):
        st.session_state.password_correct = False
        st.rerun()

    is_admin = st.session_state.user_nama == "Admin"
    
    if is_admin:
        tabs = st.tabs(["👨‍💼 Tab Admin (Semua Tim)"])
        
        with tabs[0]:
            st.header("👨‍💼 Panel Monitoring Admin")
            st.write("Pantau rincian biaya, hitung pengeluaran mingguan, dan konfirmasi pembayaran bon tim.")
            
            list_tim = [nama for nama in USERS_CREDENTIALS.keys() if nama != "Admin"]
            target_user = st.selectbox("🎯 Pilih Nama Teknisi/User:", list_tim)
            
            st.divider()
            
            df_admin = get_user_data(target_user)
            
            if not df_admin.empty:
                df_admin['Total_Angka'] = df_admin['Total'].astype(str).str.replace(',', '').astype(float)
                
                hari_ini = datetime.now()
                tujuh_hari_lalu = hari_ini - timedelta(days=7)
                
                df_mingguan = df_admin[df_admin['Tanggal'] >= tujuh_hari_lalu]
                total_mingguan = df_mingguan['Total_Angka'].sum()
                
                st.metric(label=f"📊 Total Pengeluaran 7 Hari Terakhir ({target_user})", value=f"Rp {total_mingguan:,.0f}")
                
                st.divider()
                st.subheader(f"📋 Detail Laporan & Konfirmasi Pembayaran: {target_user}")
                
                df_admin['original_row_index'] = df_admin.index + 2
                
                for i, row in df_admin.iterrows():
                    tgl_str = row['Tanggal'].strftime('%d/%m/%Y')
                    cust_name = row.get('Customer', 'Unknown')
                    current_status = row.iloc[13] if len(row) >= 14 else ""
                    
                    status_lunas = (current_status == "Sudah Dibayar Admin")
                    
                    with st.expander(f"📅 {tgl_str} - {cust_name} | Total: Rp {float(row['Total_Angka']):,.0f} | 📌 Status: {current_status if current_status else 'Pending'}"):
                        st.markdown(f"**Keperluan / Detail Pekerjaan:** {row.get('Keperluan')}")
                        st.write(f"Total Pengeluaran: **Rp {float(row['Total_Angka']):,.0f}**")
                        
                        col_chk, col_space = st.columns([2, 2])
                        with col_chk:
                            confirm_pay = st.checkbox("💸 Tandai bon ini sebagai 'Sudah Dibayar'", value=status_lunas, key=f"pay_chk_{i}")
                            
                            if confirm_pay != status_lunas:
                                status_baru = "Sudah Dibayar Admin" if confirm_pay else ""
                                if update_payment_status(target_user, int(row['original_row_index']), status_baru):
                                    st.toast("Status pembayaran berhasil diperbarui!", icon="💰")
                                    st.rerun()
            else:
                st.info(f"Belum ada riwayat data laporan yang masuk dari {target_user}.")
                
    else:
        tabs = st.tabs(["📝 Input Laporan", "📊 Riwayat & Rincian"])

        # --- TAB 1: INPUT LAPORAN ---
        with tabs[0]:
            opsi_biaya = st.sidebar.multiselect("Pilih Input:", ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain"], default=["Bensin", "Toll", "Parkir"])
            lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 190)
            spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 80, 50)
            lebar_nota = st.sidebar.slider("Lebar Nota (mm)", 50, 190, 150)
            kop_exist = os.path.exists(KOP_FILE_PATH)

            with st.form("main_form", clear_on_submit=False):
                if kop_exist: 
                    st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
                else:
                    st.warning("⚠️ File 'kop_tetap.jpg' tidak ditemukan.")
                    
                c_id1, c_id2 = st.columns(2)
                nama_teknisi = c_id1.text_input("Nama Pelaksana", value=st.session_state.user_nama, disabled=True)
                tgl_input = c_id2.date_input("Tanggal Tugas", datetime.now())
                customer = st.text_input("Nama Customer / Perusahaan:")
                mesin = st.selectbox("Pilih Mesin:", ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"])
                detail = st.text_area("Detail Pekerjaan:")
                keperluan = f"[{mesin}] {detail}"
                
                bensin = toll = parkir = makan_teknisi = uang_makan = hotel = lain_lain = 0
                col_a, col_b = st.columns(2)
                if "Bensin" in opsi_biaya: bensin = col_a.number_input("Bensin", min_value=0)
                if "Toll" in opsi_biaya: toll = col_b.number_input("Toll", min_value=0)
                col_c, col_d = st.columns(2)
                if "Parkir" in opsi_biaya: parkir = col_c.number_input("Parkir", min_value=0)
                if "Makan Teknisi" in opsi_biaya: makan_teknisi = col_d.number_input("Makan Teknisi", min_value=0)
                
                if "Uang Makan" in opsi_biaya: uang_makan = st.number_input("Uang Makan (Luar Kota)", min_value=0)
                if "Hotel" in opsi_biaya: hotel = st.number_input("Biaya Hotel", min_value=0)
                if "Lain-lain" in opsi_biaya: lain_lain = st.number_input("Lain-lain", min_value=0)
                
                is_lembur = st.checkbox("⚠️ Centang jika kerja Lembur")
                
                bukti_files = st.file_uploader("📸 Nota", accept_multiple_files=True, type=['jpg','png','jpeg','pdf'])
                report_file = st.file_uploader("📄 Service Report", type=['pdf'])
                btn_sub = st.form_submit_button("💾 SIMPAN & DOWNLOAD PDF")

            if btn_sub:
                with st.spinner("Sedang memproses..."):
                    try:
                        total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + lain_lain
                        tgl_iso = tgl_input.strftime('%Y-%m-%d')
                        tgl_cetak = tgl_input.strftime('%d/%m/%Y')
                        
                        append_to_sheets(nama_teknisi, [tgl_iso, customer, nama_teknisi, keperluan, bensin, toll, parkir, makan_teknisi, uang_makan, hotel, lain_lain, total, "", ""])
                        
                        pdf = FPDF()
                        pdf.add_page()
                        if kop_exist:
                            pdf.image(KOP_FILE_PATH, x=(210 - lebar_kop) / 2, y=10, w=lebar_kop)
                            pdf.set_y(10 + spasi_bawah) 
                        else:
                            pdf.set_y(20)
                        
                        pdf.set_font("Arial", "B", 11)
                        pdf.cell(0, 7, f"Customer: {customer}", ln=True)
                        pdf.cell(0, 7, f"Pelaksana: {nama_teknisi} | Tanggal: {tgl_cetak}", ln=True)
                        pdf.ln(2); pdf.set_font("Arial", "", 11)
                        pdf.multi_cell(0, 7, f"Pekerjaan: {keperluan}"); pdf.ln(5)
                        
                        pdf.set_font("Arial", "B", 11); pdf.set_fill_color(240, 240, 240)
                        pdf.cell(100, 10, " Kategori Biaya", 1, 0, 'L', True); pdf.cell(60, 10, " Nominal", 1, 1, 'L', True)
                        pdf.set_font("Arial", "", 11)
                        dict_b = {"Bensin": bensin, "Toll": toll, "Parkir": parkir
