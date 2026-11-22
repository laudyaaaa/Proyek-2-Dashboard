"""Tahap 1-3 - Memuat data mentah ke PostgreSQL, lalu cleaning dan pengisian tabel dengan SQL.
Jalankan: python 02_load.py   (setelah file .env siap)

Python di sini hanya mengantar file hasil scraping ke tabel staging (stg_mentah), apa adanya.
Semua pengolahan dikerjakan PostgreSQL:
  schema.sql       -> membuat tabel dan view
  01_cleaning.sql  -> cleaning: stg_mentah -> stg_bersih
  SQL di bawah     -> stg_bersih -> kategori, dim_tanggal, berita
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

import koneksi

BASE = Path(__file__).parent
SRC = BASE / "KEKKNYA FIKS CSV.csv"          # hasil web scraper
LAPORAN = BASE / "laporan_cleaning.txt"      # angka untuk laporan
KOLOM_MENTAH = ["web_scraper_order", "web_scraper_start_url", "pagination",
                "data", "data3", "data4", "image"]

# 1 kategori unik = 1 baris. id_kategori dibuat otomatis oleh database.
SQL_ISI_KATEGORI = """
INSERT INTO kategori (nama_kategori, grup_kategori)
SELECT DISTINCT kategori, kategori_grup
FROM stg_bersih
ORDER BY kategori
"""

# Kalender: semua tanggal dari berita pertama sampai terakhir (termasuk hari tanpa berita).
# ISODOW: 1 = Senin ... 7 = Minggu, jadi hari_ke = ISODOW - 1.
SQL_ISI_DIM_TANGGAL = """
INSERT INTO dim_tanggal (tanggal, tahun, kuartal, bulan, nama_bulan, hari_ke, nama_hari, is_weekend)
SELECT t::date,
       EXTRACT(YEAR    FROM t),
       EXTRACT(QUARTER FROM t),
       EXTRACT(MONTH   FROM t),
       (ARRAY['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus',
              'September','Oktober','November','Desember'])[EXTRACT(MONTH FROM t)::int],
       EXTRACT(ISODOW FROM t) - 1,
       (ARRAY['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'])[EXTRACT(ISODOW FROM t)::int],
       EXTRACT(ISODOW FROM t) >= 6
FROM generate_series((SELECT MIN(tanggal_publikasi)::date FROM stg_bersih),
                     (SELECT MAX(tanggal_publikasi)::date FROM stg_bersih),
                     INTERVAL '1 day') AS t
"""

# Tabel fakta: nama kategori diganti id_kategori (JOIN), kolom turunan dihitung di SQL.
SQL_ISI_BERITA = """
INSERT INTO berita (id_berita, judul, tanggal_publikasi, tanggal, jam,
                    id_kategori, panjang_judul, url_gambar)
SELECT s.id_berita, s.judul, s.tanggal_publikasi,
       s.tanggal_publikasi::date,
       EXTRACT(HOUR FROM s.tanggal_publikasi),
       k.id_kategori,
       CHAR_LENGTH(s.judul),
       s.url_gambar
FROM stg_bersih s
JOIN kategori k ON k.nama_kategori = s.kategori
ORDER BY s.id_berita
"""


# Angka untuk laporan cleaning, semuanya dihitung SQL
SQL_LAPORAN_STATUS = """
SELECT status, COUNT(*) AS jumlah
FROM v_cleaning
GROUP BY status
ORDER BY status
"""
SQL_LAPORAN_GRUP = """
SELECT grup_kategori, COUNT(*) AS jumlah
FROM v_berita
GROUP BY grup_kategori
ORDER BY jumlah DESC
"""
SQL_LAPORAN_BULAN = """
SELECT TO_CHAR(tanggal, 'YYYY-MM') AS bulan, COUNT(*) AS jumlah
FROM berita
GROUP BY 1
ORDER BY 1
"""


def tulis_laporan(conn):
    status = dict(conn.execute(text(SQL_LAPORAN_STATUS)).all())
    awal, akhir = conn.execute(text("SELECT MIN(tanggal_publikasi), MAX(tanggal_publikasi) FROM berita")).one()
    log = [f"Baris awal (stg_mentah)                : {sum(status.values())}"]
    for nama in ("dibuang: tanggal kosong", "dibuang: duplikat judul+waktu",
                 "dibuang: di luar rentang analisis"):
        log.append(f"{nama.capitalize():39s}: {status.get(nama, 0)}")
    log.append(f"Baris akhir (lolos, masuk tabel berita): {status.get('lolos', 0)}")
    log.append(f"Rentang data                           : {awal} s/d {akhir}")
    log.append("\nJumlah per grup kategori:")
    log += [f"{g:25s}{n:6d}" for g, n in conn.execute(text(SQL_LAPORAN_GRUP)).all()]
    log.append("\nJumlah per bulan:")
    log += [f"{b}{n:7d}" for b, n in conn.execute(text(SQL_LAPORAN_BULAN)).all()]
    LAPORAN.write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))


def jalankan_file_sql(conn, nama):
    """Menjalankan satu file .sql. Tanda persen digandakan supaya tidak dianggap parameter."""
    conn.exec_driver_sql((BASE / nama).read_text(encoding="utf-8").replace("%", "%%"))


def main():
    if not SRC.exists():
        sys.exit(f"File data mentah tidak ditemukan: {SRC.name}")
    engine = koneksi.buat_engine()
    if engine is None:
        sys.exit("File .env belum diisi. Salin .env.example menjadi .env lalu isi DB_PASSWORD.")

    # 1. Buat tabel dan view dari schema.sql
    with engine.begin() as conn:
        jalankan_file_sql(conn, "schema.sql")
    print("Tabel dan view dibuat dari schema.sql")

    # 2. File hasil scraping -> stg_mentah. Semua kolom dibaca sebagai teks, tidak diolah.
    mentah = pd.read_csv(SRC, dtype=str, encoding="utf-8-sig")[KOLOM_MENTAH]
    mentah.insert(0, "no_baris", range(1, len(mentah) + 1))
    mentah.to_sql("stg_mentah", engine, if_exists="append", index=False,
                  chunksize=1000, method="multi")
    print(f"Data mentah dimuat ke stg_mentah: {len(mentah)} baris")

    # 3. Cleaning dan pengisian tabel utama, seluruhnya dengan SQL (satu transaksi)
    with engine.begin() as conn:
        jalankan_file_sql(conn, "01_cleaning.sql")
        conn.execute(text(SQL_ISI_KATEGORI))
        conn.execute(text(SQL_ISI_DIM_TANGGAL))
        conn.execute(text(SQL_ISI_BERITA))
    print("Cleaning (01_cleaning.sql) dan pengisian tabel utama selesai\n")

    # 4. Laporan cleaning + verifikasi
    with engine.connect() as conn:
        tulis_laporan(conn)
        print()
        for t in ("stg_mentah", "stg_bersih", "kategori", "dim_tanggal", "berita"):
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:12s}: {n} baris")
    print("Selesai. Lanjutkan: python 04_text_mining.py")
    print("Cek di pgAdmin: kominfo_jatim > Schemas > public > Tables")


if __name__ == "__main__":
    main()
