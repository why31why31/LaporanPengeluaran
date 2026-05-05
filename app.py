import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

# --- 1. KONFIGURASI GOOGLE SHEETS ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 
RANGE_NAME = "Pengeluaran!A:H"

def get_sheets_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('sheets', 'v4', credentials=creds)

def get_all_data():
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])

def append_to_sheets(data):
    service = get_sheets_service()
    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A1",
        valueInputOption="USER_ENTERED", body=body).execute()

# --- 2. ANTARMUKA PENGGUNA ---
st.set_page_config(page_title="Sistem Laporan Wahyudi", layout="centered")

tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Pengeluaran Baru")
    # ... (Kode form input harian Bapak yang sebelumnya tetap sama)
    with st.form("main_form", clear_on_submit=True):
        nama_input = st.text_input("Nama Personel", value="Wahyudi")
        tgl_input = st.date_input("Tanggal", datetime.now())
        keperluan_input = st.text_area("Detail Pekerjaan")
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0)
        toll = c2.number_input("Toll (Rp)", min_value=0)
        makan = c1.number_input("Makan (Rp)", min_value=0)
        parkir = c2.number_input("Parkir (Rp)", min_value=0)
        submit = st.form_submit_button("Simpan Data")

    if submit:
        total = bensin + toll + makan + parkir
        append_to_sheets([str(tgl_input), nama_input, keperluan_input, bensin, toll, makan, parkir, total])
        st.success("Data berhasil tersimpan!")

with tab2:
    st.header("Generate Laporan Per Periode")
    st.write("Pilih rentang tanggal untuk merangkum pengeluaran.")
    
    # FILTER TANGGAL (Pilih Tanggal Mulai & Tanggal Selesai)
    tgl_range = st.date_input(
        "Pilih Rentang Tanggal",
        value=(datetime.now(), datetime.now()), # Default hari ini s/d hari ini
        key="range_laporan"
    )
    
    # Cek apakah user sudah pilih kedua tanggal (mulai & selesai)
    if len(tgl_range) == 2:
        tgl_mulai, tgl_selesai = tgl_range
        
        if st.button("Tampilkan & Siapkan PDF Kumulatif"):
            df = get_all_data()
            if not df.empty:
                # Konversi kolom tanggal agar bisa dibandingkan
                df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.date
                
                # Filter berdasarkan pilihan user
                mask = (df['Tanggal'] >= tgl_mulai) & (df['Tanggal'] <= tgl_selesai)
                df_filtered = df.loc[mask]
                
                if not df_filtered.empty:
                    st.subheader(f"Data Periode {tgl_mulai} s/d {tgl_selesai}")
                    st.dataframe(df_filtered, use_container_width=True)
                    
                    # --- PROSES PDF KUMULATIF ---
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Kop Surat Singkat
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, "REKAP PENGELUARAN KUMULATIF", ln=True, align="C")
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 7, f"Periode: {tgl_mulai} s/d {tgl_selesai}", ln=True, align="C")
                    pdf.ln(5)
                    
                    # Header Tabel
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(25, 10, "Tanggal", 1)
                    pdf.cell(100, 10, "Keperluan", 1)
                    pdf.cell(30, 10, "Total", 1)
                    pdf.ln()
                    
                    # Isi Tabel
                    pdf.set_font("Arial", "", 10)
                    grand_total = 0
                    for _, row in df_filtered.iterrows():
                        pdf.cell(25, 10, str(row['Tanggal']), 1)
                        # Potong teks keperluan agar tidak keluar tabel
                        teks_keperluan = str(row['Keperluan'])[:50]
                        pdf.cell(100, 10, teks_keperluan, 1)
                        
                        nilai_total = int(row['Total']) if str(row['Total']).isdigit() else 0
                        pdf.cell(30, 10, f"{nilai_total:,}", 1)
                        pdf.ln()
                        grand_total += nilai_total
                    
                    # Total Akhir
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(125, 10, "TOTAL KESELURUHAN", 1, 0, 'R')
                    pdf.cell(30, 10, f"Rp {grand_total:,}", 1)
                    
                    pdf_output = bytes(pdf.output())
                    
                    st.divider()
                    st.download_button(
                        label=f"📥 Download Rekap {tgl_mulai} s/d {tgl_selesai}",
                        data=pdf_output,
                        file_name=f"Rekap_{tgl_mulai}_to_{tgl_selesai}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.warning("Tidak ada data ditemukan pada rentang tanggal tersebut.")
    else:
        st.info("Silakan pilih tanggal mulai dan tanggal selesai pada kalender di atas.")
