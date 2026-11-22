-- ============================================================
-- schema.sql  |  Database: kominfo_jatim (PostgreSQL)
-- Projek: Analisis publikasi berita Dinas Kominfo Jawa Timur
-- Aman dijalankan ulang: objek lama dihapus lalu dibuat lagi.
-- Dijalankan otomatis oleh 02_load.py.
-- ============================================================

DROP VIEW  IF EXISTS v_berita            CASCADE;
DROP VIEW  IF EXISTS v_cleaning          CASCADE;
DROP TABLE IF EXISTS klasifikasi_berita  CASCADE;
DROP TABLE IF EXISTS aturan_klasifikasi  CASCADE;
DROP TABLE IF EXISTS kata_frekuensi      CASCADE;
DROP TABLE IF EXISTS bigram_frekuensi    CASCADE;
DROP TABLE IF EXISTS kata_khas_kategori  CASCADE;
DROP TABLE IF EXISTS tren_kata_bulanan   CASCADE;
DROP TABLE IF EXISTS kata_berita         CASCADE;
DROP TABLE IF EXISTS stopword            CASCADE;
DROP TABLE IF EXISTS berita              CASCADE;
DROP TABLE IF EXISTS kategori            CASCADE;
DROP TABLE IF EXISTS dim_tanggal         CASCADE;
DROP TABLE IF EXISTS stg_berita          CASCADE;
DROP TABLE IF EXISTS stg_bersih          CASCADE;
DROP TABLE IF EXISTS stg_mentah          CASCADE;

-- ------------------------------------------------------------
-- A. TABEL STAGING (tempat singgah sebelum masuk tabel utama)
-- ------------------------------------------------------------

-- Data mentah hasil scraping, apa adanya: semua kolom bertipe teks,
-- nama kolom masih dari web scraper (data = judul, data3 = tanggal,
-- data4 = kategori, image = url gambar). no_baris = urutan baris di file.
CREATE TABLE stg_mentah (
    no_baris               INTEGER PRIMARY KEY,
    web_scraper_order      TEXT,
    web_scraper_start_url  TEXT,
    pagination             TEXT,
    data                   TEXT,
    data3                  TEXT,
    data4                  TEXT,
    image                  TEXT
);

-- Data setelah cleaning (diisi oleh 01_cleaning.sql)
CREATE TABLE stg_bersih (
    id_berita          INTEGER   PRIMARY KEY,
    judul              TEXT      NOT NULL,
    tanggal_publikasi  TIMESTAMP NOT NULL,
    kategori           TEXT      NOT NULL,
    kategori_grup      TEXT      NOT NULL,
    url_gambar         TEXT
);

-- ------------------------------------------------------------
-- B. TABEL UTAMA (star schema: 1 fakta + 2 dimensi)
-- ------------------------------------------------------------

-- Tabel kategori: 1 kategori memiliki banyak berita
CREATE TABLE kategori (
    id_kategori    SMALLINT    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nama_kategori  VARCHAR(60) NOT NULL UNIQUE,
    grup_kategori  VARCHAR(40) NOT NULL
);

-- Tabel dimensi tanggal: 1 tanggal memiliki banyak berita
CREATE TABLE dim_tanggal (
    tanggal     DATE        PRIMARY KEY,
    tahun       SMALLINT    NOT NULL,
    kuartal     SMALLINT    NOT NULL CHECK (kuartal BETWEEN 1 AND 4),
    bulan       SMALLINT    NOT NULL CHECK (bulan BETWEEN 1 AND 12),
    nama_bulan  VARCHAR(12) NOT NULL,
    hari_ke     SMALLINT    NOT NULL CHECK (hari_ke BETWEEN 0 AND 6),  -- 0 = Senin
    nama_hari   VARCHAR(10) NOT NULL,
    is_weekend  BOOLEAN     NOT NULL
);

-- Tabel fakta: satu baris = satu berita
CREATE TABLE berita (
    id_berita          INTEGER      PRIMARY KEY,
    judul              TEXT         NOT NULL,
    tanggal_publikasi  TIMESTAMP    NOT NULL,
    tanggal            DATE         NOT NULL REFERENCES dim_tanggal (tanggal),
    jam                SMALLINT     NOT NULL CHECK (jam BETWEEN 0 AND 23),
    id_kategori        SMALLINT     NOT NULL REFERENCES kategori (id_kategori),
    panjang_judul      SMALLINT     NOT NULL,
    url_gambar         TEXT
);

-- Index untuk mempercepat query analisis
CREATE INDEX idx_berita_tanggal   ON berita (tanggal);
CREATE INDEX idx_berita_kategori  ON berita (id_kategori);
CREATE INDEX idx_berita_waktu     ON berita (tanggal_publikasi);

-- ------------------------------------------------------------
-- C. TABEL ANALISIS TEKS (diisi oleh 04_text_mining.py)
-- ------------------------------------------------------------

-- Daftar kata umum yang dibuang saat analisis (yang, dan, di, ...)
CREATE TABLE stopword (
    kata  VARCHAR(40) PRIMARY KEY
);

-- Hasil tokenisasi: satu baris = satu kata dalam satu judul.
-- 1 berita memiliki banyak kata; posisi = urutan kata di judul (1, 2, 3, ...)
CREATE TABLE kata_berita (
    id_berita  INTEGER     NOT NULL REFERENCES berita (id_berita) ON DELETE CASCADE,
    posisi     SMALLINT    NOT NULL CHECK (posisi >= 1),
    kata       VARCHAR(60) NOT NULL,
    PRIMARY KEY (id_berita, posisi)
);
CREATE INDEX idx_kata_berita_kata ON kata_berita (kata);

-- Tabel ringkasan (hasil akhir analisis teks seluruh data)
CREATE TABLE kata_frekuensi (
    periode    VARCHAR(10) NOT NULL,          -- 'semua', '2025', '2026'
    kata       VARCHAR(60) NOT NULL,
    frekuensi  INTEGER     NOT NULL CHECK (frekuensi > 0),
    PRIMARY KEY (periode, kata)
);

CREATE TABLE bigram_frekuensi (
    bigram     VARCHAR(121) PRIMARY KEY,
    frekuensi  INTEGER      NOT NULL CHECK (frekuensi > 0)
);

CREATE TABLE kata_khas_kategori (
    grup_kategori  VARCHAR(40)  NOT NULL,
    kata           VARCHAR(60)  NOT NULL,
    skor           NUMERIC(6,4) NOT NULL,
    PRIMARY KEY (grup_kategori, kata)
);

CREATE TABLE tren_kata_bulanan (
    tahun   SMALLINT    NOT NULL,
    bulan   SMALLINT    NOT NULL CHECK (bulan BETWEEN 1 AND 12),
    kata    VARCHAR(60) NOT NULL,
    jumlah  INTEGER     NOT NULL CHECK (jumlah > 0),
    PRIMARY KEY (tahun, bulan, kata)
);

-- ------------------------------------------------------------
-- C2. KLASIFIKASI SUMBER & TOPIK BERITA (diisi oleh klasifikasi.sql,
--     yang dijalankan 04_text_mining.py)
-- Kategori asli dari situs tidak diubah. Ini pengelompokan tambahan
-- dari judul berita dengan aturan kata kunci.
-- ------------------------------------------------------------

-- Aturan kata kunci. Satu label boleh punya beberapa aturan.
-- Judul dicocokkan ke aturan berurutan (urutan kecil dulu);
-- aturan pertama yang cocok menentukan label berita itu.
CREATE TABLE aturan_klasifikasi (
    jenis   VARCHAR(10) NOT NULL CHECK (jenis IN ('sumber', 'topik')),
    urutan  SMALLINT    NOT NULL CHECK (urutan >= 1),
    label   VARCHAR(40) NOT NULL,
    pola    TEXT        NOT NULL,              -- regex PostgreSQL untuk judul huruf kecil
    PRIMARY KEY (jenis, urutan)
);

-- Hasil klasifikasi: 1 berita = 1 sumber + 1 topik
CREATE TABLE klasifikasi_berita (
    id_berita  INTEGER     PRIMARY KEY REFERENCES berita (id_berita) ON DELETE CASCADE,
    sumber     VARCHAR(40) NOT NULL,
    topik      VARCHAR(40) NOT NULL
);
CREATE INDEX idx_klasifikasi_sumber ON klasifikasi_berita (sumber);
CREATE INDEX idx_klasifikasi_topik  ON klasifikasi_berita (topik);

-- ------------------------------------------------------------
-- D. VIEW gabungan: dipakai dashboard (app.py) dan 03_analisis.sql
-- ------------------------------------------------------------
CREATE VIEW v_berita AS
SELECT b.id_berita, b.judul, b.tanggal_publikasi, b.tanggal, b.jam,
       d.tahun, d.kuartal, d.bulan, d.nama_bulan, d.hari_ke, d.nama_hari, d.is_weekend,
       k.nama_kategori, k.grup_kategori, b.panjang_judul,
       kb.sumber, kb.topik                -- NULL sampai 04_text_mining.py dijalankan
FROM berita b
JOIN dim_tanggal d USING (tanggal)
JOIN kategori   k USING (id_kategori)
LEFT JOIN klasifikasi_berita kb USING (id_berita);
