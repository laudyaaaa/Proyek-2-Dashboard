# Deploy dashboard: Supabase + Streamlit Community Cloud

Tujuan: dashboard bisa dibuka siapa saja lewat link, misalnya
`https://dashboard-kominfo-jatim.streamlit.app`, tanpa laptop harus menyala.

```
Laptop                         Supabase (PostgreSQL di cloud)      Streamlit Community Cloud
02_load.py, 04_text_mining.py  ───── mengisi data ─────►  database  ◄──── dibaca ──── app.py ──► link publik
(dijalankan sekali)                                                     (kode dari GitHub)
```

Semua layanan di bawah gratis. Kode tidak perlu diubah lagi: cukup isi pengaturan koneksi.

Perkiraan waktu: 30–60 menit.

---

## Bagian A. Database di Supabase

### A1. Buat project

1. Buka **supabase.com**, daftar (boleh pakai akun GitHub).
2. Klik **New project**, lalu isi:
   - **Name**: `kominfo-jatim`
   - **Database password**: buat password kuat, lalu **simpan** (misalnya di Notepad). Ini bukan password akun Supabase, dan nanti dipakai di `.env`.
   - **Region**: **Southeast Asia (Singapore)**, yang paling dekat dari Indonesia.
3. Kalau ada pilihan **Enable Data API**, **matikan**. Dashboard ini terhubung langsung ke PostgreSQL dan tidak memakai Data API. Mematikannya mencegah tabel diakses lewat API publik Supabase.
   - Kalau pilihan itu tidak muncul, matikan setelah project jadi: **Project Settings → Data API**.
4. Klik **Create new project**, lalu tunggu sekitar 2 menit.

### A2. Ambil data koneksi

1. Di halaman project, klik tombol **Connect** di bagian atas.
2. Pilih **Session pooler**.
   - **Jangan** pilih *Direct connection*. Alamatnya (`db.xxxx.supabase.co`) hanya bisa diakses lewat IPv6, sedangkan Streamlit Cloud tidak bisa menjangkaunya.
3. Salin teksnya. Bentuknya seperti ini:

   ```
   postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```

4. Pecah menjadi 5 isian:

   | Isian | Ambil dari | Contoh |
   |---|---|---|
   | `DB_USER` | setelah `postgresql://`, sebelum `:` | `postgres.abcdefghijklmnop` |
   | `DB_PASSWORD` | password database dari langkah A1 | `...` |
   | `DB_HOST` | setelah `@`, sebelum `:5432` | `aws-1-ap-southeast-1.pooler.supabase.com` |
   | `DB_PORT` | angka setelah host | `5432` |
   | `DB_NAME` | bagian paling akhir | `postgres` |

   Bagian setelah `postgres.` (contoh: `abcdefghijklmnop`) adalah **kode proyek**. Kode ini dipakai lagi di langkah C3.

### A3. Isi data dari laptop

1. Buka file `.env` di folder proyek, lalu **ganti isinya** dengan data Supabase. Simpan dulu isi lamanya di tempat lain kalau masih ingin memakai PostgreSQL di laptop.

   ```
   DB_HOST=aws-1-ap-southeast-1.pooler.supabase.com
   DB_PORT=5432
   DB_NAME=postgres
   DB_USER=postgres.abcdefghijklmnop
   DB_PASSWORD=password_database_supabase
   DB_SSLMODE=require
   ```

   `DB_SSLMODE=require` membuat koneksi terenkripsi.

2. Jalankan di terminal, sama seperti biasa:

   ```
   python 02_load.py
   python 04_text_mining.py
   ```

   Kalau berhasil, muncul `berita : 9108 baris`. Data sekarang ada di Supabase.

3. Cek di Supabase: menu **Table Editor**. Tabel `berita`, `kategori`, dan seterusnya sudah terisi.

### A4. Buat user khusus baca (disarankan)

Dashboard hanya membaca data. Dengan user khusus baca, password yang disimpan di Streamlit Cloud tidak bisa dipakai untuk mengubah atau menghapus data, sekalipun bocor.

1. Supabase: menu **SQL Editor → New query**.
2. Salin seluruh isi `supabase_user_baca.sql` ke editor.
3. Ganti `GANTI_DENGAN_PASSWORD_KUAT` dengan password baru, lalu simpan password ini.
4. Klik **Run**. Di bagian bawah muncul daftar tabel dengan hak `SELECT`.

Cukup dijalankan **sekali**. Kalau nanti `02_load.py` dijalankan ulang, hak baca tetap berlaku otomatis.

---

## Bagian B. Upload kode ke GitHub

Streamlit Cloud mengambil kode dari GitHub.

### Cara paling mudah: lewat VS Code

1. Buka folder proyek di VS Code.
2. Klik ikon **Source Control** di sisi kiri (ikon cabang).
   - Kalau diminta menginstal Git, instal dulu, lalu buka ulang VS Code.
3. Klik **Publish to GitHub**, login GitHub, lalu pilih **Publish to GitHub public repository**.
   - VS Code otomatis mengikuti `.gitignore`, jadi `.env` (berisi password) **tidak ikut terunggah**.
4. Buka repository-nya di github.com dan pastikan:
   - ✅ ada `app.py`, `requirements.txt`, dan folder `.streamlit` (isinya `config.toml`)
   - ❌ **tidak ada** file `.env`. Kalau ternyata ada, hapus repository-nya, lalu ganti password database di Supabase (**Project Settings → Database → Reset database password**).

### Alternatif: upload lewat website GitHub

Bisa juga lewat github.com → **New repository** → **uploading an existing file**, lalu seret file-filenya. **Hati-hati:** cara ini **tidak** mengikuti `.gitignore`, jadi jangan ikut menyeret `.env`, folder `cadangan_*`, atau dokumen pribadi.

---

## Bagian C. Deploy di Streamlit Community Cloud

1. Buka **share.streamlit.io** dan login dengan akun GitHub yang sama.
2. Klik **Create app → Deploy a public app from GitHub**, lalu isi:
   - **Repository**: repository yang tadi dibuat
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: misalnya `dashboard-kominfo-jatim`
3. Klik **Advanced settings**:
   - **Python version**: `3.12`
   - **Secrets**: tempel teks berikut, lalu ganti isinya:

   ```toml
   DB_HOST = "aws-1-ap-southeast-1.pooler.supabase.com"
   DB_PORT = "5432"
   DB_NAME = "postgres"
   DB_USER = "dashboard_baca.abcdefghijklmnop"
   DB_PASSWORD = "password_user_dashboard_baca"
   DB_SSLMODE = "require"
   ```

   - `DB_USER` = `dashboard_baca.` + kode proyek dari langkah A2.
   - Kalau langkah A4 dilewati, pakai `postgres.kodeproyek` dan password database dari A1.

4. Klik **Deploy**. Instalasi pertama butuh beberapa menit.
5. Selesai. Dashboard terbuka di link `https://....streamlit.app`.

Secrets disimpan terpisah dari kode, jadi password tidak pernah masuk ke GitHub.

---

## Bagian D. Kalau ada masalah

| Pesan atau gejala | Penyebab | Solusi |
|---|---|---|
| `Tenant or user not found` | `DB_USER` tidak memakai `.kodeproyek`, atau host salah | Salin ulang dari tombol **Connect → Session pooler** |
| `password authentication failed` | Password salah. Yang benar adalah password database, bukan password akun | Supabase: **Project Settings → Database → Reset database password** |
| `Network is unreachable` atau timeout | Memakai host `db.xxxx.supabase.co` (Direct connection) | Ganti dengan host **Session pooler** (`...pooler.supabase.com`) |
| `permission denied for table ...` | User baca belum diberi hak | Jalankan ulang `supabase_user_baca.sql` di SQL Editor, tanpa baris `CREATE ROLE` |
| Dashboard: "Pengaturan database belum diisi" | Secrets kosong atau nama isiannya salah ketik | Cek **App settings → Secrets**. Nama harus persis `DB_HOST`, `DB_USER`, dst. |
| `ModuleNotFoundError` | `requirements.txt` tidak ada di folder paling atas repository | Pastikan `requirements.txt` sejajar dengan `app.py` |
| Halaman "Zzzz… This app has gone to sleep" | Aplikasi tidak dibuka selama 12 jam | Klik tombol untuk membangunkan, lalu tunggu sekitar 1 menit |
| Dashboard error karena database tidak bisa dibaca setelah lama tidak dipakai | Project Supabase gratis **dijeda** kalau sepi aktivitas selama 7 hari | Buka dashboard Supabase, lalu klik **Restore project** |

**Sebelum presentasi:** buka dashboard Supabase dan link Streamlit sekitar 10 menit sebelumnya, supaya keduanya sudah menyala.

---

## Bagian E. Memperbarui setelah deploy

- **Kode berubah** (misalnya `app.py`): commit dan push ke GitHub (VS Code: Source Control → Commit → Sync). Streamlit Cloud otomatis memperbarui aplikasi.
- **Data berubah** (misalnya CSV scraping baru): jalankan `02_load.py` dan `04_text_mining.py` dengan `.env` yang mengarah ke Supabase. Dashboard menyimpan hasil query selama 10 menit, jadi tunggu sebentar atau klik **Reboot app** di Streamlit Cloud.
