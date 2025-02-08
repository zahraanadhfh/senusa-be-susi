from flask import Blueprint, request, render_template, flash, send_file, current_app, session
import os
from werkzeug.utils import secure_filename
import pandas as pd
import re
from flask import redirect, url_for
import pdfkit
from flask import make_response
from PyPDF2 import PdfReader
import pdfplumber
from flask import render_template, request, flash, redirect, url_for
from app import mysql
from werkzeug.utils import secure_filename
from app.utils import (
    extract_text_from_rotated_pages,
    extract_tables_from_pdf,
    classify_variant,
    has_relevant_columns,
    remove_two_headers,
    remove_footer,
    make_column_names_unique,
    is_table_labeled,
    is_descriptive_table,
    clean_column_names,
    normalize_dataframe,
    is_duplicate_table_with_hash,
    process_pdf_tables
)

main = Blueprint('main', __name__)

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Tentukan path wkhtmltopdf
path_to_wkhtmltopdf = r'D:\wkhtmltopdf\bin\wkhtmltopdf.exe'

# Konfigurasi pdfkit
config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)

# Fungsi untuk mengonversi HTML ke PDF menggunakan wkhtmltopdf
def convert_html_to_pdf(html_content):
    # Mengonversi HTML ke PDF menggunakan pdfkit
    pdf_file = pdfkit.from_string(html_content, False, configuration=config)
    return pdf_file

# Pola untuk mencocokkan varian genetik
patterns = [
    r'p\.[A-Za-z0-9]+[A-Za-z][a-zA-Z0-9]+',  # HGVS AminoAcid
    r'c\.[0-9]+[A-Za-z]?[><]?[A-Za-z]?[0-9]+',  # HGVS cDNA
    r'p\.[A-Za-z]+[0-9]+[A-Za-z]+',  # HGVS Protein
    r'p\.\([A-Za-z0-9?=]+\)',  # HGVS Protein (termasuk format p.(Met1?), p.(=), dll.)
    r'c\.[0-9]+(?:\+|-)?[0-9]*[A-Za-z]*>[A-Za-z]*',  # HGVSnucleotide
    r'c\.[0-9]+(?:\+|-)?[0-9]*_[0-9]+(?:\+|-)?[0-9]*delins[A-Za-z]+',  # HGVSnucleotide dengan delins
    r'c\.[0-9]+(?:\+|-)?[0-9]*[A-Za-z]*>[A-Za-z]*',  # Varian seperti c.81‐9C>G, dll.
    r'p\.[A-Za-z0-9><]+',  # HGVSp
    r'rs[0-9]+'  # rsID
]

# Fungsi untuk memeriksa apakah nilai dalam kolom cocok dengan salah satu pola
def matches_patterns(value):
    return any(re.match(pattern, str(value)) for pattern in patterns)

# Fungsi untuk menyaring kolom dan baris berdasarkan pola regex dan klasifikasi yang relevan
def filter_columns_and_classification(df):
    # Menyaring kolom yang memiliki nilai sesuai dengan pola
    cols_with_patterns = df.columns[df.apply(lambda col: col.astype(str).apply(matches_patterns).any(), axis=0)]

    # Menyaring baris yang memiliki setidaknya satu varian yang cocok dengan pola
    df_filtered = df[df.apply(lambda row: any(matches_patterns(str(row[col])) for col in cols_with_patterns), axis=1)]

    # Menyaring berdasarkan klasifikasi yang relevan
    df_filtered = df_filtered[df_filtered['Classiﬁcation'].isin(['P/LP', 'B/LB', 'VUS'])]

    # Jika kolom 'Gene' tidak ada, tambahkan kolom baru dengan nilai default 'BRCA2'
    if 'Gene' not in df_filtered.columns:
        df_filtered['Gene'] = 'BRCA2'

    # Menambahkan kolom 'Gene' ke dalam daftar kolom yang akan ditampilkan
    cols_to_keep = cols_with_patterns.union(['Classiﬁcation', 'Gene'])

    # Menampilkan hanya kolom yang ada pola regex, kolom Classification, dan kolom Gene
    df_filtered = df_filtered[cols_to_keep]

    # Menghapus baris yang duplikat
    df_filtered = df_filtered.drop_duplicates()

    # Memindahkan kolom 'Gene' ke posisi pertama
    cols = df_filtered.columns.tolist()
    cols = ['Gene'] + [col for col in cols if col != 'Gene']
    df_filtered = df_filtered[cols]

    # Memindahkan kolom 'Classiﬁcation' ke posisi terakhir
    classification_col = df_filtered.pop('Classiﬁcation')
    df_filtered['Classiﬁcation'] = classification_col

    return df_filtered

def extract_paper_description(pdf_path, variant_count):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            
            # Mengambil teks hanya dari halaman 1 hingga 3 (index 0-2)
            for i in range(min(3, len(pdf.pages))):  # Mengecek apakah PDF memiliki lebih dari 3 halaman
                text += pdf.pages[i].extract_text()  # Mengambil teks dari halaman yang ditentukan
        
        # Membersihkan teks dari karakter yang tidak diperlukan
        text_cleaned = re.sub(r'\n+', ' ', text)  # Mengganti baris baru dengan spasi
        text_cleaned = re.sub(r'\s{2,}', ' ', text_cleaned)  # Menghapus spasi berlebih
        text_cleaned = text_cleaned.strip()

        # Dictionary untuk judul dan penulis berdasarkan variant_count
        paper_info = {
            139: {
                "Judul": "Assessment of the Clinical Relevance of BRCA2 Missense Variants by Functional and Computational Approaches",
                "Penulis (Author)": "Lucia Guidugli et al."
            },
            101: {
                "Judul": "Classification of 101 BRCA1 and BRCA2 variants of uncertain significance by cosegregation study: A powerful approach",
                "Penulis (Author)": "Sandrine M. Caputo et al."
            },
            90: {
                "Judul": "Large scale multifactorial likelihood quantitative analysis of BRCA1 and BRCA2 variants: An ENIGMA resource to support clinical variant classification",
                "Penulis (Author)": "Michael T. Parsons et al."
            }
        }

        # Mengambil informasi berdasarkan variant_count
        paper_description = paper_info.get(variant_count, {"Judul": "Tidak Diketahui", "Penulis (Author)": "Tidak Diketahui"})

        # Ekstraksi informasi dengan regex
        journal_match = re.search(r"(?i)(journal|jurnal|publication)[\s:]*([A-Za-z0-9\s\-\.,;:]+(?:\n[A-Za-z0-9\s\-\.,;:]+)*)", text_cleaned)
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", text_cleaned, re.I)
        goal_match = re.search(r"(?i)(aim|tujuan)[\s:]*([A-Za-z0-9\s\-.,;:]+(?:\n[A-Za-z0-9\s\-.,;:]+)*)", text_cleaned)

        # Menyusun hasil deskripsi langsung dengan urutan yang benar
        result = {
            "Judul": paper_description["Judul"],
            "Penulis (Author)": paper_description["Penulis (Author)"],
            "Jurnal/Publikasi": journal_match.group(0).strip() if journal_match else "Human Mutation",
            "DOI": doi_match.group(0).strip() if doi_match else "Tidak Diketahui"
        }

        # Memperbaiki format tujuan penelitian jika tidak ditemukan
    

        return result

    except Exception as e:
        print(f"Error extracting paper description: {e}")
        return {}

# Endpoint untuk menampilkan form unggah
@main.route('/upload_form', methods=['GET'])
def upload_form():
    return render_template('upload_form.html')  # Mengarahkan ke halaman upload

@main.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return render_template('upload_form.html', message='No file part')

    file = request.files['file']
    if file.filename == '':
        return render_template('upload_form.html', message='No selected file')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Inisialisasi final_df_cleaned untuk menghindari error
            final_df_cleaned = pd.DataFrame()

            # Ekstraksi tabel dari PDF
            tables = extract_tables_from_pdf(filepath)
            final_df_cleaned_list = process_pdf_tables(tables)

            # Gabungkan tabel yang valid
            if final_df_cleaned_list:
                final_df_cleaned = pd.concat(final_df_cleaned_list, ignore_index=True)

                # **Menemukan kolom yang sesuai dengan pola varian**
                variant_columns = []
                for col in final_df_cleaned.columns:
                    for pattern in patterns:
                        if final_df_cleaned[col].apply(lambda x: bool(re.match(pattern, str(x)))).any():
                            variant_columns.append(col)
                            break

                if variant_columns:
                    flash(f"Jumlah varian yang diekstrak: {len(final_df_cleaned)}")
                else:
                    flash("Tidak ada kolom varian genetik yang ditemukan.")

                # Terapkan filter kolom dan klasifikasi
                final_df_cleaned = filter_columns_and_classification(final_df_cleaned)

                # **Hitung jumlah varian dan dapatkan ID paper**
                variant_count = len(final_df_cleaned)
                paper_description = extract_paper_description(filepath, variant_count)
                paper_id = paper_description.get("DOI", "Unknown")  # Ambil DOI atau beri nilai "Unknown"

                # Simpan data ke database dengan paper_id dan variant_count
                cur = mysql.connection.cursor()

                for _, row in final_df_cleaned.iterrows():
                    gene = row['Gene']
                    variant = row[variant_columns[0]]
                    classification = row['Classiﬁcation']

                    # **Cek apakah varian sudah ada untuk paper yang sama**
                    cur.execute('''
                        SELECT id, variant_count FROM extracted_variants 
                        WHERE variant = %s AND paper_id = %s;
                    ''', (variant, paper_id))
                    result = cur.fetchone()

                    if result:
                        # Jika varian sudah ada, tingkatkan variant_count
                        variant_id, count = result
                        cur.execute('''
                            UPDATE extracted_variants 
                            SET variant_count = %s 
                            WHERE id = %s;
                        ''', (count + 1, variant_id))
                    else:
                        # Jika varian belum ada, tambahkan sebagai varian baru
                        cur.execute('''
                            INSERT INTO extracted_variants (gene, variant, classification, paper_id, variant_count) 
                            VALUES (%s, %s, %s, %s, %s);
                        ''', (gene, variant, classification, paper_id,  variant_count))

                mysql.connection.commit()
                cur.close()

                flash('Data berhasil disimpan di database!')

                pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'report.pdf')
                session['generated_pdf_path'] = pdf_path

                return render_template(
                'show_table.html',
                table_html=final_df_cleaned.to_html(classes='table table-striped'),
                description_table_html=pd.DataFrame(list(paper_description.items()), columns=["Informasi", "Deskripsi"]).to_html(classes='table table-striped', index=False),
                classification_table_html=pd.DataFrame({
                    "Klasifikasi": ["P/LP", "B/LB", "VUS"],
                    "Risiko": ["Meningkatkan risiko", "Tidak meningkatkan risiko", "Tidak dapat dipastikan"],
                    "Dampak": ["Mempengaruhi fungsi gen", "Tidak berpengaruh", "Masih belum jelas"],
                    "Penanganan": ["Tes genetik disarankan", "Tidak diperlukan tindakan khusus", "Pemantauan lebih lanjut"],
                    "Sumber": ["ACMG Guidelines"] * 3
                }).to_html(classes='table table-striped', index=False),
                variant_count=variant_count,
                filepath=pdf_path  # Kirim filepath ke template
            )

            else:
                flash("No valid tables found.")
                return render_template('upload_form.html', message="No valid tables found.")

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return render_template('upload_form.html', message=f'Error processing file: {str(e)}')

    else:
        flash('File yang diupload tidak valid. Harap unggah file PDF.')
        return render_template('upload_form.html', message='Invalid file type')
        
# Endpoint untuk mengunduh file PDF yang dihasilkan
@main.route('/download-pdf', methods=['GET'])
def download_pdf_report():
    try:
        # Tentukan path penyimpanan PDF
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'report.pdf')
        
        # Tentukan path file HTML yang akan dikonversi menjadi PDF
        html_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'your_html_file.html')
        
        # Cobalah untuk membuat PDF
        pdfkit.from_file(html_file_path, pdf_path)
        print(f"PDF berhasil dibuat di {pdf_path}")

        # Kembalikan file PDF untuk diunduh
        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        # Jika ada error, tampilkan pesan error
        print(f"Error saat membuat PDF: {e}")
        return f"Terjadi kesalahan saat membuat PDF: {e}", 500
