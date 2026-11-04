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
import base64
import uuid
import time  # <-- DITAMBAHKAN UNTUK SISTEM JEDA AUTO-RETRY

# Impor pypdfium2 untuk konversi PDF ke Gambar Preview
try:
    import pypdfium2 as pdfium
    HAS_PDFIUM = True
except ImportError:
    HAS_PDFIUM = False

# --- SETTING HALAMAN UTAMA (WAJIB DI PALING ATAS) ---
st.set_page_config(page_title="Finpac ServiceApp", layout="wide")

# --- FUNGSI BACKGROUND TAMPILAN (DENGAN CACHE) ---
@st.cache_data
def get_bg_encoded(bg_file):
    with open(bg_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

def set_background():
    bg_file = "bg_finpac.jpg"
    if os.path.exists(bg_file):
        encoded_string = get_bg_encoded(bg_file)
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:image/jpeg;base64,{encoded_string});
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            .stForm {{ background-color: rgba(255, 255, 255, 0.95); border-radius: 10px; padding: 20px; }}
            </style>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <style>
            .stApp {
                background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
            }
            .stForm { background-color: rgba(255, 255, 255, 0.9); border-radius: 10px; padding: 20px; }
            </style>
            """,
            unsafe_allow_html=True
        )

set_background()

# --- FUNGSI KONVERSI PDF KE GAMBAR UNTUK PREVIEW ---
def pdf_bytes_to_images(pdf_bytes):
    images = []
    if not HAS_PDFIUM:
        return images
    try:
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        for page in pdf_doc:
            image = page.render(scale=2.0).to_pil()
            images.append(image)
    except Exception:
        pass
    return images

# --- 1. KONFIGURASI ---
USERS_CREDENTIALS = {
    "Asep Wahyu": "as1",
    "Wahyu": "wahyu123",
    "Rangga": "rangga123",
    "Ali": "ali123",
    "Karim": "karim123",
    "Admin": "adminfinpac"
}

SPREADSHEET_ID = "1IX6TAhHaf1rwJyQKY9MkMXaN1zVye24TyVgmma8YIU8"
KOP_FILE_PATH = "kop_tetap.jpg"

# --- 2. FUNGSI GOOGLE SHEETS (DENGAN SISTEM AUTO-RETRY ANTI SSL ERROR) ---
@st.cache_resource
def get_gcp_service(service_name, version):
    info = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(info)
    return build(service_name, version, credentials=creds)

def append_to_sheets(nama_user, data, is_lembur=False):
    for attempt in range(3):
        try:
            service = get_gcp_service('sheets', 'v4')
            spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
            
            sheet_id = None
            sheet_names = []
            for s in spreadsheet.get('sheets', []):
                title = s.get('properties', {}).get('title')
                sheet_names.append(title)
                if title == nama_user:
                    sheet_id = s.get('properties', {}).get('sheetId')
            
            if nama_user not in sheet_names:
                batch_request = {'requests': [{'addSheet': {'properties': {'title': nama_user}}}]}
                response = service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_request).execute()
                sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
                header = [["Tanggal", "Customer", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link GDrive", "Status Bayar"]]
                service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A1", valueInputOption="USER_ENTERED", body={'values': header}).execute()

            response = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, 
                range=f"'{nama_user}'!A1", 
                valueInputOption="USER_ENTERED", 
                insertDataOption="INSERT_ROWS", 
                body={'values': [data]}
            ).execute()
            
            updated_range = response.get('updates', {}).get('updatedRange', '')
            match = re.search(r'!A(\d+)', updated_range)
            if match and is_lembur:
                row_index = int(match.group(1))
                bg_color = {"red": 1.0, "green": 1.0, "blue": 0.0} 
                requests = [{
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row_index - 1,
                            "endRowIndex": row_index,
                            "startColumnIndex": 0,
                            "endColumnIndex": 14 
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": bg_color
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                }]
                service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': requests}).execute()
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                st.error(f"Gagal simpan ke Sheets: {e}")
                return False

def get_user_data(nama_user):
    for attempt in range(3):
        try:
            service = get_gcp_service('sheets', 'v4')
            result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:N").execute()
            values = result.get('values', [])
            
            result_formula = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:N", valueRenderOption="FORMULA").execute()
            formulas = result_formula.get('values', [])
            
            lembur_flags = []
            try:
                format_req = service.spreadsheets().get(
                    spreadsheetId=SPREADSHEET_ID,
                    ranges=[f"'{nama_user}'!A:A"],
                    includeGridData=True
                ).execute()
                
                row_data = format_req.get('sheets', [{}])[0].get('data', [{}])[0].get('rowData', [])
                for r in row_data[1:]: 
                    is_l = False
                    try:
                        vals = r.get('values', [])
                        if vals:
                            color = vals[0].get('effectiveFormat', {}).get('backgroundColor', {})
                            if color.get('red', 0) > 0.8 and color.get('green', 0) > 0.8 and color.get('blue', 0) < 0.2:
                                is_l = True
                    except Exception:
                        pass
                    lembur_flags.append(is_l)
            except Exception:
                pass 
            
            if not values or len(values) < 2: 
                return pd.DataFrame()
            
            max_cols = 14
            processed_values = []
            processed_flags = []
            header = ["Tanggal", "Customer", "Nama", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link GDrive", "Status Bayar"]
            
            for i, row in enumerate(values[1:]):
                row_idx = i + 1
                if not row or row[0] == "":
                    continue
                
                while len(row) < max_cols:
                    row.append("")
                    
                if row_idx < len(formulas) and len(formulas[row_idx]) > 12:
                    raw_formula = formulas[row_idx][12]
                    if raw_formula:
                        row[12] = raw_formula
                        
                processed_values.append(row[:max_cols])
                
                flag = False
                if i < len(lembur_flags):
                    flag = lembur_flags[i]
                processed_flags.append(flag)
                
            if not processed_values:
                return pd.DataFrame()
                
            df = pd.DataFrame(processed_values, columns=header)
            df['Is_Lembur'] = processed_flags
            df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
            df = df.dropna(subset=['Tanggal'])
            df = df.sort_values(by='Tanggal', ascending=False)
            return df
        except Exception as e:
            if attempt < 2:
                time.sleep(1) # Jeda 1 detik lalu coba lagi
            else:
                st.error(f"Gagal memproses data riwayat: {e}")
                return pd.DataFrame()

def update_gdrive_link(nama_user, row_index, link, label):
    for attempt in range(3):
        try:
            service = get_gcp_service('sheets', 'v4')
            formula = f'=HYPERLINK("{link}"; "{label}")'
            target_range = f"'{nama_user}'!M{row_index}"
            body = {'values': [[formula]]}
            service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=target_range, valueInputOption="USER_ENTERED", body=body).execute()
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                st.error(f"Gagal update link: {e}")
                return False

def update_payment_status(nama_user, row_index, status_text):
    for attempt in range(3):
        try:
            service = get_gcp_service('sheets', 'v4')
            target_range = f"'{nama_user}'!N{row_index}"
            body = {'values': [[status_text]]}
            service.spreadsheets().values().update(spreadsheetId=SPREADSHEET_ID, range=target_range, valueInputOption="USER_ENTERED", body=body).execute()
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                st.error(f"Gagal update status bayar: {e}")
                return False

def delete_user_row(nama_user, row_index):
    for attempt in range(3):
        try:
            service = get_gcp_service('sheets', 'v4')
            spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
            sheet_id = next(s['properties']['sheetId'] for s in spreadsheet['sheets'] if s['properties']['title'] == nama_user)
            request = {'deleteDimension': {'range': {'sheetId': sheet_id, 'dimension': 'ROWS', 'startIndex': row_index, 'endIndex': row_index + 1}}}
            service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': [request]}).execute()
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                st.error(f"Gagal hapus baris: {e}")
                return False

# --- 3. SISTEM LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
        st.session_state.user_nama = ""
    if not st.session_state.password_correct:
        st.markdown("<h1 style='text-align: center; color: #1f3a93;'>🔐 Akses Terkunci - PT. Finpac</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.container():
                st.write("Silakan login untuk mengakses Sistem Laporan Pengeluaran.")
                user_input = st.selectbox("Pilih Nama Anda:", list(USERS_CREDENTIALS.keys()))
                pwd_input = st.text_input("Masukkan Password Anda:", type="password")
                if st.button("Masuk", use_container_width=True):
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
    st.sidebar.header(f"Halo, {st.session_state.user_nama}")
    if st.sidebar.button("Log Out"):
        st.session_state.password_correct = False
        st.rerun()

    is_admin = st.session_state.user_nama == "Admin"
    
    if is_admin:
        tabs = st.tabs(["👨‍💼 Tab Admin (Semua Tim)"])
        
        with tabs[0]:
            st.header("👨‍💼 Panel Monitoring Admin")
            st.write("Pantau rincian biaya, konfirmasi pembayaran bon tim, dan hitung pengeluaran mingguan.")
            
            list_tim = [nama for nama in USERS_CREDENTIALS.keys() if nama != "Admin"]
            target_user = st.selectbox("🎯 Pilih Nama Teknisi/User:", list_tim)
            st.divider()
            
            df_admin = get_user_data(target_user)
            if not df_admin.empty:
                df_admin['original_row_index'] = df_admin.index + 2
                df_admin['Total_Angka'] = df_admin['Total'].astype(str).str.replace(',', '').astype(float)
                
                st.write("📅 **Filter Tanggal Laporan**")
                col_d1, col_d2 = st.columns(2)
                tgl_mulai_admin = col_d1.date_input("Dari Tanggal", datetime.now() - timedelta(days=7), key="d1_admin")
                tgl_akhir_admin = col_d2.date_input("Sampai Tanggal", datetime.now(), key="d2_admin")
                
                mask_admin = (df_admin['Tanggal'].dt.date >= tgl_mulai_admin) & (df_admin['Tanggal'].dt.date <= tgl_akhir_admin)
                df_admin_filtered = df_admin.loc[mask_admin].copy()
                
                st.subheader(f"📋 Spreadsheet Laporan: {target_user}")
                
                if not df_admin_filtered.empty:
                    st.caption("💡 Petunjuk: Baris berwarna **Kuning** adalah tugas **Lembur**. Centang 'Status Lunas' lalu klik tombol Simpan.")
                    
                    df_sheet = df_admin_filtered.copy()
                    df_sheet['Tanggal'] = df_sheet['Tanggal'].dt.strftime('%Y-%m-%d')
                    
                    cleaned_links = []
                    for val in df_sheet['Link GDrive']:
                        val_str = str(val)
                        urls = re.findall(r'(https?://[^\s",]+)', val_str)
                        if urls:
                            cleaned_links.append(urls[0])
                        else:
                            cleaned_links.append(None)
                            
                    df_sheet['Link Dokumen'] = cleaned_links
                    df_sheet['Status Lunas'] = df_sheet['Status Bayar'] == "Sudah Dibayar Admin"
                    
                    kolom_tampil = ["Tanggal", "Customer", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link Dokumen", "Status Lunas", "Is_Lembur"]
                    df_tampil = df_sheet[kolom_tampil]
                    
                    def warnai_baris(row):
                        if row.get('Is_Lembur', False):
                            return ['background-color: #fff2cc'] * len(row)
                        return [''] * len(row)
                        
                    styled_df = df_tampil.style.apply(warnai_baris, axis=1)
                    
                    edited_df = st.data_editor(
                        styled_df,
                        use_container_width=True,
                        hide_index=True,
                        disabled=["Tanggal", "Customer", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link Dokumen"],
                        column_config={
                            "Link Dokumen": st.column_config.LinkColumn(
                                "📄 Link Dokumen", 
                                help="Klik untuk membuka PDF Service Report di GDrive",
                                display_text="Buka Lampiran"
                            ),
                            "Is_Lembur": None 
                        }
                    )
                    
                    if st.button("💾 Simpan Perubahan Pembayaran"):
                        perubahan_terjadi = False
                        with st.spinner("Menyimpan status ke Google Sheets..."):
                            for idx, row in edited_df.iterrows():
                                nilai_baru_checkbox = row['Status Lunas']
                                nilai_lama_checkbox = df_sheet.loc[idx, 'Status Lunas']
                                
                                if nilai_baru_checkbox != nilai_lama_checkbox:
                                    original_row = int(df_admin_filtered.loc[idx, 'original_row_index'])
                                    status_teks = "Sudah Dibayar Admin" if nilai_baru_checkbox else ""
                                    
                                    update_payment_status(target_user, original_row, status_teks)
                                    perubahan_terjadi = True
                                    
                        if perubahan_terjadi:
                            st.success("✅ Semua status pembayaran berhasil diperbarui!")
                            st.rerun()
                        else:
                            st.info("Tidak ada perubahan status yang diubah.")
                            
                    st.divider()
                    total_terpilih = df_admin_filtered['Total_Angka'].sum()
                    st.metric(label=f"📊 Total Pengeluaran (Tabel Terpilih)", value=f"Rp {total_terpilih:,.0f}")
                
                else:
                    st.info(f"Tidak ada data laporan pada rentang tanggal {tgl_mulai_admin.strftime('%d/%m/%Y')} hingga {tgl_akhir_admin.strftime('%d/%m/%Y')}.")
            else:
                st.info(f"Belum ada riwayat data laporan yang masuk dari {target_user}.")
                
    else:
        tabs = st.tabs(["📝 Input Laporan", "📊 Riwayat & Rincian"])

        # --- TAB 1: INPUT LAPORAN (DENGAN OPSI SIMPAN DRAF LOKAL) ---
        with tabs[0]:
            if 'saved_draft' in st.session_state and st.session_state.saved_draft:
                col_draft_info, col_draft_clear = st.columns([4, 1])
                with col_draft_info:
                    cust_draft_name = st.session_state.saved_draft.get('customer', 'Tanpa Nama')
                    st.info(f"📂 **Draf Tersimpan Ditemukan!** Form di bawah telah diisi dari draf customer: **{cust_draft_name}**")
                with col_draft_clear:
                    if st.button("🗑️ Hapus Draf", use_container_width=True):
                        del st.session_state.saved_draft
                        st.toast("Draf berhasil dihapus!", icon="🧹")
                        st.rerun()

            d = st.session_state.saved_draft if 'saved_draft' in st.session_state else {}
            opsi_biaya_default = d.get('opsi_biaya', ["Bensin", "Toll", "Parkir"])

            opsi_biaya = st.sidebar.multiselect("Pilih Input:", ["Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain"], default=opsi_biaya_default)
            lebar_kop = st.sidebar.slider("Lebar Kop (mm)", 30, 190, 70)
            spasi_bawah = st.sidebar.slider("Spasi Bawah (mm)", 10, 80, 50)
            lebar_nota = st.sidebar.slider("Lebar Nota (mm)", 50, 190, 90)
            kop_exist = os.path.exists(KOP_FILE_PATH)

            with st.form("main_form", clear_on_submit=False):
                if kop_exist: 
                    st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
                else:
                    st.warning("⚠️ File 'kop_tetap.jpg' tidak ditemukan.")
                    
                c_id1, c_id2 = st.columns(2)
                nama_teknisi = c_id1.text_input("Nama Pelaksana", value=st.session_state.user_nama, disabled=True)
                
                tgl_default = d.get('tgl_input', datetime.now())
                if isinstance(tgl_default, str):
                    try:
                        tgl_default = datetime.strptime(tgl_default, '%Y-%m-%d').date()
                    except Exception:
                        tgl_default = datetime.now()
                tgl_input = c_id2.date_input("Tanggal Tugas", tgl_default)
                
                customer = st.text_input("Nama Customer / Perusahaan:", value=d.get('customer', ''))
                
                list_mesin = ["Kilian", "Romaco", "Siebler", "MG2", "Frewitt", "Truking", "FrymaKoruma", "Stephan", "Lainnya"]
                idx_mesin = list_mesin.index(d.get('mesin')) if d.get('mesin') in list_mesin else 0
                mesin = st.selectbox("Pilih Mesin:", list_mesin, index=idx_mesin)
                
                detail = st.text_area("Detail Pekerjaan:", value=d.get('detail', ''))
                keperluan = f"[{mesin}] {detail}"
                
                bensin = toll = parkir = makan_teknisi = uang_makan = hotel = lain_lain = 0
                col_a, col_b = st.columns(2)
                if "Bensin" in opsi_biaya: bensin = col_a.number_input("Bensin", min_value=0, value=int(d.get('bensin', 0)))
                if "Toll" in opsi_biaya: toll = col_b.number_input("Toll", min_value=0, value=int(d.get('toll', 0)))
                col_c, col_d = st.columns(2)
                if "Parkir" in opsi_biaya: parkir = col_c.number_input("Parkir", min_value=0, value=int(d.get('parkir', 0)))
                if "Makan Teknisi" in opsi_biaya: makan_teknisi = col_d.number_input("Makan Teknisi", min_value=0, value=int(d.get('makan_teknisi', 0)))
                
                if "Uang Makan" in opsi_biaya: uang_makan = st.number_input("Uang Makan (Luar Kota)", min_value=0, value=int(d.get('uang_makan', 0)))
                if "Hotel" in opsi_biaya: hotel = st.number_input("Biaya Hotel", min_value=0, value=int(d.get('hotel', 0)))
                if "Lain-lain" in opsi_biaya: lain_lain = st.number_input("Lain-lain", min_value=0, value=int(d.get('lain_lain', 0)))
                
                is_lembur = st.checkbox("⚠️ Centang jika kerja Lembur", value=d.get('is_lembur', False))
                
                bukti_files = st.file_uploader("📸 Nota", accept_multiple_files=True, type=['jpg','png','jpeg','pdf'])
                report_file = st.file_uploader("📄 Service Report", type=['pdf'])
                
                c_form_btn1, c_form_btn2 = st.columns(2)
                with c_form_btn1:
                    btn_draft = st.form_submit_button("💾 SIMPAN DRAF LAPORAN")
                with c_form_btn2:
                    btn_preview = st.form_submit_button("🔍 TAMPILKAN PREVIEW LAPORAN")

            if btn_draft:
                st.session_state.saved_draft = {
                    "customer": customer, "tgl_input": tgl_input, "mesin": mesin, "detail": detail,
                    "bensin": bensin, "toll": toll, "parkir": parkir, "makan_teknisi": makan_teknisi,
                    "uang_makan": uang_makan, "hotel": hotel, "lain_lain": lain_lain,
                    "is_lembur": is_lembur, "opsi_biaya": opsi_biaya
                }
                st.toast("✅ Draf isian laporan berhasil disimpan!", icon="💾")
                st.rerun()

            if btn_preview:
                with st.spinner("Menyiapkan preview laporan & lampiran..."):
                    try:
                        total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + lain_lain
                        tgl_iso = tgl_input.strftime('%Y-%m-%d')
                        tgl_cetak = tgl_input.strftime('%d/%m/%Y')
                        
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
                        
                        dict_biaya = {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan (LK)": uang_makan, "Hotel": hotel, "Lain-lain": lain_lain}
                        for k, v in dict_biaya.items():
                            if v > 0:
                                pdf.cell(100, 8, f" {k}", 1); pdf.cell(60, 8, f" Rp {v:,}", 1, 1)
                        pdf.set_font("Arial", "B", 11); pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True); pdf.cell(60, 10, f" Rp {total:,}", 1, 1, 'L', True)

                        if is_lembur:
                            pdf.ln(4)
                            pdf.set_fill_color(255, 255, 0)
                            pdf.set_font("Arial", "B", 11)
                            pdf.cell(160, 9, f" Belum termasuk lembur tgl ({tgl_cetak})", 0, 1, 'L', True)

                        unique_id = uuid.uuid4().hex
                        temp_n = []; nota_pdfs = []
                        preview_attachments = []
                        
                        if bukti_files:
                            pdf.add_page(); pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True); pdf.ln(5)
                            for i, f in enumerate(bukti_files):
                                file_bytes = f.read()
                                f.seek(0)
                                if f.type == "application/pdf": 
                                    nota_pdfs.append(f)
                                    pdf_imgs = pdf_bytes_to_images(file_bytes)
                                    for idx_p, img_p in enumerate(pdf_imgs):
                                        preview_attachments.append((f"Nota PDF #{i+1} (Hal. {idx_p+1})", img_p))
                                else:
                                    img = Image.open(f).convert("RGB")
                                    preview_attachments.append((f"Nota Gambar #{i+1}", img))
                                    t_n = f"temp_nota_{unique_id}_{i}.jpg"
                                    img.save(t_n, "JPEG")
                                    temp_n.append(t_n)
                                    pdf.image(t_n, x=10, w=lebar_nota); pdf.ln(10)

                        if report_file:
                            rep_bytes = report_file.read()
                            report_file.seek(0)
                            rep_imgs = pdf_bytes_to_images(rep_bytes)
                            for idx_r, img_r in enumerate(rep_imgs):
                                preview_attachments.append((f"Service Report PDF (Hal. {idx_r+1})", img_r))

                        main_out = f"temp_render_{unique_id}.pdf"
                        pdf.output(main_out)
                        
                        merger = PdfWriter()
                        merger.append(main_out)
                        for n_pdf in nota_pdfs: merger.append(io.BytesIO(n_pdf.read()))
                        if report_file: merger.append(io.BytesIO(report_file.read()))
                        
                        f_buf = io.BytesIO(); merger.write(f_buf); f_buf.seek(0)
                        
                        st.session_state.preview_pdf_bytes = f_buf.getvalue()
                        st.session_state.preview_attachments = preview_attachments
                        st.session_state.preview_data = {
                            "customer": customer, "tgl_iso": tgl_iso, "tgl_cetak": tgl_cetak, "nama_teknisi": nama_teknisi,
                            "keperluan": keperluan, "dict_biaya": dict_biaya, "bensin": bensin, "toll": toll, "parkir": parkir,
                            "makan_teknisi": makan_teknisi, "uang_makan": uang_makan, "hotel": hotel,
                            "lain_lain": lain_lain, "total": total, "is_lembur": is_lembur,
                            "count_nota": len(bukti_files), "has_report": bool(report_file)
                        }
                        
                        if os.path.exists(main_out): os.remove(main_out)
                        for t in temp_n: 
                            if os.path.exists(t): os.remove(t)
                    
                    except Exception as e:
                        st.error(f"Gagal memproses Preview: {e}")

            if 'preview_pdf_bytes' in st.session_state and st.session_state.preview_pdf_bytes:
                st.markdown("---")
                st.subheader("📑 Visual Print Preview Laporan & Seluruh Lampiran PDF")
                
                p = st.session_state.preview_data
                
                with st.container(border=True):
                    if kop_exist:
                        st.image(KOP_FILE_PATH, width=int(lebar_kop * 3))
                    st.markdown(f"### **Customer: {p.get('customer', '')}**")
                    st.write(f"**Pelaksana:** {p.get('nama_teknisi', '')} | **Tanggal:** {p.get('tgl_cetak', '')}")
                    st.write(f"**Detail Pekerjaan:** {p.get('keperluan', '')}")
                    st.divider()
                    
                    st.markdown("##### 💵 Rincian Pengeluaran Biaya:")
                    df_preview_biaya = pd.DataFrame([
                        {"Kategori Biaya": k, "Nominal": f"Rp {v:,.0f}"} 
                        for k, v in p.get('dict_biaya', {}).items() if v > 0
                    ])
                    if not df_preview_biaya.empty:
                        st.table(df_preview_biaya)
                    
                    st.markdown(f"### **TOTAL PENGELUARAN: Rp {p.get('total', 0):,.0f}**")
                    
                    if p.get('is_lembur', False):
                        st.warning(f"🟨 **Status Lembur:** Belum termasuk lembur tgl ({p.get('tgl_cetak', '')})")
                    
                    st.divider()
                    st.markdown("##### 📸 Visual Preview Seluruh Lampiran (Nota Gambar, PDF Nota, & PDF Service Report):")
                    
                    if 'preview_attachments' in st.session_state and st.session_state.preview_attachments:
                        for lbl, img_obj in st.session_state.preview_attachments:
                            st.write(f"📎 **{lbl}**")
                            st.image(img_obj, use_container_width=True)
                            st.write("")
                    else:
                        st.caption("Tidak ada lampiran dokumen/gambar yang diunggah.")

                st.write("") 
                col_conf1, col_conf2 = st.columns(2)
                
                if col_conf1.button("✅ Data Benar, Simpan ke Database", use_container_width=True):
                    with st.spinner("Mengunggah data ke Google Sheets..."):
                        append_to_sheets(
                            p['nama_teknisi'], 
                            [p['tgl_iso'], p['customer'], p['nama_teknisi'], p['keperluan'], 
                             p['bensin'], p['toll'], p['parkir'], p['makan_teknisi'], 
                             p['uang_makan'], p['hotel'], p['lain_lain'], p['total'], "", ""], 
                            p['is_lembur']
                        )
                        
                        st.session_state.pdf_data = st.session_state.preview_pdf_bytes
                        st.session_state.pdf_name = f"Laporan_{p['customer']}_{p['tgl_iso']}.pdf"
                        st.session_state.last_customer = p['customer']
                        st.session_state.pdf_ready = True
                        
                        del st.session_state.preview_data
                        del st.session_state.preview_pdf_bytes
                        if 'preview_attachments' in st.session_state:
                            del st.session_state.preview_attachments
                        if 'saved_draft' in st.session_state:
                            del st.session_state.saved_draft
                        st.rerun()

                if col_conf2.button("❌ Batal / Edit Kembali", use_container_width=True):
                    del st.session_state.preview_data
                    del st.session_state.preview_pdf_bytes
                    if 'preview_attachments' in st.session_state:
                        del st.session_state.preview_attachments
                    st.rerun()

            if 'pdf_ready' in st.session_state and st.session_state.pdf_ready:
                st.success(f"✅ Data {st.session_state.last_customer} Berhasil Disimpan di Database!")
                st.download_button(
                    label="📥 KLIK DI SINI UNTUK DOWNLOAD PDF LAPORAN", 
                    data=st.session_state.pdf_data, 
                    file_name=st.session_state.pdf_name,
                    mime="application/pdf"
                )
                if st.button("🧹 Bersihkan Form / Input Baru"):
                    for key in ['pdf_ready', 'pdf_data', 'pdf_name', 'last_customer', 'preview_data', 'preview_pdf_bytes', 'preview_attachments', 'saved_draft']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

        # --- TAB 2: RIWAYAT MANDIRI ---
        with tabs[1]:
            st.header(f"📊 Riwayat: {st.session_state.user_nama}")
            
            st.write("📅 **Filter Tanggal Riwayat**")
            col_u1, col_u2 = st.columns(2)
            tgl_mulai_user = col_u1.date_input("Dari Tanggal", datetime.now() - timedelta(days=30), key="d1_user")
            tgl_akhir_user = col_u2.date_input("Sampai Tanggal", datetime.now(), key="d2_user")
            st.divider()

            df = get_user_data(st.session_state.user_nama)
            if not df.empty:
                df['original_row_index'] = df.index + 2
                
                mask_user = (df['Tanggal'].dt.date >= tgl_mulai_user) & (df['Tanggal'].dt.date <= tgl_akhir_user)
                df_filtered = df.loc[mask_user].copy()
                
                if not df_filtered.empty:
                    for i, row in df_filtered.iterrows():
                        tgl_str = row['Tanggal'].strftime('%d/%m/%Y')
                        cust_name = row.get('Customer', 'Unknown')
                        label_hyperlink = f"{cust_name}_{tgl_str}"
                        
                        lembur_marker = " 🟨 (Lembur)" if row.get('Is_Lembur', False) else ""

                        with st.expander(f"📅 {tgl_str} - {cust_name}{lembur_marker}"):
                            if row.get('Is_Lembur', False):
                                st.warning("⚠️ Laporan ini ditandai sebagai pekerjaan lembur.")
                                
                            status_bayar_user = row.iloc[13] if len(row) >= 14 else ""
                            if status_bayar_user == "Sudah Dibayar Admin":
                                st.success("💰 **Bon Sudah Dibayarkan oleh Admin**")
                            else:
                                st.warning("⏳ **Status: Menunggu Pembayaran (Pending)**")
                                
                            st.markdown(f"**Customer:** {cust_name}")
                            
                            raw_link = row.iloc[12] if len(row) >= 13 else ""
                            display_link = ""
                            
                            if 'HYPERLINK' in str(raw_link):
                                urls = re.findall(r'"(http[^"]+)"', str(raw_link))
                                if urls: display_link = urls[0]
                            elif str(raw_link).startswith("http"):
                                display_link = str(raw_link)

                            if display_link:
                                st.success(f"🔗 [Buka PDF: {label_hyperlink}]({display_link})")
                            
                            st.divider()
                            st.write("🔗 **Update Link GDrive (Label otomatis rapi):**")
                            c_link, c_save = st.columns([3, 1])
                            with c_link:
                                link_val = st.text_input("Paste Link PDF:", value=display_link, key=f"link_txt_{i}", label_visibility="collapsed")
                            with c_save:
                                if st.button("💾 Simpan", key=f"btn_link_{i}"):
                                    if update_gdrive_link(st.session_state.user_nama, int(row['original_row_index']), link_val, label_hyperlink):
                                        st.toast("Link berhasil disimpan!", icon="✅")
                                        st.rerun()

                            st.divider()
                            list_kategori = {"Bensin": "Bensin", "Toll": "Toll", "Parkir": "Parkir", "Makan Teknisi": "Makan Teknisi", "Uang Makan": "Uang Makan", "Hotel": "Hotel", "Lain-lain": "Lain-lain"}
                            for label, kolom in list_kategori.items():
                                values_cell = row.get(kolom, 0)
                                try:
                                    val = float(str(values_cell).replace(',', ''))
                                    if val > 0: st.write(f"✅ {label}: Rp {val:,.0f}")
                                except Exception: continue
                            
                            st.subheader(f"Total: Rp {float(str(row.get('Total', 0)).replace(',', '')):,.0f}")
                            
                            if status_bayar_user == "Sudah Dibayar Admin":
                                st.error("🔒 Laporan ini tidak dapat dihapus karena sudah dikonfirmasi lunas oleh Admin.")
                            else:
                                if st.button(f"🗑️ Hapus Laporan Ini", key=f"del_lap_{i}"):
                                    delete_user_row(st.session_state.user_nama, int(row['original_row_index']) - 1)
                                    st.success("Data berhasil dihapus!"); st.rerun()
                else:
                    st.info(f"Tidak ada laporan pada rentang tanggal {tgl_mulai_user.strftime('%d/%m/%Y')} hingga {tgl_akhir_user.strftime('%d/%m/%Y')}.")
            else:
                st.info("Belum ada data riwayat sama sekali.")
