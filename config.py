DB_USERNAME = "root"  # Sesuaikan dengan username MySQL kamu
DB_PASSWORD = ""  # Sesuaikan dengan password MySQL kamu
DB_HOST = "localhost"  # Sesuaikan dengan host MySQL kamu
DB_NAME = "genetic_variants_db"  # Nama database yang ingin digunakan

SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
