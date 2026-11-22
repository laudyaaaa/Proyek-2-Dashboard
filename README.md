# Dashboard Publikasi Berita Dinas Kominfo Jawa Timur

Data: hasil scraping kominfo.jatimprov.go.id/berita (Jan 2025 - 28 Okt 2026, 9.108 berita).

## Urutan menjalankan
1. `python -m pip install -r requirements.txt`
2. Salin `.env.example` menjadi `.env`, isi password PostgreSQL
3. `python 02_load.py`       -> data mentah masuk PostgreSQL, cleaning (01_cleaning.sql), tabel utama terisi
4. `python 04_text_mining.py` -> tabel analisis teks dan klasifikasi sumber/topik (klasifikasi.sql) di PostgreSQL + folder `hasil/`
5. Jalankan query di `03_analisis.sql` lewat pgAdmin
6. `streamlit run app.py`    -> dashboard (membaca dari PostgreSQL)

## Alur data
`KEKKNYA FIKS CSV.csv` -> `stg_mentah` -> (01_cleaning.sql) -> `stg_bersih` -> `kategori`,
`dim_tanggal`, `berita` -> `kata_berita`, `klasifikasi_berita` (sumber dan topik) dan tabel ringkasan teks -> dashboard.

Seluruh pengolahan data dikerjakan PostgreSQL: cleaning, pemecahan ke tabel, agregasi,
window function, tokenisasi judul, bigram, TF-IDF, dan klasifikasi sumber/topik berita. Python hanya mengantar file mentah
ke tabel staging, mengirim parameter filter, dan menggambar grafik. Dashboard butuh
PostgreSQL menyala.

## Berkas
| Berkas | Fungsi |
|---|---|
| schema.sql | Skema database: staging, 3 tabel utama, tabel analisis teks, view v_berita |
| 01_cleaning.sql | Cleaning dengan SQL: view v_cleaning (status tiap baris) dan pengisian stg_bersih |
| 02_load.py | Memuat file mentah ke stg_mentah, menjalankan schema.sql dan 01_cleaning.sql, mengisi tabel utama, menulis laporan_cleaning.txt |
| 03_analisis.sql | 25 query analisis untuk dijalankan di pgAdmin |
| klasifikasi.sql | Aturan kata kunci untuk memberi label sumber dan topik pada setiap berita (dijalankan 04_text_mining.py) |
| kueri.py | Semua query SQL berparameter yang dipakai dashboard dan text mining |
| teks.py | Daftar stopword (dimuat ke tabel stopword) |
| 04_text_mining.py | Menjalankan tokenisasi dan ringkasan teks di SQL, ekspor ke `hasil/` |
| koneksi.py | Koneksi PostgreSQL dari .env (laptop) atau Secrets (Streamlit Cloud) |
| supabase_user_baca.sql | User database khusus baca untuk dashboard di Supabase |
| DEPLOY.md | Panduan deploy ke Supabase + Streamlit Community Cloud |
| app.py | Dashboard Streamlit (tampilan saja; angka dari SQL) |

`01_cleaning.py` dan `berita_bersih.csv` adalah sisa versi lama dan tidak dipakai lagi.

Jangan upload `.env` ke GitHub (sudah ada di `.gitignore`).

## Deploy
Database di Supabase, dashboard di Streamlit Community Cloud. Langkah lengkapnya ada di `DEPLOY.md`.
