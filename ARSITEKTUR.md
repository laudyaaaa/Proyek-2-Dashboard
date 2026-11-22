# Arsitektur Sistem: Dashboard Publikasi Berita Dinas Kominfo Jawa Timur

Dokumen ini menjelaskan cara kerja sistem dari data mentah sampai dashboard, fungsi setiap file, dan output yang dihasilkan setiap tahap.

## 1. Gambaran umum

Sistem ini menganalisis publikasi berita di situs kominfo.jatimprov.go.id/berita. Data diambil dengan web scraper, dibersihkan dan disimpan di PostgreSQL, lalu ditampilkan sebagai dashboard interaktif Streamlit.

Yang dianalisis adalah **judul, waktu terbit, dan kategori** berita. Isi berita tidak termasuk.

| Hal | Nilai |
|---|---|
| Sumber data | `KEKKNYA FIKS CSV.csv` (hasil scraping, 11.008 baris) |
| Data setelah cleaning | 9.108 berita |
| Rentang analisis | 1 Januari 2025 sampai 28 Oktober 2026 |
| Database | PostgreSQL, nama database `kominfo_jatim` |
| Dashboard | Streamlit + Plotly |

### Prinsip rancangan

**Semua pengolahan data dikerjakan oleh PostgreSQL**: cleaning, pemecahan ke tabel, agregasi, window function, tokenisasi judul, bigram, TF-IDF, dan klasifikasi sumber serta topik berita.

Python hanya melakukan tiga hal:

1. mengantar file mentah ke tabel staging,
2. mengirim perintah SQL dan parameter filter,
3. menggambar grafik dari hasil query.

Akibatnya, dashboard tidak bisa berjalan tanpa PostgreSQL yang menyala, dan setiap angka di dashboard bisa ditelusuri ke satu query SQL di `kueri.py`.

## 2. Arsitektur

Sistem terdiri dari tiga lapisan.

```
┌──────────────────────────────────────────────────────────────────┐
│ LAPISAN 1: SUMBER DATA                                           │
│   KEKKNYA FIKS CSV.csv  (hasil web scraper, semua kolom teks)    │
└───────────────────────────────┬──────────────────────────────────┘
                                │ 02_load.py (pandas: baca, kirim apa adanya)
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ LAPISAN 2: DATABASE PostgreSQL (kominfo_jatim)                   │
│                                                                  │
│   Staging        stg_mentah ──(01_cleaning.sql)──> stg_bersih    │
│                                                        │         │
│   Tabel utama    kategori <── berita ──> dim_tanggal <─┘         │
│   (star schema)               │                                  │
│                               │ 04_text_mining.py + kueri.py     │
│   Analisis teks  stopword, kata_berita, kata_frekuensi,          │
│                  bigram_frekuensi, kata_khas_kategori,           │
│                  tren_kata_bulanan                               │
│   Klasifikasi    aturan_klasifikasi ──(klasifikasi.sql)──>       │
│                  klasifikasi_berita (sumber + topik per berita)  │
│                                                                  │
│   View           v_cleaning (status tiap baris mentah)           │
│                  v_berita   (berita + kategori + tanggal +       │
│                              sumber + topik)                     │
└───────────────────────────────┬──────────────────────────────────┘
                                │ query berparameter dari kueri.py
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ LAPISAN 3: PENYAJIAN                                             │
│   app.py        dashboard Streamlit (6 tab)                      │
│   hasil/        CSV ringkasan teks + word cloud PNG              │
│   pgAdmin       menjalankan 03_analisis.sql secara manual        │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Alur kerja langkah demi langkah

Urutan menjalankan:

```
python -m pip install -r requirements.txt
python 02_load.py
python 04_text_mining.py
streamlit run app.py
```

File `.env` harus sudah berisi password PostgreSQL sebelum langkah kedua.

### Tahap 1: Membuat struktur database

`02_load.py` menjalankan `schema.sql`. Semua tabel dan view lama dihapus lalu dibuat ulang, jadi tahap ini aman diulang kapan saja.

### Tahap 2: Memuat data mentah

`02_load.py` membaca CSV dengan pandas. Semua kolom dibaca sebagai teks dan tidak diolah sama sekali, lalu dimasukkan ke tabel `stg_mentah`. Satu kolom ditambahkan, yaitu `no_baris` (urutan baris di file).

Nama kolom masih mengikuti web scraper:

| Kolom mentah | Isi |
|---|---|
| `data` | judul berita |
| `data3` | tanggal dan jam, contoh `28-10-2026, 05:10` |
| `data4` | kategori |
| `image` | URL gambar |

### Tahap 3: Cleaning dengan SQL

`02_load.py` menjalankan `01_cleaning.sql`, yang bekerja dalam dua bagian.

**View `v_cleaning`** merapikan setiap baris mentah dan memberinya status. Tidak ada baris yang dihapus di sini, sehingga baris yang dibuang beserta alasannya tetap bisa diperiksa.

| Langkah | Yang dilakukan |
|---|---|
| 1 | Spasi dan enter berlebih pada judul dijadikan satu spasi |
| 2 | Teks tanggal diubah menjadi `TIMESTAMP`; pola yang salah atau kosong menjadi `NULL` |
| 3 | Duplikat ditandai: judul dan waktu yang sama persis dianggap salinan |
| 4 | Baris di luar rentang 1 Jan 2025 sampai 28 Okt 2026 ditandai |

**Tabel `stg_bersih`** diisi dengan baris berstatus `lolos`. Pada saat yang sama:

- `id_berita` dibuat, urut dari berita terlama,
- 26 kategori asli dikelompokkan menjadi 6 grup: UMUM, SETDA/PERANGKAT DAERAH, EVENT KHUSUS, GUBERNUR/WAKIL GUBERNUR, OLAHRAGA, dan LAINNYA.

Hasil cleaning pada data saat ini:

| Status | Jumlah baris |
|---|---|
| Baris awal | 11.008 |
| Dibuang: tanggal kosong | 13 |
| Dibuang: duplikat judul + waktu | 1 |
| Dibuang: di luar rentang analisis | 1.886 |
| **Lolos** | **9.108** |

### Tahap 4: Mengisi tabel utama

Masih di `02_load.py`, tiga perintah SQL memecah `stg_bersih` menjadi star schema:

| Tabel | Cara pengisian |
|---|---|
| `kategori` | Satu baris per kategori unik; `id_kategori` dibuat otomatis oleh database |
| `dim_tanggal` | Kalender lengkap dari berita pertama sampai terakhir (`generate_series`), termasuk hari tanpa berita |
| `berita` | Nama kategori diganti `id_kategori` lewat JOIN; kolom turunan `tanggal`, `jam`, dan `panjang_judul` dihitung |

Tahap 3 dan 4 berjalan dalam satu transaksi. Kalau salah satu gagal, semuanya dibatalkan.

Terakhir, `02_load.py` menulis `laporan_cleaning.txt`.

### Tahap 5: Analisis teks

`04_text_mining.py` mengirim query dari `kueri.py` dalam satu transaksi:

1. **Stopword.** Daftar kata umum dari `teks.py` dimuat ke tabel `stopword`.
2. **Tokenisasi.** Setiap judul dipecah menjadi kata: huruf dikecilkan, tanda petik dibuang, hanya rangkaian huruf a-z yang diambil, lalu kata di bawah 3 huruf dan stopword dibuang. Hasilnya masuk ke `kata_berita`, satu baris per kata, lengkap dengan posisinya di judul. Tidak ada stemming, supaya kata tetap terbaca utuh di grafik.
3. **Klasifikasi sumber dan topik.** `klasifikasi.sql` dijalankan: aturan kata kunci dimuat ke `aturan_klasifikasi`, lalu setiap berita diberi satu label sumber dan satu label topik di `klasifikasi_berita` (lihat bagian 4).
4. **Ringkasan.** Empat tabel ringkasan diisi (lihat bagian 4).
5. **Ekspor.** Keempat tabel ringkasan dan ringkasan klasifikasi disimpan sebagai CSV, dan word cloud dibuat untuk tiap periode.

### Tahap 6: Dashboard

`app.py` membaca filter dari sidebar (periode dan grup kategori), mengirimnya sebagai parameter `:awal`, `:akhir`, dan `:grup` ke query di `kueri.py`, lalu menggambar hasilnya.

Setiap query dashboard diawali CTE `FILTER` yang sama, sehingga semua grafik selalu mengikuti filter yang sedang aktif. Hasil query disimpan di cache selama 10 menit.

## 4. Struktur database

### Tabel staging

| Tabel | Isi | Diisi oleh |
|---|---|---|
| `stg_mentah` | Data scraping apa adanya, semua kolom teks | `02_load.py` |
| `stg_bersih` | Data setelah cleaning | `01_cleaning.sql` |

### Tabel utama (star schema)

```
   kategori                  berita                    dim_tanggal
┌──────────────┐      ┌───────────────────┐      ┌────────────────┐
│ id_kategori  │◄─────│ id_kategori       │      │ tanggal        │
│ nama_kategori│      │ tanggal           │─────►│ tahun, kuartal │
│ grup_kategori│      │ id_berita         │      │ bulan          │
└──────────────┘      │ judul             │      │ nama_bulan     │
                      │ tanggal_publikasi │      │ hari_ke        │
                      │ jam               │      │ nama_hari      │
                      │ panjang_judul     │      │ is_weekend     │
                      │ url_gambar        │      └────────────────┘
                      └───────────────────┘
```

- `berita` adalah tabel fakta: satu baris sama dengan satu berita.
- `kategori` dan `dim_tanggal` adalah tabel dimensi. Satu kategori atau satu tanggal memiliki banyak berita.
- `hari_ke` bernilai 0 untuk Senin sampai 6 untuk Minggu.
- Tiga index dipasang di `berita` (tanggal, kategori, waktu publikasi) untuk mempercepat query.

### Tabel analisis teks

| Tabel | Isi |
|---|---|
| `stopword` | Kata umum yang dibuang saat analisis |
| `kata_berita` | Hasil tokenisasi: satu baris per kata per judul, dengan `posisi` |
| `kata_frekuensi` | 50 kata terbanyak per periode (`semua`, `2025`, `2026`) |
| `bigram_frekuensi` | 50 pasangan kata bersebelahan terbanyak |
| `kata_khas_kategori` | 10 kata paling khas tiap grup kategori, dengan skor TF-IDF |
| `tren_kata_bulanan` | Jumlah judul per bulan untuk 10 kata terbanyak |

### Tabel klasifikasi sumber dan topik

| Tabel | Isi |
|---|---|
| `aturan_klasifikasi` | Aturan kata kunci: `jenis` (sumber/topik), `urutan`, `label`, `pola` (regex). Satu label boleh punya beberapa aturan |
| `klasifikasi_berita` | Satu baris per berita: `id_berita`, `sumber`, `topik` |

### View

| View | Fungsi |
|---|---|
| `v_cleaning` | Setiap baris mentah beserta statusnya (`lolos` atau alasan dibuang) |
| `v_berita` | Gabungan `berita`, `kategori`, `dim_tanggal`, dan `klasifikasi_berita` (LEFT JOIN, jadi `sumber` dan `topik` bernilai NULL sebelum `04_text_mining.py` dijalankan). Dipakai oleh dashboard dan `03_analisis.sql` |

### Metode analisis teks

**Bigram** dihitung dengan self join pada `kata_berita`: kata di `posisi` digabung dengan kata di `posisi + 1` dalam judul yang sama.

**TF-IDF** memperlakukan satu grup kategori sebagai satu dokumen:

```
tf   = 1 + ln(jumlah kemunculan kata di grup)
idf  = ln((1 + jumlah grup) / (1 + jumlah grup yang memuat kata)) + 1
skor = tf × idf, lalu dinormalkan per grup (norma L2)
```

Kata dengan skor tinggi adalah kata yang sering muncul di satu grup tetapi jarang di grup lain.

**Klasifikasi sumber dan topik** menjawab masalah kategori situs: 78% berita masuk UMUM karena situs tidak punya kategori wilayah atau topik. Kategori asli tidak diubah; setiap berita diberi dua label tambahan dari judulnya:

- **sumber**: siapa yang diberitakan. Labelnya DPRD, Gubernur/Pemprov Jatim, Diskominfo Jatim, Pemkab/Pemkot, TNI/Polri/penegak hukum, Kampus/sekolah, BUMN/bank/swasta, Pemerintah pusat, Ormas/komunitas.
- **topik**: berita itu tentang apa. Labelnya Ekonomi/UMKM, Pangan & pertanian, Kesehatan, Pendidikan & SDM, Infrastruktur & transportasi, Digital & informasi, Sosial, Budaya/wisata/keagamaan, Olahraga, Bencana & lingkungan, Hukum/keamanan/politik, Penghargaan, Pemerintahan & kelembagaan.

Caranya dengan aturan kata kunci (bukan machine learning):

```
1. judul diubah menjadi huruf kecil
2. judul dicocokkan ke aturan berurutan (LATERAL JOIN ... ORDER BY urutan LIMIT 1)
3. aturan pertama yang cocok menentukan label
4. tidak cocok dengan aturan mana pun -> 'Belum terkelompok'
```

Pola memakai `\y` (batas kata) supaya potongan kata tidak ikut tertangkap, misalnya "ikan" tidak cocok dengan "pastikan". Nama kabupaten/kota dicek paling akhir karena nama kota juga muncul pada berita aktor lain ("KAI Daop 8 Surabaya"). Pada data saat ini sekitar 15% berita belum terkelompok untuk sumber dan 13% untuk topik.

## 5. Fungsi setiap file

### File utama

| File | Jenis | Fungsi | Output |
|---|---|---|---|
| `KEKKNYA FIKS CSV.csv` | Data | Data mentah hasil web scraper | Menjadi input `02_load.py` |
| `schema.sql` | SQL | Mendefinisikan semua tabel, index, dan view `v_berita`. Menghapus objek lama lebih dulu | Struktur database kosong |
| `01_cleaning.sql` | SQL | Membuat view `v_cleaning` dan mengisi `stg_bersih` | Tabel `stg_bersih` (9.108 baris) dan ringkasan jumlah per status |
| `02_load.py` | Python | Menjalankan `schema.sql`, memuat CSV ke `stg_mentah`, menjalankan `01_cleaning.sql`, mengisi tabel utama | Tabel staging dan tabel utama terisi; `laporan_cleaning.txt` |
| `03_analisis.sql` | SQL | 25 query analisis untuk dijalankan manual di pgAdmin, satu per satu (query 20–25 untuk klasifikasi sumber dan topik) | Tabel hasil di pgAdmin (bahan laporan) |
| `klasifikasi.sql` | SQL | Aturan kata kunci sumber dan topik, lalu pengisian `klasifikasi_berita`. Aturan diubah di file ini | Tabel `aturan_klasifikasi` dan `klasifikasi_berita` (9.108 baris) |
| `04_text_mining.py` | Python | Memuat stopword, menjalankan tokenisasi, `klasifikasi.sql`, dan ringkasan teks, mengekspor hasil | 8 tabel analisis teks dan klasifikasi terisi; isi folder `hasil/` |
| `kueri.py` | Python | Kumpulan semua query SQL berparameter yang dipakai dashboard dan text mining | Tidak ada output langsung; diimpor oleh `app.py` dan `04_text_mining.py` |
| `teks.py` | Python | Daftar stopword bahasa Indonesia: daftar Sastrawi, ditambah daftar cadangan dan kata khusus seperti "jatim", "jawa", "timur" | Variabel `STOPWORDS`, dimuat ke tabel `stopword` |
| `koneksi.py` | Python | Membaca pengaturan dari `.env` (laptop) atau Secrets (Streamlit Cloud), lalu membuat koneksi ke PostgreSQL, terenkripsi kalau `DB_SSLMODE` diisi. Mengembalikan `None` kalau password belum diisi | Engine SQLAlchemy |
| `app.py` | Python | Dashboard Streamlit: filter, kartu angka, grafik, tabel, tombol unduh | Halaman web (lokal atau Streamlit Cloud); unduhan `berita_terfilter.csv` |
| `supabase_user_baca.sql` | SQL | Membuat user database khusus baca untuk dashboard di Supabase. Dijalankan sekali di SQL Editor Supabase | Role `dashboard_baca` dengan hak `SELECT` saja |

### File konfigurasi

| File | Fungsi |
|---|---|
| `.env` | Menyimpan `DB_PASSWORD` dan, bila perlu, `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSLMODE`. Tidak boleh diunggah ke GitHub. Di Streamlit Cloud, isian yang sama ditulis di Secrets |
| `.env.example` | Contoh isi `.env`, untuk PostgreSQL lokal dan untuk Supabase |
| `.gitignore` | Mengecualikan `.env`, `secrets.toml`, cache Python, folder cadangan, dan dokumen pribadi dari Git |
| `requirements.txt` | Daftar pustaka Python dengan versi dikunci, supaya hasil di laptop dan di cloud sama |
| `.streamlit/config.toml` | Tema dashboard dan mematikan pengumpulan statistik pemakaian |
| `.vscode/settings.json` | Pengaturan editor VS Code |

### File output

| File | Dibuat oleh | Isi |
|---|---|---|
| `laporan_cleaning.txt` | `02_load.py` | Jumlah baris awal, dibuang, dan lolos; rentang data; jumlah per grup kategori dan per bulan |
| `hasil/kata_frekuensi.csv` | `04_text_mining.py` | 50 kata terbanyak tiap periode |
| `hasil/bigram_frekuensi.csv` | `04_text_mining.py` | 50 pasangan kata terbanyak |
| `hasil/kata_khas_kategori.csv` | `04_text_mining.py` | 10 kata paling khas tiap grup, dengan skor |
| `hasil/tren_kata_bulanan.csv` | `04_text_mining.py` | Tren bulanan 10 kata terbanyak |
| `hasil/sumber_topik.csv` | `04_text_mining.py` | Jumlah berita per label sumber/topik, grup kategori, dan tahun |
| `hasil/wordcloud_semua.png` | `04_text_mining.py` | Word cloud 100 kata teratas, seluruh data |
| `hasil/wordcloud_2025.png` | `04_text_mining.py` | Word cloud 100 kata teratas, tahun 2025 |
| `hasil/wordcloud_2026.png` | `04_text_mining.py` | Word cloud 100 kata teratas, tahun 2026 |

### File dan folder pendukung

| File atau folder | Keterangan |
|---|---|
| `README.md` | Petunjuk singkat menjalankan proyek |
| `DEPLOY.md` | Panduan deploy: database di Supabase, kode di GitHub, aplikasi di Streamlit Community Cloud |
| `cadangan_sebelum_sql/` | Versi lama, saat cleaning masih dikerjakan Python (`01_cleaning.py`). Tidak dipakai |
| `cadangan_sebelum_redesain/` | Versi lama `app.py` dan temanya sebelum tampilan diubah. Tidak dipakai |
| `cadangan_sebelum_klasifikasi/` | Versi file sebelum klasifikasi sumber dan topik ditambahkan. Tidak dipakai |
| `rps matkul terkait/` | RPS mata kuliah terkait (Proyek Basis Data, Data Story Telling, Deployment Aplikasi) |
| `Jalur_Pengerjaan_Projek.xlsx` | Catatan jalur pengerjaan proyek |
| `__pycache__/` | Cache Python, dibuat otomatis |

## 6. Ketergantungan antar file

```
02_load.py ──────► koneksi.py ──► .env
   ├─► schema.sql
   ├─► 01_cleaning.sql
   └─► KEKKNYA FIKS CSV.csv

04_text_mining.py ► koneksi.py
   ├─► kueri.py
   ├─► klasifikasi.sql
   └─► teks.py ──► Sastrawi (opsional)

app.py ──────────► koneksi.py
   └─► kueri.py

03_analisis.sql   (berdiri sendiri, dijalankan di pgAdmin)
```

`kueri.py` dipakai bersama oleh dashboard dan text mining. Query pengisi tabel ringkasan (`ISI_KATA_FREKUENSI`, `ISI_BIGRAM_FREKUENSI`, `ISI_KATA_KHAS`) membungkus query yang sama dengan yang dipakai dashboard, sehingga angka di folder `hasil/` dan di dashboard dihitung dengan rumus yang sama.

## 7. Isi dashboard

### Filter (sidebar)

| Filter | Pilihan |
|---|---|
| Periode | Semua, per tahun (2025, 2026), atau rentang tanggal kustom |
| Grup kategori | Satu atau lebih dari 6 grup |

### Tab

| Tab | Isi | Query di `kueri.py` |
|---|---|---|
| Ringkasan | Total berita, rata-rata per hari, bulan dan jam terpadat, tren bulanan dengan rata-rata bergerak 3 bulan, donat grup kategori, donat hari kerja vs akhir pekan, ritme harian, berita per hari, temuan utama (termasuk sumber penurunan terbesar dan isi UMUM terbanyak) | `KPI`, `TREN_BULANAN`, `PER_GRUP`, `PER_HARI`, `PER_JAM`, `JAN_OKT`, `BANDING_KLASIFIKASI`, `KLASIFIKASI` |
| Kategori | Komposisi grup per bulan (jumlah atau persentase), berita per grup, 12 kategori asli terbanyak, isi berita menurut sumber dan topik (hanya UMUM atau semua grup terpilih), tabel aturan kata kunci | `KOMPOSISI_BULANAN`, `PER_GRUP`, `KATEGORI_TERBANYAK`, `KLASIFIKASI`, `ATURAN` |
| Pola waktu | Heatmap hari × jam, berita per jam | `HARI_X_JAM`, `PER_JAM` |
| Kata kunci | Word cloud, 20 kata terbanyak, 15 bigram terbanyak, tren satu kata, kata khas tiap grup (TF-IDF) | `KATA_TERBANYAK`, `BIGRAM_TERBANYAK`, `TREN_KATA`, `KATA_KHAS` |
| 2025 vs 2026 | Perbandingan Januari sampai Oktober kedua tahun, per bulan dan total; berita apa yang berkurang menurut sumber atau topik; tren per kuartal per sumber/topik | `JAN_OKT`, `BANDING_BULANAN`, `BANDING_KLASIFIKASI`, `TREN_KLASIFIKASI` |
| Data | Daftar berita dengan kolom sumber dan topik, pencarian judul, unduh CSV | `DATA`, `DATA_JUMLAH` |

Perbandingan antar tahun dibatasi Januari sampai Oktober karena data 2026 berakhir pada 28 Oktober. Tren per kuartal hanya memuat kuartal yang lengkap, jadi kuartal 4 2026 tidak ikut.

## 8. Teknologi

| Komponen | Teknologi | Peran |
|---|---|---|
| Database | PostgreSQL | Penyimpanan dan seluruh pengolahan data |
| Koneksi | SQLAlchemy, psycopg2 | Penghubung Python ke PostgreSQL |
| Pemuatan data | pandas | Membaca CSV dan hasil query |
| Dashboard | Streamlit | Kerangka halaman, filter, tab |
| Grafik | Plotly | Grafik interaktif |
| Teks | Sastrawi, wordcloud | Daftar stopword dan gambar word cloud |
| Konfigurasi | python-dotenv | Membaca `.env` |
| Deploy: database | Supabase (PostgreSQL, session pooler) | Database di cloud yang dibaca dashboard |
| Deploy: aplikasi | Streamlit Community Cloud + GitHub | Menjalankan `app.py` dan memberi link publik |

## 9. Hal yang perlu diketahui

- **Query memakai bind parameter**, bukan penyambungan teks, sehingga input pengguna (kata pencarian, kata tren) aman dari SQL injection.
- **Menjalankan ulang `02_load.py` menghapus tabel analisis teks dan klasifikasi**, karena `schema.sql` membuat ulang semua tabel. Setelah itu `04_text_mining.py` harus dijalankan lagi; sebelum itu, tab Kata kunci dan bagian sumber/topik menampilkan pesan bahwa tabel masih kosong.
- **Klasifikasi sumber dan topik adalah perkiraan dari judul.** Satu berita hanya mendapat label dari aturan pertama yang cocok, dan sebagian berita bisa salah kelompok. Angkanya cocok untuk melihat pola besar, bukan hitungan pasti. Aturan diubah di `klasifikasi.sql`; untuk mencoba aturan baru cukup jalankan file itu di pgAdmin, tanpa mengulang `02_load.py`.
- **Dashboard menunjukkan di mana penurunan 2026 terjadi, bukan penyebabnya.** Penurunan terbesar berasal dari berita Pemkab/Pemkot dan kampus, sedangkan berita Pemprov dan DPRD relatif stabil. Penyebabnya perlu dikonfirmasi ke pengelola situs.
- **Rentang analisis dan pengelompokan kategori diatur di `01_cleaning.sql`.** Daftar grup di `app.py` (variabel `GRUP`) ditulis manual, jadi kalau nama grup diubah di SQL, daftar itu harus ikut diubah.
- **Grup `TANPA KATEGORI` tidak ada di filter dashboard.** Pada data saat ini tidak ada berita tanpa kategori, jadi tidak berpengaruh. Kalau data baru memuat berita semacam itu, berita tersebut tidak akan tampil di dashboard.
- **Deploy memakai Supabase dan Streamlit Community Cloud (lihat `DEPLOY.md`).** Koneksi ke Supabase harus lewat *session pooler*, karena alamat direct connection hanya IPv6 dan tidak terjangkau dari Streamlit Cloud. Dashboard sebaiknya memakai user `dashboard_baca` yang hanya bisa membaca. Project Supabase gratis dijeda kalau sepi aktivitas selama seminggu, dan aplikasi Streamlit tidur kalau tidak dibuka selama 12 jam, jadi buka keduanya sebelum presentasi.
