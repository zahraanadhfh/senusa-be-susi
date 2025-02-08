from flask import Flask, render_template, Blueprint, request, flash, redirect, url_for, send_file
from werkzeug.middleware.proxy_fix import ProxyFix
from app.routes import main  # pastikan ini mengarah ke file routes.py Anda
from flask_mysqldb import MySQL  # Import MySQL
import MySQLdb
from flask_cors import CORS

# Inisialisasi aplikasi Flask
app = Flask(__name__)
CORS(app)

# Konfigurasi aplikasi Flask
app.config['SECRET_KEY'] = '5a10b3eb74992533cf0d5efce67ca7f9'
app.config['UPLOAD_FOLDER'] = './uploads'

# Konfigurasi koneksi MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # Ganti dengan username MySQL Anda
app.config['MYSQL_PASSWORD'] = ''  # Ganti dengan password MySQL Anda
app.config['MYSQL_DB'] = 'genetic_variants_db'  # Nama database yang Anda buat

# Inisialisasi MySQL
mysql = MySQL(app)

# Middleware untuk menangani proxy
app.wsgi_app = ProxyFix(app.wsgi_app)

# Fungsi untuk membuat tabel jika belum ada
def create_table_if_not_exists():
    try:
        with mysql.connection.cursor() as cur:
            # Tambahkan kolom paper_id dan variant_count jika belum ada
            create_table_query = '''
            CREATE TABLE IF NOT EXISTS extracted_variants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                gene VARCHAR(255) NOT NULL,
                variant VARCHAR(255) NOT NULL,
                classification VARCHAR(255) NOT NULL,
                paper_id VARCHAR(50) NOT NULL,  -- ID Paper yang terkait
                variant_count INT DEFAULT 1    -- Jumlah kemunculan varian
            );
            '''
            cur.execute(create_table_query)

            # Tambahkan kolom baru jika tabel sudah ada
            alter_queries = [
                "ALTER TABLE extracted_variants ADD COLUMN paper_id VARCHAR(50) NOT NULL DEFAULT '' AFTER classification;",
                "ALTER TABLE extracted_variants ADD COLUMN variant_count INT DEFAULT 1 AFTER paper_id;"
            ]
            
            for query in alter_queries:
                try:
                    cur.execute(query)
                except:
                    pass  # Kolom sudah ada, lanjutkan saja
            
            mysql.connection.commit()
        print("Table 'extracted_variants' is updated and ready.")
    except Exception as e:
        print(f"Error updating table: {str(e)}")
        
# Menambahkan blueprint untuk menangani rute utama
app.register_blueprint(main)

# Menambahkan route untuk root ("/")
@app.route('/')
def home():
    return redirect(url_for('main.upload_form'))  # Arahkan ke /upload_form



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    # Pastikan tabel sudah ada sebelum aplikasi dijalankan
    create_table_if_not_exists()
    # Menjalankan aplikasi
