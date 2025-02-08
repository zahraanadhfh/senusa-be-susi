import camelot
import pdfplumber
import pandas as pd
import re
import fitz  # PyMuPDF
from pandas.util import hash_pandas_object


# Fungsi untuk memutar halaman PDF dalam memori menggunakan PyMuPDF (rotasi 90 derajat)
def rotate_pdf_in_memory(input_path):
    doc = fitz.open(input_path)
    rotated_pages = []

    for page in doc:
        # Rotasi 90 derajat (untuk landscape)
        page.set_rotation(90)
        rotated_pages.append(page)

    return rotated_pages

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Membersihkan nama kolom dengan menghapus spasi ekstra dan mengganti spasi dengan garis bawah (_).
    """
    df.columns = df.columns.astype(str).str.strip().str.replace(' ', '_')
    return df

def make_column_names_unique(df):
    """
    Menangani kolom duplikat dengan menambahkan suffix '_x' jika ada kolom dengan nama yang sama.
    """
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():  # Cek kolom yang duplikat
        # Temukan kolom duplikat dan beri sufiks yang sesuai
        cols[cols[cols == dup].index.values.tolist()] = [dup + f'_{i}' if i != 0 else dup for i in range(sum(cols == dup))]
    df.columns = cols
    return df

# Fungsi untuk mengekstrak teks dari halaman yang diputar
def extract_text_from_rotated_pages(rotated_pages):
    pages_text = []
    for page in rotated_pages:
        pages_text.append(page.get_text())
    return pages_text

# Fungsi untuk mengekstrak tabel dari PDF menggunakan Camelot
def extract_tables_from_pdf(pdf_path):
    # Ekstrak tabel menggunakan Camelot (rotasi sudah ditangani)
    tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream', edge_tol=200)
    return tables

# Fungsi untuk memverifikasi apakah teks di atas tabel mengandung kata "Table"
def is_table_labeled(page_text, table_bbox):
    """
    Memeriksa apakah ada kata 'Table' dalam teks di atas tabel berdasarkan koordinat bounding box.
    """
    x1, y1, x2, y2 = table_bbox
    upper_text_region = re.split(r'\n', page_text)

    for line in upper_text_region:
        if "table" in line.lower():
            return True
    return False

# Fungsi untuk memverifikasi apakah tabel mengandung kolom yang relevan
def has_relevant_columns(table):
    hgvs_aminodacid_pattern = r'p\.[A-Za-z0-9]+[A-Za-z][a-zA-Z0-9]+'
    hgvs_cdna_pattern = r'c\.[0-9]+[A-Za-z]?[><]?[A-Za-z]?[0-9]+'
    hgvs_protein_pattern = r'p\.[A-Za-z]+[0-9]+[A-Za-z]+'
    hgvs_sp_pattern = r'p\.[A-Za-z0-9><]+'  # Pencocokan pola HGVSp
    rsid_pattern = r'rs[0-9]+'  # Pencocokan pola rsID

    for col in table.columns:
        table[col] = table[col].astype(str)  # Convert the column to string before using .str.contains()
        if (table[col].str.contains(hgvs_aminodacid_pattern, regex=True).any() or
            table[col].str.contains(hgvs_cdna_pattern, regex=True).any() or
            table[col].str.contains(hgvs_protein_pattern, regex=True).any() or
            table[col].str.contains(rsid_pattern, regex=True).any()):
            return True
    return False

# Fungsi untuk memverifikasi apakah tabel mengandung kolom deskriptif
def is_descriptive_table(df):
    if len(df.columns) < 2:  # Tabel dengan kurang dari 2 kolom dianggap deskriptif
        return True

    long_text_count = sum(df.applymap(lambda x: len(x) > 50 if isinstance(x, str) else False).sum())
    total_cells = df.size

    if long_text_count / total_cells > 0.5:  # Jika lebih dari 50% sel berupa teks panjang
        return True

    return False

# Fungsi untuk menghapus dua header dari DataFrame
def remove_two_headers(df):
    if len(df.columns) > 15:
        df_cleaned = df.iloc[5:].reset_index(drop=True)  # Menghapus 5 baris pertama
    else:
        df_cleaned = df.iloc[3:].reset_index(drop=True)  # Menghapus 3 baris pertama

    if len(df_cleaned) == 0:
        return pd.DataFrame()  # Mengembalikan DataFrame kosong jika semua baris terhapus

    df_cleaned.columns = df_cleaned.iloc[0]  # Baris pertama menjadi header kolom
    df_cleaned = df_cleaned[1:].reset_index(drop=True)  # Hapus baris pertama yang menjadi header

    return df_cleaned

# Fungsi untuk menghapus footer dari DataFrame
def remove_footer(df):
    df_cleaned = df[~df.apply(lambda row: row.astype(str).str.len().sum() < 10, axis=1)]
    return df_cleaned

# Fungsi untuk mengklasifikasikan berdasarkan kolom yang relevan
def classify_variant(df):
    # Mapping IARC-5-tier classes to P/LP, B/LB, VUS
    iarc_classification_mapping = {
        1: 'B/LB',  # Benign (BV)
        2: 'B/LB',  # Likely Benign (LBV)
        3: 'VUS',   # Variant of Uncertain Significance
        4: 'P/LP',  # Likely Pathogenic (LPV)
        5: 'P/LP'   # Pathogenic (PV)
    }

    classification_results = []

    for index, row in df.iterrows():
        classification = None
        for col in df.columns:
            # Cek apakah kolom mengandung kata kunci yang relevan
            if any(keyword in col.lower() for keyword in ['classiﬁcation', 'clinical significance', 'tier class', 'class']):
                value = str(row[col]).strip().lower()

                # Jika kolom adalah "class" dan nilainya numerik (1-5)
                if 'class' in col.lower() and value.isdigit():
                    class_value = int(value)
                    if class_value in iarc_classification_mapping:
                        classification = iarc_classification_mapping[class_value]
                        break

                # Jika kolom bukan numerik, gunakan logika sebelumnya
                else:
                    classifications = {
                        'P/LP': ['Pathogenic', 'Likely Pathogenic', 'P', 'LP'],
                        'B/LB': ['Benign', 'Likely Benign', 'B', 'LB'],
                        'VUS': ['Variant of Unknown Significance', 'Intermediate', 'VUS']
                    }
                    for key, values in classifications.items():
                        if any(val.lower() in value for val in values):
                            classification = key
                            break

        classification_results.append(classification if classification else 'Unclassified')

    df['Classiﬁcation'] = classification_results
    return df


# Fungsi untuk normalisasi DataFrame sebelum dibandingkan
def normalize_dataframe(df):
    df = df.applymap(lambda x: x.strip().lower() if isinstance(x, str) else x)  # Normalisasi teks
    df = df.sort_index(axis=1).sort_values(by=df.columns.tolist(), ignore_index=True)  # Sortir kolom dan baris
    return df

# Fungsi untuk memeriksa duplikat tabel dengan hashing
def is_duplicate_table_with_hash(new_table, table_list):
    normalized_new_table = normalize_dataframe(new_table)
    new_table_hash = hash_pandas_object(normalized_new_table).sum()  # Menghasilkan hash untuk tabel baru
    print(f"Hash for new table: {new_table_hash}")  # Debugging hash tabel baru
    
    for existing_table in table_list:
        normalized_existing_table = normalize_dataframe(existing_table)
        existing_table_hash = hash_pandas_object(normalized_existing_table).sum()  # Hash tabel yang ada
        print(f"Hash for existing table: {existing_table_hash}")  # Debugging hash tabel yang ada

        # Bandingkan hash
        if existing_table_hash == new_table_hash:
            print(f"Tabel dianggap duplikat!")  # Tabel ditemukan duplikat
            return True
    return False

# Fungsi untuk memproses tabel dan menghindari duplikat
def process_pdf_tables(tables):
    cleaned_df_list = []  # List untuk menampung tabel yang sudah dibersihkan

    for table in tables:
        df = table.df
        df = clean_column_names(df)

        if has_relevant_columns(df) and not is_descriptive_table(df):
            cleaned_df = remove_two_headers(df)
            cleaned_df = remove_footer(cleaned_df)
            cleaned_df = make_column_names_unique(cleaned_df)
            cleaned_df = classify_variant(cleaned_df)

            # Memeriksa apakah tabel sudah ada berdasarkan hash
            if not is_duplicate_table_with_hash(cleaned_df, cleaned_df_list):
                cleaned_df_list.append(cleaned_df)
            else:
                print(f"Page {table.page} tabel diabaikan karena duplikat.")

    return cleaned_df_list