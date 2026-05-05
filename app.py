import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF
from pypdf import PdfWriter
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
import os

# --- 1. KONFIGURASI GOOGLE SHEETS ---
SPREADSHEET_ID = "1wNpbzzumbN9cSJZCYufEfZpIw4DdKp8Tunfuoc13CrM" 
RANGE_NAME = "Pengeluaran!A:H" # Ambil semua kolom A sampai H

def get_sheets_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('sheets', 'v4', credentials=creds)

# Fungsi ambil data untuk laporan kumulatif
def get_all_data():
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0]) # Baris 1 sebagai header

def append_to_sheets(data):
    service = get_sheets_service()
    body = {'values': [data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range="Pengeluaran!A1",
        valueInputOption="USER_ENTERED", body=body).execute()

# --- 2. ANTARMUKA PENGGUNA ---
st.set_page_config(page_title="Sistem Laporan Wahyudi", layout="centered")

# TABS: Memisahkan Input Harian dan Laporan Mingguan
tab1, tab2 = st.tabs(["📝 Input Harian", "📅 Laporan Kumulatif"])

with tab1:
    st.header("Input Pengeluaran Baru")
    with st.form("main_form", clear_on_submit=True):
        nama = st.text_input("Nama Personel", value="Wahyudi")
        tgl = st.date_input("Tanggal", datetime.now())
        keperluan = st.text_area("Detail Pekerjaan")
        c1, c2 = st.columns(2)
        bensin = c1.number_input("Bensin (Rp)", min_value=0)
        toll = c2.number_input("Toll (Rp)", min_value=0)
        makan = c1.number_input("Makan (Rp)", min_value=0)
        parkir = c2.number_input("Parkir (Rp)", min_value=0)
        
        bukti_files = st.file_uploader("Upload Nota", accept_multiple_files=True, type=['jpg','png','jpeg'])
        submit = st.form_submit_button("Simpan Data")

    if submit:
        total = bensin + toll + makan + parkir
        append_to_sheets([str(tgl), nama, keperluan, bensin, toll, makan, parkir, total])
        st.success("Data berhasil tersimpan di Google Sheets!")

with tab2:
    st.header("Generate PDF Mingguan")
    st.write("Fitur ini akan merangkum semua data pengeluaran dalam 7 hari terakhir.")
    
    if st.button("Tampilkan Data & Siapkan PDF"):
        df = get_all_data()
        if not df.empty:
            # Filter data 7 hari terakhir
            df['Tanggal'] = pd.to_datetime(df['Tanggal'])
            tgl_awal = datetime.now() - timedelta(days=7)
            df_filtered = df[df['Tanggal'] >= tgl_awal]
            
            if not df_filtered.empty:
                st.dataframe(df_filtered) # Tampilkan tabel di layar
                
                # --- PROSES PDF KUMULATIF ---
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "REKAP PENGELUARAN MINGGUAN", ln=True, align="C")
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 10, f"Periode: {tgl_awal.date()} s/d {datetime.now().date()}", ln=True, align="C")
                pdf.ln(5)
                
                # Header Tabel PDF
                pdf.set_font("Arial", "B", 10)
                pdf.cell(30, 10, "Tanggal", 1)
                pdf.cell(60, 10, "Keperluan", 1)
                pdf.cell(30, 10, "Total", 1)
                pdf.ln()
                
                # Isi Tabel
                pdf.set_font("Arial", "", 10)
                grand_total = 0
                for index, row in df_filtered.iterrows():
                    pdf.cell(30, 10, str(row['Tanggal'].date()), 1)
                    pdf.cell(60, 10, str(row['Keperluan'])[:30], 1)
                    pdf.cell(30, 10, f"{int(row['Total']):,}", 1)
                    pdf.ln()
                    grand_total += int(row['Total'])
                
                pdf.set_font("Arial", "B", 10)
                pdf.cell(90, 10, "GRAND TOTAL", 1)
                pdf.cell(30, 10, f"{grand_total:,}", 1)
                
                pdf_output = bytes(pdf.output())
                
                st.download_button(
                    label="📥 Download PDF Mingguan",
                    data=pdf_output,
                    file_name=f"Rekap_Mingguan_{datetime.now().date()}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("Tidak ada data dalam 7 hari terakhir.")
        else:
            st.error("Gagal mengambil data dari Google Sheets.")
