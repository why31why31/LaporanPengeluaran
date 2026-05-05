import streamlit as st
import pandas as pd
from datetime import datetime
import os
from fpdf import FPDF

st.set_page_config(page_title="Sistem Pengeluaran", layout="centered")

# --- Fungsi Simpan Excel ---
def simpan_ke_excel(data):
    file_ex = "Hasil_Input_Pengeluaran.xlsx"
    df_baru = pd.DataFrame([data])
    if os.path.exists(file_ex):
        df_lama = pd.read_excel(file_ex)
        pd.concat([df_lama, df_baru], ignore_index=True).to_excel(file_ex, index=False)
    else:
        df_baru.to_excel(file_ex, index=False)

# --- Fungsi Membuat PDF ---
def buat_pdf(data, files, output_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "NOTA PENGELUARAN KANTOR", ln=True, align="C")
    pdf.ln(5)
    
    pdf.set_font("Arial", "", 12)
    fields = [
        ("Nama", data['Nama']),
        ("Tanggal", data['Tanggal']),
        ("Keperluan", data['Keperluan']),
        ("-------------------", "-------------------"),
        ("Bensin", f"Rp {data['Bensin']:,}"),
        ("Uang Makan", f"Rp {data['Makan']:,}"),
        ("Toll", f"Rp {data['Toll']:,}"),
        ("Parkir", f"Rp {data['Parkir']:,}"),
        ("Lain-lain", f"Rp {data['Lain-lain']:,}"),
        ("TOTAL", f"Rp {data['Total']:,}")
    ]
    
    for label, value in fields:
        pdf.cell(50, 10, label, border=0)
        pdf.cell(0, 10, f": {value}", border=0, ln=True)
    
    # Tambahkan Lampiran Foto
    if files:
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "LAMPIRAN BUKTI", ln=True)
        for f_path in files:
            # Menyisipkan gambar ke PDF
            try:
                pdf.image(f_path, x=10, w=90) 
                pdf.ln(5)
            except:
                pass
    
    pdf.output(output_path)

# --- UI Utama ---
st.title("📝 Input & Konversi PDF")

with st.form("main_form", clear_on_submit=True):
    nama = st.text_input("Nama")
    tgl = st.date_input("Tanggal")
    keperluan = st.text_area("Keperluan")
    
    c1, c2 = st.columns(2)
    bensin = c1.number_input("Bensin", min_value=0)
    makan = c2.number_input("Makan", min_value=0)
    toll = c1.number_input("Toll", min_value=0)
    parkir = c2.number_input("Parkir", min_value=0)
    lain = c1.number_input("Lain-lain", min_value=0)
    
    bukti_files = st.file_uploader("Upload Bukti (Gambar)", accept_multiple_files=True, type=['jpg', 'jpeg', 'png'])
    
    submit = st.form_submit_button("Simpan & Generate PDF")

if submit:
    total = bensin + makan + toll + parkir + lain
    data_input = {
        "Nama": nama, "Tanggal": str(tgl), "Keperluan": keperluan,
        "Bensin": bensin, "Makan": makan, "Toll": toll, "Parkir": parkir,
        "Lain-lain": lain, "Total": total
    }
    
    # 1. Simpan Excel
    simpan_ke_excel(data_input)
    
    # 2. Simpan File Fisik & List Path untuk PDF
    saved_paths = []
    if not os.path.exists("lampiran"): os.makedirs("lampiran")
    
    for bf in bukti_files:
        p = os.path.join("lampiran", bf.name)
        with open(p, "wb") as f:
            f.write(bf.getbuffer())
        saved_paths.append(p)
    
    # 3. Generate PDF
    pdf_name = f"Nota_{nama}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    buat_pdf(data_input, saved_paths, pdf_name)
    
    st.success(f"✅ Tersimpan! PDF dibuat: {pdf_name}")
    with open(pdf_name, "rb") as f:
        st.download_button("Download PDF Sekarang", f, file_name=pdf_name)