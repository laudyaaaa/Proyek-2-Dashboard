-- ============================================================
-- 03_analisis.sql | Query analisis berita Kominfo Jatim
-- Jalankan satu per satu di pgAdmin: blok teks dengan mouse,
-- lalu tekan F5 (hanya teks yang diblok yang dijalankan).
-- ============================================================

-- 0. View gabungan v_berita -----------------------------------
-- View ini dibuat di schema.sql (dijalankan 02_load.py) dan dipakai
-- oleh semua query di bawah serta oleh dashboard (kueri.py).
-- Untuk melihat isinya:
SELECT * FROM v_berita LIMIT 10;

-- 1. Ringkasan umum ---------------------------------------------
SELECT COUNT(*)                       AS total_berita,
       MIN(tanggal)                   AS tanggal_awal,
       MAX(tanggal)                   AS tanggal_akhir,
       COUNT(DISTINCT tanggal)        AS hari_ada_berita,
       ROUND(COUNT(*)::numeric / COUNT(DISTINCT tanggal), 1) AS rata2_berita_per_hari_aktif
FROM berita;

-- 2. Jumlah berita per bulan ------------------------------------
SELECT tahun, bulan, nama_bulan, COUNT(*) AS jumlah_berita
FROM v_berita
GROUP BY tahun, bulan, nama_bulan
ORDER BY tahun, bulan;

-- 3. Tren per bulan + rata-rata bergerak 3 bulan ----------------
WITH bulanan AS (
    SELECT tahun, bulan, COUNT(*) AS jumlah
    FROM v_berita GROUP BY tahun, bulan
)
SELECT tahun, bulan, jumlah,
       ROUND(AVG(jumlah) OVER (ORDER BY tahun, bulan ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS rata2_bergerak_3bln,
       jumlah - LAG(jumlah) OVER (ORDER BY tahun, bulan) AS selisih_bulan_lalu
FROM bulanan
ORDER BY tahun, bulan;

-- 4. Per grup kategori + persentase ------------------------------
SELECT grup_kategori,
       COUNT(*) AS jumlah,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
FROM v_berita
GROUP BY grup_kategori
ORDER BY jumlah DESC;

-- 5. Per kategori asli (26 kategori) ------------------------------
SELECT nama_kategori, grup_kategori, COUNT(*) AS jumlah
FROM v_berita
GROUP BY nama_kategori, grup_kategori
ORDER BY jumlah DESC;

-- 6. Per hari dalam seminggu ---------------------------------------
SELECT hari_ke, nama_hari, COUNT(*) AS jumlah,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
FROM v_berita
GROUP BY hari_ke, nama_hari
ORDER BY hari_ke;

-- 7. Per jam publikasi -----------------------------------------------
SELECT jam, COUNT(*) AS jumlah
FROM v_berita
GROUP BY jam
ORDER BY jam;

-- 8. Perbandingan Jan-Okt 2025 vs Jan-Okt 2026 (per bulan) ---------------
SELECT bulan, nama_bulan,
       COUNT(*) FILTER (WHERE tahun = 2025) AS tahun_2025,
       COUNT(*) FILTER (WHERE tahun = 2026) AS tahun_2026,
       COUNT(*) FILTER (WHERE tahun = 2026) - COUNT(*) FILTER (WHERE tahun = 2025) AS selisih,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE tahun = 2026) - COUNT(*) FILTER (WHERE tahun = 2025))
             / NULLIF(COUNT(*) FILTER (WHERE tahun = 2025), 0), 1) AS perubahan_persen
FROM v_berita
WHERE bulan <= 10
GROUP BY bulan, nama_bulan
ORDER BY bulan;

-- 9. Total Jan-Okt per tahun (perbandingan adil) --------------------------
SELECT tahun, COUNT(*) AS total_jan_okt
FROM v_berita
WHERE bulan <= 10
GROUP BY tahun
ORDER BY tahun;

-- 10. Komposisi grup kategori per tahun (Jan-Okt) ---------------------------
SELECT grup_kategori,
       COUNT(*) FILTER (WHERE tahun = 2025) AS tahun_2025,
       COUNT(*) FILTER (WHERE tahun = 2026) AS tahun_2026
FROM v_berita
WHERE bulan <= 10
GROUP BY grup_kategori
ORDER BY tahun_2025 DESC;

-- 11. 10 hari paling ramai ----------------------------------------------------
SELECT tanggal, nama_hari, COUNT(*) AS jumlah
FROM v_berita
GROUP BY tanggal, nama_hari
ORDER BY jumlah DESC
LIMIT 10;

-- 12. Lonjakan event khusus per bulan -------------------------------------------
SELECT tahun, bulan, nama_kategori, COUNT(*) AS jumlah
FROM v_berita
WHERE grup_kategori = 'EVENT KHUSUS'
GROUP BY tahun, bulan, nama_kategori
ORDER BY tahun, bulan, jumlah DESC;

-- 13. Berita weekend vs weekday ----------------------------------------------------
SELECT CASE WHEN is_weekend THEN 'Akhir pekan' ELSE 'Hari kerja' END AS jenis_hari,
       COUNT(*) AS jumlah,
       COUNT(DISTINCT tanggal) AS jumlah_hari,
       ROUND(COUNT(*)::numeric / COUNT(DISTINCT tanggal), 1) AS rata2_per_hari
FROM v_berita
GROUP BY is_weekend;

-- 14. Rata-rata panjang judul per tahun ----------------------------------------------
SELECT tahun, ROUND(AVG(panjang_judul), 1) AS rata2_panjang_judul
FROM v_berita
GROUP BY tahun
ORDER BY tahun;

-- ============================================================
-- ANALISIS TEKS (jalankan setelah python 04_text_mining.py)
-- ============================================================

-- 15. Hasil tokenisasi satu judul (kata_berita JOIN berita) -------------------------
SELECT b.judul, kb.posisi, kb.kata
FROM kata_berita kb
JOIN berita b USING (id_berita)
WHERE b.id_berita = 1
ORDER BY kb.posisi;

-- 16. 20 kata terbanyak di judul -----------------------------------------------------
SELECT kata, COUNT(*) AS frekuensi
FROM kata_berita
GROUP BY kata
ORDER BY frekuensi DESC, kata
LIMIT 20;

-- 17. 15 pasangan kata (bigram) terbanyak: self join posisi dan posisi + 1 ---------
SELECT a.kata || ' ' || b.kata AS bigram, COUNT(*) AS frekuensi
FROM kata_berita a
JOIN kata_berita b ON b.id_berita = a.id_berita AND b.posisi = a.posisi + 1
GROUP BY a.kata, b.kata
ORDER BY frekuensi DESC, bigram
LIMIT 15;

-- 18. Jumlah judul per bulan yang memuat kata 'surabaya' ----------------------------
SELECT v.tahun, v.bulan, v.nama_bulan, COUNT(DISTINCT v.id_berita) AS jumlah_judul
FROM v_berita v
JOIN kata_berita kb USING (id_berita)
WHERE kb.kata = 'surabaya'
GROUP BY v.tahun, v.bulan, v.nama_bulan
ORDER BY v.tahun, v.bulan;

-- 19. Kata paling khas tiap grup kategori (hasil TF-IDF, rumusnya di kueri.py) ------
SELECT grup_kategori, kata, skor
FROM kata_khas_kategori
ORDER BY grup_kategori, skor DESC;

-- ============================================================
-- KLASIFIKASI SUMBER & TOPIK (jalankan setelah python 04_text_mining.py)
-- Label dibuat oleh klasifikasi.sql dari judul berita dengan aturan kata kunci.
-- Kategori asli dari situs tidak diubah.
-- ============================================================

-- 20. Aturan kata kunci yang dipakai (urutan kecil dicek lebih dulu) --------------
SELECT jenis, urutan, label, pola
FROM aturan_klasifikasi
ORDER BY jenis, urutan;

-- 21. Isi kategori UMUM menurut sumber (siapa yang diberitakan) -----------------------
SELECT sumber, COUNT(*) AS jumlah,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
FROM v_berita
WHERE grup_kategori = 'UMUM'
GROUP BY sumber
ORDER BY jumlah DESC;

-- 22. Isi kategori UMUM menurut topik ---------------------------------------------------
SELECT topik, COUNT(*) AS jumlah,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
FROM v_berita
WHERE grup_kategori = 'UMUM'
GROUP BY topik
ORDER BY jumlah DESC;

-- 23. Berita apa yang berkurang? Jan-Okt 2025 vs 2026 per sumber ------------------------
--     porsi_dari_total_perubahan = bagian sumber ini dari seluruh penurunan
WITH per_sumber AS (
    SELECT sumber,
           COUNT(*) FILTER (WHERE tahun = 2025) AS tahun_2025,
           COUNT(*) FILTER (WHERE tahun = 2026) AS tahun_2026
    FROM v_berita
    WHERE bulan <= 10
    GROUP BY sumber
)
SELECT sumber, tahun_2025, tahun_2026,
       tahun_2026 - tahun_2025 AS selisih,
       ROUND(100.0 * (tahun_2026 - tahun_2025) / NULLIF(tahun_2025, 0), 1) AS perubahan_persen,
       ROUND(100.0 * (tahun_2026 - tahun_2025) / SUM(tahun_2026 - tahun_2025) OVER (), 1)
           AS porsi_dari_total_perubahan
FROM per_sumber
ORDER BY selisih;

-- 24. Sumber x topik pada kategori UMUM: siapa memberitakan apa ---------------------------
SELECT sumber, topik, COUNT(*) AS jumlah
FROM v_berita
WHERE grup_kategori = 'UMUM'
GROUP BY sumber, topik
ORDER BY jumlah DESC
LIMIT 20;

-- 25. Contoh judul yang belum terkelompok (bahan untuk memperbaiki aturan) ----------------
SELECT judul, grup_kategori
FROM v_berita
WHERE sumber = 'Belum terkelompok'
ORDER BY RANDOM()
LIMIT 20;
