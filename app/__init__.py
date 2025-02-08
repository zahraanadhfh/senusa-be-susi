from flask import Flask
from flask_mysqldb import MySQL

mysql = MySQL()  # Inisialisasi objek mysql

def create_app():
    app = Flask(__name__)

    # Konfigurasi MySQL
    app.config['MYSQL_HOST'] = 'localhost'  # Ganti dengan host MySQL Anda
    app.config['MYSQL_USER'] = 'root'  # Ganti dengan username MySQL Anda
    app.config['MYSQL_PASSWORD'] = ''  # Ganti dengan password MySQL Anda
    app.config['MYSQL_DB'] = 'genetic_variants_db'  # Ganti dengan nama database Anda

    # Inisialisasi MySQL dengan aplikasi Flask
    mysql.init_app(app)

    return app
