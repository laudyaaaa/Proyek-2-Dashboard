"""Tahap 4 - Analisis teks judul berita, dikerjakan di PostgreSQL.
Jalankan: python 04_text_mining.py   (setelah 02_load.py)

Urutan:
  1. daftar stopword (teks.py)        -> tabel stopword
  2. tokenisasi judul dengan SQL       -> tabel kata_berita (dipakai dashboard)
     klasifikasi.sql                   -> tabel aturan_klasifikasi, klasifikasi_berita
                                          (sumber dan topik tiap berita)
  3. ringkasan dengan SQL              -> tabel kata_frekuensi, bigram_frekuensi,
                                          kata_khas_kategori, tren_kata_bulanan
  4. ekspor                            -> folder hasil/ (CSV tiap tabel + word cloud PNG)
Python hanya mengirim perintah SQL dan menyimpan hasilnya; semua hitungan ada di kueri.py.
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

import koneksi
import kueri
import teks

BASE = Path(__file__).parent
HASIL = BASE / "hasil"
HASIL.mkdir(exist_ok=True)

URUTAN = {
    "kata_frekuensi": "periode, frekuensi DESC, kata",
    "bigram_frekuensi": "frekuensi DESC, bigram",
    "kata_khas_kategori": "grup_kategori, skor DESC, kata",
    "tren_kata_bulanan": "kata, tahun, bulan",
}


def wordcloud(frek, nama):
    from wordcloud import WordCloud
    wc = WordCloud(width=1200, height=600, background_color="white", colormap="Blues",
                   max_words=100, prefer_horizontal=0.9)
    wc.generate_from_frequencies(dict(zip(frek["kata"], frek["frekuensi"])))
    wc.to_file(str(HASIL / f"wordcloud_{nama}.png"))


def main():
    engine = koneksi.buat_engine()
    if engine is None:
        sys.exit("File .env belum diisi. Salin .env.example menjadi .env lalu isi DB_PASSWORD.")

    with engine.begin() as conn:  # satu transaksi: kalau ada yang gagal, semua dibatalkan
        if conn.execute(text("SELECT COUNT(*) FROM berita")).scalar() == 0:
            sys.exit("Tabel berita masih kosong. Jalankan dulu: python 02_load.py")

        # Kosongkan hasil lama supaya aman dijalankan ulang
        conn.execute(text("TRUNCATE stopword, kata_berita, kata_frekuensi, bigram_frekuensi, "
                          "kata_khas_kategori, tren_kata_bulanan, aturan_klasifikasi, klasifikasi_berita"))

        # 1. Stopword
        conn.execute(text("INSERT INTO stopword (kata) VALUES (:kata)"),
                     [{"kata": k} for k in sorted(teks.STOPWORDS)])

        # 2. Tokenisasi, lalu klasifikasi sumber dan topik dari judul
        conn.execute(text(kueri.TOKENISASI))
        conn.exec_driver_sql((BASE / "klasifikasi.sql").read_text(encoding="utf-8").replace("%", "%%"))

        # 3. Tabel ringkasan (seluruh data = semua tanggal, semua grup)
        periode = conn.execute(text(kueri.PERIODE)).mappings().all()
        grup = conn.execute(text(kueri.SEMUA_GRUP)).scalar()
        semua = next({"awal": p["awal"], "akhir": p["akhir"], "grup": grup}
                     for p in periode if p["periode"] == "semua")
        for p in periode:
            conn.execute(text(kueri.ISI_KATA_FREKUENSI),
                         {"periode": p["periode"], "awal": p["awal"], "akhir": p["akhir"],
                          "grup": grup, "n": 50})
        conn.execute(text(kueri.ISI_BIGRAM_FREKUENSI), {**semua, "n": 50})
        conn.execute(text(kueri.ISI_KATA_KHAS), {**semua, "n": 10})
        conn.execute(text(kueri.ISI_TREN_KATA))

    # 4. Ekspor CSV dan word cloud (100 kata teratas tiap periode)
    with engine.connect() as conn:
        for nama, urut in URUTAN.items():
            t = pd.read_sql(text(f"SELECT * FROM {nama} ORDER BY {urut}"), conn)
            t.to_csv(HASIL / f"{nama}.csv", index=False, encoding="utf-8-sig")
            print(f"  {nama:20s}: {len(t)} baris")
        rs = pd.read_sql(text(kueri.RINGKASAN_KLASIFIKASI), conn)
        rs.to_csv(HASIL / "sumber_topik.csv", index=False, encoding="utf-8-sig")
        print(f"  {'sumber_topik':20s}: {len(rs)} baris (jumlah berita per sumber/topik, grup, tahun)")
        for p in periode:
            frek = pd.read_sql(text(kueri.KATA_TERBANYAK), conn,
                               params={"awal": p["awal"], "akhir": p["akhir"], "grup": grup, "n": 100})
            wordcloud(frek, p["periode"])
        n_stop = conn.execute(text("SELECT COUNT(*) FROM stopword")).scalar()
        n_kata = conn.execute(text(kueri.JUMLAH_TOKEN)).scalar()
        top = pd.read_sql(text("SELECT kata, frekuensi FROM kata_frekuensi WHERE periode = 'semua' "
                               "ORDER BY frekuensi DESC, kata LIMIT 10"), conn)
    print(f"  {'stopword':20s}: {n_stop} baris")
    print(f"  {'kata_berita':20s}: {n_kata} baris")
    print("Tabel ditulis ke PostgreSQL; CSV dan word cloud disimpan di folder 'hasil'.")
    print("\n10 kata teratas (seluruh data):")
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
