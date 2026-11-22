"""Daftar stopword bahasa Indonesia untuk analisis teks judul berita.

Daftar ini dimuat ke tabel `stopword` di PostgreSQL oleh 04_text_mining.py.
Tokenisasi, frekuensi kata, bigram, dan TF-IDF dikerjakan dengan SQL (lihat kueri.py).

Metode: case folding -> ambil huruf saja -> buang stopword (daftar Sastrawi +
daftar tambahan) -> token. Tanpa stemming, supaya kata tetap terbaca utuh di grafik.
"""

_STOP_CADANGAN = {
    "yang", "dan", "dari", "untuk", "dengan", "pada", "dalam", "ini", "itu", "atau",
    "juga", "akan", "adalah", "oleh", "sebagai", "agar", "karena", "saat", "serta",
    "para", "bagi", "hingga", "antara", "atas", "telah", "sudah", "masih", "lebih",
    "tidak", "bisa", "dapat", "kami", "kita", "mereka", "ada", "secara", "setelah",
    "sebelum", "pun", "namun", "tetap", "ke", "di", "se", "ya", "nya",
}
# Kata yang muncul di hampir semua judul sehingga tidak informatif
STOP_TAMBAHAN = {"jatim", "jawa", "timur", "kembali", "usai", "kini", "ayo", "yuk", "tak", "jadi", "jelang"}

try:  # daftar stopword bahasa Indonesia dari Sastrawi
    from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
    STOPWORDS = set(StopWordRemoverFactory().get_stop_words()) | _STOP_CADANGAN | STOP_TAMBAHAN
except Exception:  # Sastrawi belum terpasang -> pakai daftar cadangan
    STOPWORDS = _STOP_CADANGAN | STOP_TAMBAHAN
