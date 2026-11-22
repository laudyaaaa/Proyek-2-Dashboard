-- ============================================================
-- 01_cleaning.sql | Cleaning data berita di PostgreSQL
-- Input : tabel stg_mentah (isi file hasil scraping, apa adanya)
-- Output: tabel stg_bersih (data bersih, siap dipecah ke tabel utama)
-- Dijalankan otomatis oleh 02_load.py. Boleh juga dijalankan
-- ulang di pgAdmin (blok semua, F5).
-- ============================================================

-- A. View v_cleaning: setiap baris mentah dirapikan dan diberi status
--    ('lolos' atau alasan dibuang). Tidak ada baris yang dihapus di sini,
--    jadi bisa dicek baris mana yang dibuang dan kenapa.
CREATE OR REPLACE VIEW v_cleaning AS
WITH rapi AS (
    SELECT no_baris,
           -- 1. Rapikan teks: spasi/enter berlebih jadi satu spasi, buang spasi di ujung
           TRIM(REGEXP_REPLACE(data, '[\s\u00A0]+', ' ', 'g'))   AS judul,
           -- 2. Teks tanggal (contoh: 28-10-2026, 05:10) -> TIMESTAMP.
           --    Kalau kosong atau polanya salah, hasilnya NULL.
           CASE WHEN data3 ~ '^\d{1,2}-\d{1,2}-\d{4}, \d{1,2}:\d{2}$'
                THEN TO_TIMESTAMP(data3, 'DD-MM-YYYY, HH24:MI')::timestamp
           END                                                   AS tanggal_publikasi,
           TRIM(data4)                                           AS kategori,
           image                                                 AS url_gambar
    FROM stg_mentah
),
bernomor AS (
    -- 3. Tandai duplikat: judul dan waktu sama persis -> salinan ke-2, ke-3, ...
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY judul, tanggal_publikasi
                              ORDER BY no_baris) AS salinan_ke
    FROM rapi
)
SELECT no_baris, judul, tanggal_publikasi, kategori, url_gambar,
       CASE WHEN tanggal_publikasi IS NULL THEN 'dibuang: tanggal kosong'
            WHEN salinan_ke > 1            THEN 'dibuang: duplikat judul+waktu'
            -- 4. Rentang analisis (ubah di sini kalau berubah pikiran)
            WHEN tanggal_publikasi NOT BETWEEN TIMESTAMP '2025-01-01 00:00'
                                           AND TIMESTAMP '2026-10-28 23:59'
                                           THEN 'dibuang: di luar rentang analisis'
            ELSE 'lolos'
       END AS status
FROM bernomor;

-- B. Baris yang lolos disalin ke stg_bersih, ditambah grup kategori dan id_berita
TRUNCATE stg_bersih;

INSERT INTO stg_bersih (id_berita, judul, tanggal_publikasi, kategori, kategori_grup, url_gambar)
SELECT ROW_NUMBER() OVER (ORDER BY tanggal_publikasi, no_baris DESC) AS id_berita,  -- urut dari berita terlama
       judul,
       tanggal_publikasi,
       COALESCE(kategori, 'TANPA KATEGORI'),
       -- 5. Pengelompokan 26 kategori asli menjadi 6 grup (boleh disesuaikan)
       CASE WHEN kategori IS NULL                    THEN 'TANPA KATEGORI'
            WHEN UPPER(kategori) = 'UMUM'            THEN 'UMUM'
            WHEN UPPER(kategori) LIKE 'SETDA%'       THEN 'SETDA/PERANGKAT DAERAH'
            WHEN UPPER(kategori) = 'OLAHRAGA'        THEN 'OLAHRAGA'
            WHEN UPPER(kategori) IN ('GUBERNUR', 'GUBERNURAN', 'WAKIL GUBERNUR')
                                                     THEN 'GUBERNUR/WAKIL GUBERNUR'
            WHEN UPPER(kategori) ~ 'PORPROV|MTQ|STQH|PORNAS|FORDA|FORNAS|DIGIFEST|HAJI|SEMERU|PILKADA'
                                                     THEN 'EVENT KHUSUS'
            ELSE 'LAINNYA'
       END,
       url_gambar
FROM v_cleaning
WHERE status = 'lolos';

-- C. Cek hasil: berapa baris lolos dan berapa dibuang (angka untuk laporan)
SELECT status, COUNT(*) AS jumlah
FROM v_cleaning
GROUP BY status
ORDER BY jumlah DESC;

-- Contoh melihat baris yang dibuang karena duplikat atau tanggal kosong:
-- SELECT * FROM v_cleaning WHERE status IN ('dibuang: duplikat judul+waktu', 'dibuang: tanggal kosong');
