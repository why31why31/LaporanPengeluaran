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

def append_to_sheets(nama_user, data, is_lembur=False):
    try:
        service = get_gcp_service('sheets', 'v4')
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_names = [s.get('properties', {}).get('title') for s in spreadsheet.get('sheets', [])]
        
        if nama_user not in sheet_names:
            batch_request = {'requests': [{'addSheet': {'properties': {'title': nama_user}}}]}
            service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=batch_request).execute()
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
        if match:
            row_index = int(match.group(1))
            
            spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
            sheet_id = next(s['properties']['sheetId'] for s in spreadsheet['sheets'] if s['properties']['title'] == nama_user)
            
            if is_lembur:
                bg_color = {"red": 1.0, "green": 1.0, "blue": 0.0} 
            else:
                bg_color = {"red": 1.0, "green": 1.0, "blue": 1.0} 
                
            requests = [
                {
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
                }
            ]
            service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={'requests': requests}).execute()
                
    except Exception as e:
        st.error(f"Gagal simpan ke Sheets: {e}")

def get_user_data(nama_user):
    try:
        service = get_gcp_service('sheets', 'v4')
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:N").execute()
        values = result.get('values', [])
        
        result_formula = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{nama_user}'!A:N", valueRenderOption="FORMULA").execute()
        formulas = result_formula.get('values', [])
        
        if not values or len(values) < 2: 
            return pd.DataFrame()
        
        max_cols = 14
        processed_values = []
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
            
        if not processed_values:
            return pd.DataFrame()
            
        df = pd.DataFrame(processed_values, columns=header)
        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        df = df.dropna(subset=['Tanggal'])
        df = df.sort_values(by='Tanggal', ascending=False)
        return df
    except Exception as e:
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
            st.write("Pantau rincian biaya, konfirmasi pembayaran bon tim, dan hitung pengeluaran mingguan.")
            
            list_tim = [nama for nama in USERS_CREDENTIALS.keys() if nama != "Admin"]
            target_user = st.selectbox("🎯 Pilih Nama Teknisi/User:", list_tim)
            
            st.divider()
            
            df_admin = get_user_data(target_user)
            
            if not df_admin.empty:
                df_admin['original_row_index'] = df_admin.index + 2
                df_admin['Total_Angka'] = df_admin['Total'].astype(str).str.replace(',', '').astype(float)
                
                # --- FILTER TANGGAL ADMIN ---
                st.write("📅 **Filter Tanggal Laporan**")
                col_d1, col_d2 = st.columns(2)
                tgl_mulai_admin = col_d1.date_input("Dari Tanggal", datetime.now() - timedelta(days=7), key="d1_admin")
                tgl_akhir_admin = col_d2.date_input("Sampai Tanggal", datetime.now(), key="d2_admin")
                
                # Menyaring dataframe berdasarkan rentang tanggal yang dipilih
                mask_admin = (df_admin['Tanggal'].dt.date >= tgl_mulai_admin) & (df_admin['Tanggal'].dt.date <= tgl_akhir_admin)
                df_admin_filtered = df_admin.loc[mask_admin].copy()
                
                st.subheader(f"📋 Spreadsheet Laporan: {target_user}")
                
                if not df_admin_filtered.empty:
                    st.caption("💡 Petunjuk: Kolom 'Link Dokumen' berisi tautan langsung ke Google Drive. Anda bisa mencentang kolom 'Status Lunas' lalu klik tombol di bawah untuk menyimpan.")
                    
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
                    
                    kolom_tampil = ["Tanggal", "Customer", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link Dokumen", "Status Lunas"]
                    df_tampil = df_sheet[kolom_tampil]
                    
                    edited_df = st.data_editor(
                        df_tampil,
                        use_container_width=True,
                        hide_index=True,
                        disabled=["Tanggal", "Customer", "Keperluan", "Bensin", "Toll", "Parkir", "Makan Teknisi", "Uang Makan", "Hotel", "Lain-lain", "Total", "Link Dokumen"],
                        column_config={
                            "Link Dokumen": st.column_config.LinkColumn(
                                "📄 Link Dokumen", 
                                help="Klik untuk membuka PDF Service Report di GDrive",
                                display_text="Buka Lampiran"
                            )
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
                    
                    # Total pengeluaran sekarang menghitung HANYA data yang tampil di tabel
                    total_terpilih = df_admin_filtered['Total_Angka'].sum()
                    st.metric(label=f"📊 Total Pengeluaran (Tabel Terpilih)", value=f"Rp {total_terpilih:,.0f}")
                
                else:
                    st.info(f"Tidak ada data laporan pada rentang tanggal {tgl_mulai_admin.strftime('%d/%m/%Y')} hingga {tgl_akhir_admin.strftime('%d/%m/%Y')}.")
                
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
                btn_sub = st.form_submit_button("💾 SIMPAN & GENERATE LAPORAN")

            if 'pdf_ready' in st.session_state and st.session_state.pdf_ready:
                st.success(f"✅ Data {st.session_state.last_customer} Berhasil Disimpan!")
                st.download_button(
                    label="📥 KLIK DI SINI UNTUK DOWNLOAD PDF", 
                    data=st.session_state.pdf_data, 
                    file_name=st.session_state.pdf_name,
                    mime="application/pdf"
                )
                if st.button("🧹 Bersihkan Form / Input Baru"):
                    del st.session_state.pdf_ready
                    del st.session_state.pdf_data
                    del st.session_state.pdf_name
                    del st.session_state.last_customer
                    st.rerun()

            if btn_sub:
                with st.spinner("Sedang memproses..."):
                    try:
                        total = bensin + toll + parkir + makan_teknisi + uang_makan + hotel + lain_lain
                        tgl_iso = tgl_input.strftime('%Y-%m-%d')
                        tgl_cetak = tgl_input.strftime('%d/%m/%Y')
                        
                        append_to_sheets(nama_teknisi, [tgl_iso, customer, nama_teknisi, keperluan, bensin, toll, parkir, makan_teknisi, uang_makan, hotel, lain_lain, total, "", ""], is_lembur)
                        
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
                        
                        dict_b = {"Bensin": bensin, "Toll": toll, "Parkir": parkir, "Makan Teknisi": makan_teknisi, "Uang Makan (LK)": uang_makan, "Hotel": hotel, "Lain-lain": lain_lain}
                        for k, v in dict_b.items():
                            if v > 0:
                                pdf.cell(100, 8, f" {k}", 1); pdf.cell(60, 8, f" Rp {v:,}", 1, 1)
                        pdf.set_font("Arial", "B", 11); pdf.cell(100, 10, " TOTAL", 1, 0, 'L', True); pdf.cell(60, 10, f" Rp {total:,}", 1, 1, 'L', True)

                        if is_lembur:
                            pdf.ln(4)
                            pdf.set_fill_color(255, 255, 0)
                            pdf.set_font("Arial", "B", 11)
                            pdf.cell(160, 9, f" Belum termasuk lembur tgl ({tgl_cetak})", 0, 1, 'L', True)

                        temp_n = []; nota_pdfs = []
                        if bukti_files:
                            pdf.add_page(); pdf.set_font("Arial", "B", 12); pdf.cell(0, 10, "LAMPIRAN NOTA:", ln=True); pdf.ln(5)
                            for i, f in enumerate(bukti_files):
                                if f.type == "application/pdf": nota_pdfs.append(f)
                                else:
                                    img = Image.open(f).convert("RGB"); t_n = f"temp_nota_{i}.jpg"
                                    img.save(t_n, "JPEG"); temp_n.append(t_n)
                                    pdf.image(t_n, x=10, w=lebar_nota); pdf.ln(10)

                        main_out = "temp_render.pdf"; pdf.output(main_out)
                        merger = PdfWriter(); merger.append(main_out)
                        for n_pdf in nota_pdfs: merger.append(io.BytesIO(n_pdf.read()))
                        if report_file: merger.append(io.BytesIO(report_file.read()))
                        
                        f_buf = io.BytesIO(); merger.write(f_buf); f_buf.seek(0)
                        
                        st.session_state.pdf_data = f_buf.getvalue()
                        st.session_state.pdf_name = f"Laporan_{customer}_{tgl_iso}.pdf"
                        st.session_state.last_customer = customer
                        st.session_state.pdf_ready = True
                        
                        if os.path.exists(main_out): os.remove(main_out)
                        for t in temp_n: os.remove(t)
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

        # --- TAB 2: RIWAYAT MANDIRI ---
        with tabs[1]:
            st.header(f"📊 Riwayat: {st.session_state.user_nama}")
            
            # --- FILTER TANGGAL USER ---
            st.write("📅 **Filter Tanggal Riwayat**")
            col_u1, col_u2 = st.columns(2)
            tgl_mulai_user = col_u1.date_input("Dari Tanggal", datetime.now() - timedelta(days=30), key="d1_user")
            tgl_akhir_user = col_u2.date_input("Sampai Tanggal", datetime.now(), key="d2_user")
            st.divider()

            df = get_user_data(st.session_state.user_nama)
            if not df.empty:
                df['original_row_index'] = df.index + 2
                
                # Menyaring dataframe berdasarkan rentang tanggal yang dipilih user
                mask_user = (df['Tanggal'].dt.date >= tgl_mulai_user) & (df['Tanggal'].dt.date <= tgl_akhir_user)
                df_filtered = df.loc[mask_user].copy()
                
                if not df_filtered.empty:
                    for i, row in df_filtered.iterrows():
                        tgl_str = row['Tanggal'].strftime('%d/%m/%Y')
                        cust_name = row.get('Customer', 'Unknown')
                        label_hyperlink = f"{cust_name}_{tgl_str}"

                        with st.expander(f"📅 {tgl_str} - {cust_name}"):
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
                                except: continue
                            st.subheader(f"Total: Rp {float(str(row.get('Total', 0)).replace(',', '')):,.0f}")
                            if st.button(f"🗑️ Hapus Laporan Ini", key=f"del_lap_{i}"):
                                delete_user_row(st.session_state.user_nama, int(row['original_row_index']) - 1)
                                st.success("Data berhasil dihapus!"); st.rerun()
                else:
                    st.info(f"Tidak ada laporan pada rentang tanggal {tgl_mulai_user.strftime('%d/%m/%Y')} hingga {tgl_akhir_user.strftime('%d/%m/%Y')}.")
            else:
                st.info("Belum ada data riwayat sama sekali.")
