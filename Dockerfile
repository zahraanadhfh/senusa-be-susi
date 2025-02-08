# Gunakan image Python resmi
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev

# Salin requirements.txt dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh proyek
COPY . .

# Expose port yang digunakan (misal: 5000 untuk Flask)
EXPOSE 5000

# Perintah untuk menjalankan aplikasi
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]