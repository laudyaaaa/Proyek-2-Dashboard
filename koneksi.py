"""Koneksi ke PostgreSQL (dipakai 02_load.py, 04_text_mining.py, app.py).

Pengaturan dibaca dari:
  - file .env (di laptop), atau
  - Secrets di Streamlit Community Cloud (saat sudah di-deploy).
Lihat .env.example untuk daftar isiannya, dan DEPLOY.md untuk Supabase.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

BASE = Path(__file__).parent
KUNCI = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE")


def _baca_pengaturan():
    """Isi variabel lingkungan dari .env; kalau tidak ada, coba Secrets Streamlit."""
    load_dotenv(BASE / ".env")
    if os.getenv("DB_PASSWORD"):
        return
    try:                                      # di Streamlit Cloud: Settings -> Secrets
        import streamlit as st
        for k in KUNCI:
            if k in st.secrets and not os.getenv(k):
                os.environ[k] = str(st.secrets[k])
    except Exception:                         # bukan dijalankan lewat Streamlit / tanpa secrets
        pass


def buat_engine():
    """Mengembalikan engine SQLAlchemy, atau None kalau pengaturan belum diisi."""
    _baca_pengaturan()
    pwd = os.getenv("DB_PASSWORD")
    if not pwd or pwd == "isi_password_postgres_di_sini":
        return None
    url = URL.create("postgresql+psycopg2",
                     username=os.getenv("DB_USER", "postgres"), password=pwd,
                     host=os.getenv("DB_HOST", "localhost"),
                     port=int(os.getenv("DB_PORT", "5432")),
                     database=os.getenv("DB_NAME", "kominfo_jatim"))
    args = {"connect_timeout": 10}
    if os.getenv("DB_SSLMODE"):               # Supabase: require (koneksi terenkripsi)
        args["sslmode"] = os.getenv("DB_SSLMODE")
    # pool_pre_ping: cek koneksi sebelum dipakai, supaya tidak error setelah database "tidur"
    return create_engine(url, connect_args=args, pool_pre_ping=True)
