"""Semua query SQL yang dijalankan dashboard (app.py) dan 04_text_mining.py.

Seluruh pengolahan data (filter, agregasi, window function, tokenisasi, TF-IDF)
dikerjakan PostgreSQL. Python hanya mengirim parameter dan menggambar hasilnya.

Parameter (bind parameter, bukan sambung teks, jadi aman dari SQL injection):
  :awal, :akhir  rentang tanggal dari filter sidebar
  :grup          daftar grup kategori yang dipilih
  :n, :kata, :cari, :batas  sesuai kebutuhan tiap query
  :jenis         'sumber' atau 'topik' (klasifikasi dari klasifikasi.sql)
"""

# CTE filter: dipasang di depan setiap query dashboard.
FILTER = """
WITH f AS (
    SELECT *
    FROM v_berita
    WHERE tanggal BETWEEN :awal AND :akhir
      AND grup_kategori = ANY(:grup)
)"""

# ---------------------------------------------------------------- umum
RENTANG = "SELECT MIN(tanggal) AS tgl_min, MAX(tanggal) AS tgl_max FROM berita"

# Kartu angka di bagian atas (satu baris hasil)
KPI = FILTER + """,
bulan_puncak AS (
    SELECT LEFT(nama_bulan, 3) || ' ' || tahun AS label, COUNT(*) AS jumlah
    FROM f
    GROUP BY tahun, bulan, nama_bulan
    ORDER BY jumlah DESC, tahun, bulan
    LIMIT 1
)
SELECT COUNT(*)                                                    AS total,
       ROUND(COUNT(*)::numeric
             / (CAST(:akhir AS date) - CAST(:awal AS date) + 1), 1)  AS rata2_per_hari,
       MODE() WITHIN GROUP (ORDER BY jam)                          AS jam_puncak,
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_weekend)
             / NULLIF(COUNT(*), 0))                                AS persen_hari_kerja,
       ROUND(100.0 * COUNT(*) FILTER (WHERE grup_kategori = 'UMUM')
             / NULLIF(COUNT(*), 0))                                AS persen_umum,
       (SELECT label  FROM bulan_puncak)                           AS bulan_puncak,
       (SELECT jumlah FROM bulan_puncak)                           AS jumlah_bulan_puncak
FROM f
"""

# Total Jan-Okt per tahun + persen perubahan (perbandingan periode yang sama)
JAN_OKT = FILTER + """
SELECT COUNT(*) FILTER (WHERE tahun = 2025) AS t2025,
       COUNT(*) FILTER (WHERE tahun = 2026) AS t2026,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE tahun = 2026) - COUNT(*) FILTER (WHERE tahun = 2025))
             / NULLIF(COUNT(*) FILTER (WHERE tahun = 2025), 0), 1) AS perubahan_persen
FROM f
WHERE bulan <= 10
"""

# ---------------------------------------------------------------- tab Tren
TREN_BULANAN = FILTER + """,
bulanan AS (
    SELECT tahun, bulan, nama_bulan, COUNT(*) AS jumlah
    FROM f
    GROUP BY tahun, bulan, nama_bulan
)
SELECT tahun, bulan,
       LEFT(nama_bulan, 3) || ' ' || tahun AS label,
       jumlah,
       ROUND(AVG(jumlah) OVER (ORDER BY tahun, bulan
                               ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS rata3,
       jumlah - LAG(jumlah) OVER (ORDER BY tahun, bulan)                    AS selisih_bulan_lalu
FROM bulanan
ORDER BY tahun, bulan
"""

KOMPOSISI_BULANAN = FILTER + """
SELECT tahun, bulan,
       LEFT(nama_bulan, 3) || ' ' || tahun AS label,
       grup_kategori, COUNT(*) AS jumlah
FROM f
GROUP BY tahun, bulan, nama_bulan, grup_kategori
ORDER BY tahun, bulan, grup_kategori
"""

# ---------------------------------------------------------------- tab Kategori
PER_GRUP = FILTER + """
SELECT grup_kategori,
       COUNT(*) AS jumlah,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
FROM f
GROUP BY grup_kategori
ORDER BY jumlah DESC
"""

KATEGORI_TERBANYAK = FILTER + """
SELECT nama_kategori, COUNT(*) AS jumlah
FROM f
GROUP BY nama_kategori
ORDER BY jumlah DESC, nama_kategori
LIMIT :n
"""

# ---------------------------------------------------------------- klasifikasi sumber & topik
# Label dibuat oleh klasifikasi.sql (aturan kata kunci pada judul). Kolom sumber/topik
# di v_berita bernilai NULL sampai 04_text_mining.py dijalankan.
ADA_KLASIFIKASI = "SELECT COUNT(*) FROM klasifikasi_berita"

# Pilih kolom label sesuai :jenis
_LABEL = "CASE WHEN :jenis = 'sumber' THEN sumber ELSE topik END"

# Jumlah berita per label; 'Belum terkelompok' selalu di urutan terakhir
KLASIFIKASI = FILTER + f"""
SELECT label, jumlah, persen
FROM (
    SELECT {_LABEL} AS label,
           COUNT(*) AS jumlah,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS persen
    FROM f
    WHERE sumber IS NOT NULL
    GROUP BY 1
) x
ORDER BY label = 'Belum terkelompok', jumlah DESC, label
"""

# Aturan yang dipakai (ditampilkan di dashboard supaya cara pengelompokan terlihat)
ATURAN = """
SELECT jenis, urutan, label, pola
FROM aturan_klasifikasi
ORDER BY jenis, urutan
"""

# ---------------------------------------------------------------- tab Pola waktu
# LEFT JOIN dari daftar lengkap supaya hari/jam tanpa berita tetap muncul dengan angka 0.
PER_HARI = FILTER + """
SELECT h.hari_ke, h.nama_hari, COUNT(f.id_berita) AS jumlah
FROM (SELECT DISTINCT hari_ke, nama_hari FROM dim_tanggal) h
LEFT JOIN f USING (hari_ke)
GROUP BY h.hari_ke, h.nama_hari
ORDER BY h.hari_ke
"""

PER_JAM = FILTER + """
SELECT j.jam, COUNT(f.id_berita) AS jumlah
FROM generate_series(0, 23) AS j(jam)
LEFT JOIN f USING (jam)
GROUP BY j.jam
ORDER BY j.jam
"""

# 7 hari x 24 jam = 168 baris (untuk heatmap)
HARI_X_JAM = FILTER + """
SELECT h.hari_ke, h.nama_hari, j.jam, COUNT(f.id_berita) AS jumlah
FROM (SELECT DISTINCT hari_ke, nama_hari FROM dim_tanggal) h
CROSS JOIN generate_series(0, 23) AS j(jam)
LEFT JOIN f ON f.hari_ke = h.hari_ke AND f.jam = j.jam
GROUP BY h.hari_ke, h.nama_hari, j.jam
ORDER BY h.hari_ke, j.jam
"""

# ---------------------------------------------------------------- tab Kata kunci
JUMLAH_TOKEN = "SELECT COUNT(*) FROM kata_berita"

KATA_TERBANYAK = FILTER + """
SELECT kb.kata, COUNT(*) AS frekuensi
FROM kata_berita kb
JOIN f USING (id_berita)
GROUP BY kb.kata
ORDER BY frekuensi DESC, kb.kata
LIMIT :n
"""

# Bigram = dua kata bersebelahan dalam satu judul (self join: posisi dan posisi + 1)
BIGRAM_TERBANYAK = FILTER + """
SELECT a.kata || ' ' || b.kata AS bigram, COUNT(*) AS frekuensi
FROM kata_berita a
JOIN kata_berita b ON b.id_berita = a.id_berita AND b.posisi = a.posisi + 1
JOIN f ON f.id_berita = a.id_berita
GROUP BY a.kata, b.kata
ORDER BY frekuensi DESC, bigram
LIMIT :n
"""

# Jumlah judul per bulan yang memuat satu kata
TREN_KATA = FILTER + """
SELECT f.tahun, f.bulan,
       LEFT(f.nama_bulan, 3) || ' ' || f.tahun AS label,
       COUNT(DISTINCT f.id_berita) AS jumlah
FROM f
JOIN kata_berita kb USING (id_berita)
WHERE kb.kata = :kata
GROUP BY f.tahun, f.bulan, f.nama_bulan
ORDER BY f.tahun, f.bulan
"""

# Kata paling khas tiap grup kategori (TF-IDF, satu grup = satu dokumen).
#   tf    = 1 + ln(jumlah kata itu di grup)
#   idf   = ln((1 + jumlah grup) / (1 + jumlah grup yang memuat kata)) + 1
#   skor  = tf * idf, lalu dinormalkan per grup (dibagi panjang vektor / norma L2)
KATA_KHAS = FILTER + """,
tf AS (
    SELECT f.grup_kategori, kb.kata, COUNT(*) AS n
    FROM f
    JOIN kata_berita kb USING (id_berita)
    GROUP BY f.grup_kategori, kb.kata
),
dok AS (
    SELECT COUNT(DISTINCT grup_kategori) AS total FROM tf
),
df AS (
    SELECT kata, COUNT(*) AS n_grup FROM tf GROUP BY kata
),
bobot AS (
    SELECT tf.grup_kategori, tf.kata,
           (1 + LN(tf.n)) * (LN((1.0 + dok.total) / (1.0 + df.n_grup)) + 1) AS w
    FROM tf
    JOIN df USING (kata)
    CROSS JOIN dok
),
skor AS (
    SELECT grup_kategori, kata,
           w / SQRT(SUM(w * w) OVER (PARTITION BY grup_kategori)) AS skor
    FROM bobot
),
urut AS (
    SELECT grup_kategori, kata, skor,
           ROW_NUMBER() OVER (PARTITION BY grup_kategori ORDER BY skor DESC, kata) AS peringkat
    FROM skor
)
SELECT grup_kategori, kata, ROUND(CAST(skor AS numeric), 4) AS skor
FROM urut
WHERE peringkat <= :n
  AND (SELECT total FROM dok) >= 2
ORDER BY grup_kategori, peringkat
"""

# ---------------------------------------------------------------- tab 2025 vs 2026
BANDING_BULANAN = FILTER + """
SELECT m.bulan, m.nama_bulan,
       COUNT(*) FILTER (WHERE f.tahun = 2025) AS t2025,
       COUNT(*) FILTER (WHERE f.tahun = 2026) AS t2026,
       COUNT(*) FILTER (WHERE f.tahun = 2026) - COUNT(*) FILTER (WHERE f.tahun = 2025) AS selisih,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE f.tahun = 2026) - COUNT(*) FILTER (WHERE f.tahun = 2025))
             / NULLIF(COUNT(*) FILTER (WHERE f.tahun = 2025), 0), 1) AS perubahan_persen
FROM (SELECT DISTINCT bulan, nama_bulan FROM dim_tanggal WHERE bulan <= 10) m
LEFT JOIN f USING (bulan)
GROUP BY m.bulan, m.nama_bulan
ORDER BY m.bulan
"""

# Perubahan Jan-Okt per label sumber/topik.
# porsi_perubahan = bagian label ini dari total perubahan semua label (persen).
BANDING_KLASIFIKASI = FILTER + f""",
per_label AS (
    SELECT {_LABEL} AS label,
           COUNT(*) FILTER (WHERE tahun = 2025) AS t2025,
           COUNT(*) FILTER (WHERE tahun = 2026) AS t2026
    FROM f
    WHERE bulan <= 10 AND sumber IS NOT NULL
    GROUP BY 1
)
SELECT label, t2025, t2026,
       t2026 - t2025 AS selisih,
       ROUND(100.0 * (t2026 - t2025) / NULLIF(t2025, 0), 1) AS perubahan_persen,
       ROUND(100.0 * (t2026 - t2025) / NULLIF(SUM(t2026 - t2025) OVER (), 0), 1) AS porsi_perubahan
FROM per_label
ORDER BY selisih, label
"""

# Jumlah berita per kuartal per label. Hanya kuartal yang lengkap di dalam filter
# dan di dalam data (data berakhir 28 Okt 2026, jadi kuartal 4 2026 tidak ikut).
TREN_KLASIFIKASI = FILTER + f""",
kuartalan AS (
    SELECT tahun, kuartal, {_LABEL} AS label, COUNT(*) AS jumlah
    FROM f
    WHERE sumber IS NOT NULL
    GROUP BY tahun, kuartal, 3
)
SELECT tahun, kuartal, 'K' || kuartal || ' ' || tahun AS periode, label, jumlah
FROM kuartalan
WHERE MAKE_DATE(tahun, kuartal * 3 - 2, 1) >= CAST(:awal AS date)
  AND (MAKE_DATE(tahun, kuartal * 3, 1) + INTERVAL '1 month - 1 day')::date
      <= LEAST(CAST(:akhir AS date), (SELECT MAX(tanggal) FROM berita))
ORDER BY tahun, kuartal, label
"""

# ---------------------------------------------------------------- tab Data
# :cari kosong = semua berita. POSITION dipakai (bukan LIKE) supaya % dan _ dicari apa adanya.
_SYARAT_CARI = "(:cari = '' OR POSITION(LOWER(:cari) IN LOWER(judul)) > 0)"

DATA_JUMLAH = FILTER + f"""
SELECT COUNT(*) FROM f WHERE {_SYARAT_CARI}
"""

# :batas = NULL berarti tanpa batas (dipakai tombol unduh)
DATA = FILTER + f"""
SELECT tanggal_publikasi, judul, nama_kategori AS kategori, grup_kategori AS kategori_grup,
       sumber, topik
FROM f
WHERE {_SYARAT_CARI}
ORDER BY tanggal_publikasi DESC, id_berita DESC
LIMIT :batas
"""

# ================================================================ text mining (04_text_mining.py)
# Tokenisasi judul di SQL:
#   1. huruf kecil, tanda petik dibuang
#   2. regexp_matches mengambil setiap rangkaian huruf a-z sebagai satu kata
#   3. kata < 3 huruf dan kata yang ada di tabel stopword dibuang
#   4. kata yang tersisa diberi nomor urut (posisi) per judul
TOKENISASI = """
INSERT INTO kata_berita (id_berita, posisi, kata)
SELECT id_berita,
       ROW_NUMBER() OVER (PARTITION BY id_berita ORDER BY urutan) AS posisi,
       kata
FROM (
    SELECT b.id_berita, t.urutan, t.cocok[1] AS kata
    FROM berita b
    CROSS JOIN LATERAL regexp_matches(
        LOWER(REPLACE(REPLACE(b.judul, '’', ''), '''', '')), '[a-z]+', 'g'
    ) WITH ORDINALITY AS t(cocok, urutan)
) x
WHERE CHAR_LENGTH(kata) >= 3
  AND NOT EXISTS (SELECT 1 FROM stopword s WHERE s.kata = x.kata)
"""

# Rentang tanggal tiap periode: 'semua' + satu baris per tahun
PERIODE = """
SELECT 'semua' AS periode, MIN(tanggal) AS awal, MAX(tanggal) AS akhir FROM berita
UNION ALL
SELECT tahun::text, MIN(tanggal), MAX(tanggal) FROM v_berita GROUP BY tahun
ORDER BY periode
"""

SEMUA_GRUP = "SELECT ARRAY_AGG(DISTINCT grup_kategori) FROM kategori"

ISI_KATA_FREKUENSI = f"""
INSERT INTO kata_frekuensi (periode, kata, frekuensi)
SELECT :periode, kata, frekuensi FROM ({KATA_TERBANYAK}) q
"""

ISI_BIGRAM_FREKUENSI = f"""
INSERT INTO bigram_frekuensi (bigram, frekuensi)
SELECT bigram, frekuensi FROM ({BIGRAM_TERBANYAK}) q
"""

ISI_KATA_KHAS = f"""
INSERT INTO kata_khas_kategori (grup_kategori, kata, skor)
SELECT grup_kategori, kata, skor FROM ({KATA_KHAS}) q
"""

# Ringkasan klasifikasi untuk folder hasil/: jumlah berita per sumber/topik, grup, tahun
RINGKASAN_KLASIFIKASI = """
SELECT 'sumber' AS jenis, sumber AS label, grup_kategori, tahun, COUNT(*) AS jumlah
FROM v_berita GROUP BY sumber, grup_kategori, tahun
UNION ALL
SELECT 'topik', topik, grup_kategori, tahun, COUNT(*)
FROM v_berita GROUP BY topik, grup_kategori, tahun
ORDER BY jenis, label, grup_kategori, tahun
"""

# Tren bulanan untuk 10 kata terbanyak
ISI_TREN_KATA = """
INSERT INTO tren_kata_bulanan (tahun, bulan, kata, jumlah)
SELECT v.tahun, v.bulan, kb.kata, COUNT(DISTINCT v.id_berita)
FROM kata_berita kb
JOIN v_berita v USING (id_berita)
WHERE kb.kata IN (SELECT kata FROM kata_frekuensi
                  WHERE periode = 'semua'
                  ORDER BY frekuensi DESC, kata
                  LIMIT 10)
GROUP BY v.tahun, v.bulan, kb.kata
"""
