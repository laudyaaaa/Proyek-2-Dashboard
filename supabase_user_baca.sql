-- ============================================================
-- supabase_user_baca.sql | User database khusus BACA untuk dashboard
--
-- Kenapa: dashboard hanya membaca data (SELECT). Kalau dashboard memakai
-- user ini, password yang tersimpan di Streamlit Cloud tidak bisa dipakai
-- untuk mengubah atau menghapus data, sekalipun bocor.
--
-- Cara pakai: jalankan SEKALI di Supabase -> SQL Editor, setelah
-- 02_load.py dan 04_text_mining.py selesai. Ganti dulu passwordnya.
-- Di Streamlit Cloud, isi DB_USER = "dashboard_baca.KODEPROYEK".
-- ============================================================

CREATE ROLE dashboard_baca LOGIN PASSWORD 'GANTI_DENGAN_PASSWORD_KUAT';

-- Boleh melihat isi schema public dan membaca semua tabel/view yang ada sekarang
GRANT USAGE ON SCHEMA public TO dashboard_baca;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_baca;

-- Tabel yang dibuat ulang nanti (02_load.py menghapus lalu membuat ulang tabel)
-- otomatis juga boleh dibaca, jadi file ini tidak perlu dijalankan lagi
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON TABLES TO dashboard_baca;

-- Batas waktu query supaya satu query macet tidak menahan database
ALTER ROLE dashboard_baca SET statement_timeout = '30s';

-- Cek: daftar tabel yang boleh dibaca dashboard_baca
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'dashboard_baca'
ORDER BY table_name;
