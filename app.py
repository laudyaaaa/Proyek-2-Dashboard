"""Tahap 5 - Dashboard analisis publikasi berita Dinas Kominfo Jawa Timur.
Jalankan: streamlit run app.py   (setelah 02_load.py dan 04_text_mining.py)

Sumber data: PostgreSQL (database kominfo_jatim). Semua angka di dashboard adalah
hasil query SQL di kueri.py; file ini hanya mengirim filter sebagai parameter dan
menggambar hasilnya.
"""
from contextlib import contextmanager
from datetime import date
from html import escape
from urllib.parse import quote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

import koneksi
import kueri

GRUP = ["UMUM", "SETDA/PERANGKAT DAERAH", "EVENT KHUSUS", "GUBERNUR/WAKIL GUBERNUR",
        "OLAHRAGA", "LAINNYA"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

# Tema terang: sidebar & header biru navy, kartu putih, aksen merah. Warna seri sudah
# divalidasi terhadap kartu putih (tetap terbedakan untuk buta warna); biru muda, kuning
# tua, dan abu-abu kontrasnya < 3:1, jadi grafik yang memakainya selalu diberi label/legenda.
# Urutan slot tetap; warna mengikuti entitas, bukan peringkat.
T = dict(teks="#12233d", teks2="#5b6779", grid="#e3e8ef",
         kartu="#ffffff", garis="#dde3eb", tint="rgba(200,16,46,.08)",
         bayangan="0 1px 2px rgba(16,24,40,.06), 0 4px 14px rgba(16,24,40,.05)",
         seri=["#24599e", "#c8102e", "#5b9bd5", "#d99a1c", "#7a5cc9", "#8c96a3"],
         urut=["#d6e4f3", "#a9c6e6", "#6fa3d6", "#3b7bc0", "#1f5596", "#12335f"])

st.set_page_config(page_title="Dashboard Berita Kominfo Jatim", page_icon="📰", layout="wide")


WARNA_GRUP = dict(zip(GRUP, T["seri"]))
UTAMA, KEDUA = T["seri"][0], T["seri"][1]
TINGGI_HARI = 592                        # diatur agar kolom kanan sejajar kolom kiri
REDUP = "#b7cbe4"                        # biru pucat: batang yang bukan puncak
BELUM = "Belum terkelompok"              # label klasifikasi untuk judul yang tidak cocok aturan


# ------------------------------------------------------------------ gaya halaman (CSS)
st.html(f"""<style>
:root {{
  --kartu: {T['kartu']}; --garis: {T['garis']}; --tint: {T['tint']};
  --teks: {T['teks']}; --teks2: {T['teks2']}; --aksen: {KEDUA}; --bayangan: {T['bayangan']};
}}
</style>""")
st.html("""<style>
.block-container { padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1400px; }
[data-testid="stHeader"] { background: transparent; }
.stApp { background: #eef1f6; }

/* ---------- header */
.kepala { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 14px 24px; background: linear-gradient(100deg, #0f2747 0%, #17386a 100%); color: #fff;
  border-radius: 14px; padding: 20px 24px; border-bottom: 4px solid #c8102e;
  box-shadow: 0 8px 24px rgba(15,39,71,.18); }
.hero-label { font-size: 12px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
  color: #ff9aa6; }
.kepala h1 { margin: 6px 0 6px; padding: 0; font-size: clamp(24px, 3vw, 34px); line-height: 1.15;
  font-weight: 800; letter-spacing: -.02em; color: #fff; }
.kepala p { margin: 0; max-width: 720px; font-size: 14.5px; line-height: 1.55; color: rgba(255,255,255,.86); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; border-radius: 999px;
  font-size: 12.5px; font-weight: 600; color: #fff; background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.24); }
.ik { display: inline-block; width: 18px; height: 18px; flex: none; background: currentColor;
  -webkit-mask: center / contain no-repeat; mask: center / contain no-repeat; }
.chip .ik { width: 14px; height: 14px; }

/* ---------- kartu angka */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(215px, 1fr)); gap: 14px; }
.kpi { background: var(--kartu); border: 1px solid var(--garis); border-radius: 14px;
  padding: 16px 18px 14px; box-shadow: var(--bayangan); display: flex; flex-direction: column; gap: 4px;
  min-width: 0; }
.kpi-atas { display: flex; align-items: center; gap: 10px; }
.kpi-ikon { width: 34px; height: 34px; flex: none; border-radius: 10px; background: var(--tint);
  color: var(--aksen); display: grid; place-items: center; }
.kpi-label { font-size: 13px; font-weight: 600; color: var(--teks2); }
.kpi-baris { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.kpi { position: relative; overflow: hidden; }
.kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: #c8102e; }
.kpi-nilai { font-size: 30px; font-weight: 800; line-height: 1.15; letter-spacing: -.02em;
  color: var(--teks); font-variant-numeric: tabular-nums; margin-top: 6px; white-space: nowrap; }
.kpi-ket { font-size: 12.5px; color: var(--teks2); }

/* ---------- ubin angka (baris atas ringkasan) */
.ubin-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 16px; }
@media (max-width: 1150px) { .ubin-grid { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); } }
.ubin { position: relative; overflow: hidden; border-radius: 16px; padding: 20px 22px; color: #fff;
  min-height: 150px; display: flex; flex-direction: column; justify-content: space-between; }
.ubin::after { content: ""; position: absolute; width: 170px; height: 170px; right: -50px; bottom: -70px;
  border-radius: 50%; background: rgba(255,255,255,.12); pointer-events: none; }
.ubin-a { background: linear-gradient(135deg, #0f2747 0%, #24599e 100%);
  box-shadow: 0 10px 26px rgba(15,39,71,.25); }
.ubin-b { background: linear-gradient(135deg, #9e0b23 0%, #d81e3a 100%);
  box-shadow: 0 10px 26px rgba(200,16,46,.22); }
.ubin-label { font-size: 14px; font-weight: 600; color: rgba(255,255,255,.92); }
.ubin-nilai { font-size: 42px; font-weight: 800; line-height: 1.1; letter-spacing: -.02em;
  font-variant-numeric: tabular-nums; }
.ubin-nilai small { font-size: 15px; font-weight: 600; letter-spacing: 0; color: rgba(255,255,255,.9); }
.ubin-ket { font-size: 12.5px; color: rgba(255,255,255,.9); }
.ubin-tumpuk { display: flex; flex-direction: column; gap: 14px; }
.mini { flex: 1; display: flex; align-items: center; gap: 12px; background: var(--kartu);
  border: 1px solid var(--garis); border-radius: 14px; padding: 12px 14px; box-shadow: var(--bayangan);
  min-width: 0; }
.mini-teks small { display: block; white-space: nowrap; font-size: 12px; font-weight: 600; color: var(--teks2); }
.mini-teks b { font-size: 18px; font-weight: 800; color: var(--teks); font-variant-numeric: tabular-nums; }
.mini-chip { margin-left: auto; font-size: 11.5px; font-weight: 700; padding: 4px 9px; border-radius: 8px;
  background: var(--tint); color: var(--teks); white-space: nowrap; }

/* ---------- temuan */
.judul-bagian { display: flex; align-items: baseline; gap: 10px; margin: 10px 0 10px; }
.judul-bagian b { font-size: 16px; font-weight: 700; color: var(--teks); }
.judul-bagian span { font-size: 12.5px; color: var(--teks2); }
.temuan-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.temuan { display: flex; gap: 14px; background: var(--kartu); border: 1px solid var(--garis);
  border-radius: 14px; padding: 16px 18px; box-shadow: var(--bayangan); }
.temuan-no { font-size: 13px; font-weight: 800; color: var(--aksen); background: var(--tint);
  border-radius: 8px; width: 30px; height: 30px; flex: none; display: grid; place-items: center;
  font-variant-numeric: tabular-nums; }
.temuan-isi { font-size: 14px; line-height: 1.55; color: var(--teks2); }
.temuan-isi b { color: var(--teks); font-weight: 700; }

/* ---------- kartu grafik (st.container ber-key "kartu_...") */
[class*="st-key-kartu_"] { background: var(--kartu); border: 1px solid var(--garis) !important;
  border-radius: 14px !important; box-shadow: var(--bayangan); padding: 18px 20px 12px !important; }
.kj { font-size: 15.5px; font-weight: 700; color: var(--teks); line-height: 1.3; }
.kk { font-size: 12.5px; color: var(--teks2); margin-top: 3px; line-height: 1.45; }

/* ---------- label ringkas di atas grafik */
.label-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.label-info { background: var(--kartu); border: 1px solid var(--garis); border-radius: 12px;
  padding: 10px 16px; min-width: 150px; box-shadow: var(--bayangan); }
.label-info small { display: block; font-size: 12px; color: var(--teks2); font-weight: 600; }
.label-info b { font-size: 18px; font-weight: 800; color: var(--teks); font-variant-numeric: tabular-nums; }

/* ---------- tab sebagai pil */
.stTabs [role="tablist"] { gap: 4px; background: var(--kartu); border: 1px solid var(--garis);
  border-radius: 12px; padding: 5px; width: fit-content; max-width: 100%; box-shadow: var(--bayangan); }
.stTabs [role="tab"] { height: auto; padding: 7px 15px; border-radius: 8px; color: var(--teks2); }
.stTabs [role="tab"] p { font-size: 14px; font-weight: 600; }
.stTabs [role="tab"]:hover { background: #eaf0f8; color: var(--teks); }
.stTabs [role="tab"][aria-selected="true"] { background: #12335f; color: #fff;
  box-shadow: 0 4px 12px rgba(18,51,95,.28); }
.stTabs [role="tab"][aria-selected="true"] p { color: #fff; }
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ---------- sidebar & kaki */
[data-testid="stSidebar"] { border-right: none; }
[data-testid="stSidebar"] button[data-variant="segmented_control"][aria-checked="true"] {
  background: #c8102e !important; border-color: #c8102e !important; color: #fff !important; }
[data-testid="stSidebar"] button[data-variant="segmented_control"][aria-checked="true"] p { color: #fff !important; }
.merek { display: flex; align-items: center; gap: 12px; padding: 2px 0 14px;
  border-bottom: 1px solid rgba(255,255,255,.16); margin-bottom: 6px; }
.merek-logo { width: 40px; height: 40px; flex: none; border-radius: 11px; display: grid; place-items: center;
  color: #fff; font-weight: 800; font-size: 15px; letter-spacing: .02em;
  background: #c8102e; }
.merek b { display: block; font-size: 14.5px; color: #fff; line-height: 1.25; }
.merek span { font-size: 12px; color: rgba(255,255,255,.72); }
.info-data { font-size: 12.5px; line-height: 1.6; color: rgba(255,255,255,.78);
  background: rgba(255,255,255,.08); border-left: 3px solid #c8102e; border-radius: 8px; padding: 10px 12px; }
.info-data b { color: #fff; }
.kaki { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--garis);
  font-size: 12.5px; color: var(--teks2); display: flex; flex-wrap: wrap; gap: 6px 18px;
  justify-content: space-between; }
</style>""")

IKON = {
    "berita": '<path d="M4 5h13v14H6a2 2 0 0 1-2-2V5z"/><path d="M17 9h3v8a2 2 0 0 1-2 2"/>'
              '<path d="M8 9h5M8 13h5"/>',
    "kalender": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "grafik": '<path d="M4 19V5M4 19h16"/><path d="M8 15l4-5 3 3 4-6"/>',
    "jam": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "lapis": '<path d="M12 4l8 4-8 4-8-4 8-4z"/><path d="M4 12l8 4 8-4M4 16l8 4 8-4"/>',
    "data": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
}


def uri_svg(isi, kotak="0 0 24 24", atribut=""):
    """SVG sebagai data URI. Streamlit membuang tag <svg> dari st.html, jadi gambar
    kecil (ikon, sparkline) dipasang lewat CSS."""
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{kotak}' {atribut}>{isi}</svg>"
    return f'url("data:image/svg+xml,{quote(svg)}")'


_ATR_IKON = ("fill='none' stroke='black' stroke-width='1.9' stroke-linecap='round' "
             "stroke-linejoin='round'")
st.html("<style>" + "".join(
    f".ik-{nama} {{ -webkit-mask-image: {uri_svg(isi.replace(chr(34), chr(39)), atribut=_ATR_IKON)}; "
    f"mask-image: {uri_svg(isi.replace(chr(34), chr(39)), atribut=_ATR_IKON)}; }} "
    for nama, isi in IKON.items()) + "</style>")


def ikon(nama):
    return f'<span class="ik ik-{nama}"></span>'


def kartu_angka(label, nilai, ket, nama_ikon, mini=""):
    return (f'<div class="kpi"><div class="kpi-atas"><div class="kpi-ikon">{ikon(nama_ikon)}</div>'
            f'<div class="kpi-label">{escape(label)}</div></div>'
            f'<div class="kpi-baris"><div class="kpi-nilai">{escape(str(nilai))}</div>{mini}</div>'
            f'<div class="kpi-ket">{escape(ket)}</div></div>')


@contextmanager
def kartu(kunci, judul, ket=None):
    """Kartu berbingkai dengan judul + keterangan; grafik digambar di dalam blok `with`."""
    with st.container(border=True, key=f"kartu_{kunci}"):
        st.html(f'<div class="kj">{escape(judul)}</div>'
                + (f'<div class="kk">{escape(ket)}</div>' if ket else ""))
        yield


def gaya(fig, tinggi=360, legenda=False, x=None, y=None):
    """Gaya grafik: tipis, grid redup, teks memakai warna teks (bukan warna seri).
    Judul grafik ditulis di kepala kartu, bukan di dalam grafik."""
    fig.update_layout(
        height=tinggi, margin=dict(l=8, r=12, t=34 if legenda else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=T["teks2"], size=12), showlegend=legenda,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, xanchor="left",
                    traceorder="normal", font=dict(color=T["teks2"])),
        hoverlabel=dict(font_size=13, bgcolor=T["kartu"], bordercolor=T["grid"],
                        font_color=T["teks"]),
        bargap=0.28, barcornerradius=4)
    fig.update_xaxes(showgrid=False, linecolor=T["grid"], title=x, zeroline=False,
                     tickfont=dict(color=T["teks2"]))
    fig.update_yaxes(gridcolor=T["grid"], zeroline=False, title=y, tickfont=dict(color=T["teks2"]))
    return fig


def tampil(fig):
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def ribuan(n):
    return f"{int(n):,}".replace(",", ".")


def koma(n, digit=1):
    return f"{float(n):.{digit}f}".replace(".", ",")


def tgl(d):
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def rgba(hex_, alfa):
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


@st.cache_data(show_spinner="Menyusun word cloud...", ttl=600)
def awan_kata(frekuensi):
    """Word cloud (PNG transparan) dari pasangan (kata, frekuensi)."""
    from io import BytesIO

    from wordcloud import WordCloud
    palet = ["#12335f", "#24599e", "#c8102e", "#5b9bd5", "#3b4a5e"]

    def warna_kata(*_, random_state=None, **__):
        return random_state.choice(palet)

    wc = WordCloud(width=1800, height=620, mode="RGBA", background_color=None, max_words=120,
                   prefer_horizontal=0.95, random_state=42, margin=6, color_func=warna_kata)
    gambar = BytesIO()
    wc.generate_from_frequencies(dict(frekuensi)).to_image().save(gambar, format="PNG")
    return gambar.getvalue()


def batang_label(d):
    """Batang mendatar jumlah berita per label sumber/topik. 'Belum terkelompok' diberi warna redup."""
    d = d.iloc[::-1]                                  # terbanyak di atas
    fig = go.Figure(go.Bar(
        x=d["jumlah"], y=d["label"], orientation="h",
        marker_color=[REDUP if l == BELUM else UTAMA for l in d["label"]],
        text=[f"{ribuan(v)}  ·  {koma(p)}%" for v, p in zip(d["jumlah"], d["persen"])],
        textposition="outside", textfont=dict(color=T["teks2"]),
        hovertemplate="%{y}<br>%{x} berita<extra></extra>"))
    fig.update_traces(cliponaxis=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, float(d["jumlah"].max()) * 1.35])
    fig.update_yaxes(showgrid=False)
    return gaya(fig, tinggi=60 + 34 * len(d))


# ------------------------------------------------------------------ koneksi & query
@st.cache_resource
def ambil_engine():
    return koneksi.buat_engine()


@st.cache_data(show_spinner="Menjalankan query...", ttl=600)
def q(sql, **param):
    """Menjalankan satu query SQL dan mengembalikan hasilnya sebagai tabel."""
    with ambil_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=param)


if ambil_engine() is None:
    st.error("Pengaturan database belum diisi. Di laptop: salin .env.example menjadi .env lalu isi "
             "DB_PASSWORD. Di Streamlit Cloud: isi Settings → Secrets (lihat DEPLOY.md).")
    st.stop()
try:
    rentang_data = q(kueri.RENTANG).iloc[0]
except Exception as e:
    st.error("Database PostgreSQL tidak bisa dibaca. Pastikan PostgreSQL menyala dan "
             "`python 02_load.py` sudah dijalankan.\n\nPenyebab: " + str(e).splitlines()[0])
    st.stop()
if rentang_data.tgl_min is None:
    st.error("Tabel berita masih kosong. Jalankan dulu: `python 02_load.py`")
    st.stop()

# ------------------------------------------------------------------ filter (sidebar)
tgl_min, tgl_max = rentang_data.tgl_min, rentang_data.tgl_max

with st.sidebar:
    st.html('<div class="merek"><div class="merek-logo">KJ</div><div><b>Berita Kominfo Jatim</b>'
            '<span>Dashboard analisis publikasi</span></div></div>')
    st.subheader("Filter")
    daftar_tahun = [str(t) for t in range(tgl_min.year, tgl_max.year + 1)]
    periode = st.segmented_control("Periode", ["Semua", *daftar_tahun, "Kustom"], default="Semua")
    if periode == "Kustom":
        rentang = st.date_input("Rentang tanggal", (tgl_min, tgl_max),
                                min_value=tgl_min, max_value=tgl_max)
        if isinstance(rentang, tuple) and len(rentang) == 2:
            awal, akhir = rentang
        else:
            awal, akhir = tgl_min, tgl_max
    elif periode in daftar_tahun:
        awal = max(tgl_min, date(int(periode), 1, 1))
        akhir = min(tgl_max, date(int(periode), 12, 31))
    else:
        awal, akhir = tgl_min, tgl_max
    grup_pilih = st.multiselect("Grup kategori", GRUP, default=GRUP)
    st.html(f'<div class="info-data"><b>Sumber data</b><br>PostgreSQL · kominfo_jatim<br>'
            f'<b>Data tersedia</b><br>{tgl(tgl_min)} – {tgl(tgl_max)}</div>')

# Parameter filter yang dikirim ke setiap query (:awal, :akhir, :grup)
F = dict(awal=awal, akhir=akhir, grup=list(grup_pilih))

# ------------------------------------------------------------------ header
st.html(f"""
<div class="kepala">
  <div>
    <div class="hero-label">Dinas Kominfo Provinsi Jawa Timur · Analisis Publikasi</div>
    <h1>Publikasi Berita Dinas Kominfo Jawa Timur</h1>
    <p>Sumber: kominfo.jatimprov.go.id/berita (scraping). Analisis memakai judul, waktu, dan
       kategori berita; isi berita tidak termasuk.</p>
  </div>
  <div class="chips">
    <span class="chip">{ikon('kalender')}{tgl(awal)} – {tgl(akhir)}</span>
    <span class="chip">{ikon('lapis')}{len(grup_pilih)} dari {len(GRUP)} grup kategori</span>
  </div>
</div>""")

# ------------------------------------------------------------------ data ringkasan
kpi = q(kueri.KPI, **F).iloc[0]
if kpi.total == 0:
    st.warning("Tidak ada berita pada filter ini. Ubah periode atau grup kategori.")
    st.stop()
jam_puncak = int(kpi.jam_puncak)
per_bulan = q(kueri.TREN_BULANAN, **F)
ph = q(kueri.PER_HARI, **F)
pj = q(kueri.PER_JAM, **F)
hari_puncak = ph.loc[ph["jumlah"].idxmax()]
jam_ramai = pj.loc[pj["jumlah"].idxmax()]

jan_okt = q(kueri.JAN_OKT, **F).iloc[0]
ada_dua_tahun = jan_okt.t2025 > 0 and jan_okt.t2026 > 0
ada_klas = q(kueri.ADA_KLASIFIKASI).iloc[0, 0] > 0   # klasifikasi sumber/topik sudah diisi?
temuan = []
if ada_dua_tahun:
    u = float(jan_okt.perubahan_persen)
    arah = "turun" if u < 0 else "naik"
    temuan.append(f"Jumlah berita Jan–Okt 2026 <b>{arah} {abs(u):.0f}%</b> dibanding Jan–Okt 2025 "
                  f"({ribuan(jan_okt.t2025)} → {ribuan(jan_okt.t2026)}).")
    if ada_klas and u < 0:
        bs = q(kueri.BANDING_KLASIFIKASI, jenis="sumber", **F)
        turun = bs[(bs["label"] != BELUM) & (bs["selisih"] < 0)].head(2)
        if not turun.empty:
            nama = " dan ".join(f"<b>{escape(l)}</b> ({ribuan(-s)} berita lebih sedikit)"
                                for l, s in zip(turun["label"], turun["selisih"]))
            kalimat = (f"Penurunan terbesar berasal dari berita {nama}, sekitar "
                       f"<b>{turun['porsi_perubahan'].sum():.0f}%</b> dari total penurunan.")
            pemprov = bs[bs["label"] == "Gubernur/Pemprov Jatim"]
            if not pemprov.empty and pemprov["perubahan_persen"].notna().all():
                pp = float(pemprov["perubahan_persen"].iloc[0])
                kalimat += (f" Berita Gubernur/Pemprov Jatim {'turun' if pp < 0 else 'naik'} "
                            f"{abs(pp):.0f}%.")
            temuan.append(kalimat)
kalimat_umum = (f"<b>{kpi.persen_umum:.0f}%</b> berita berkategori UMUM; kategori khusus (event, "
                f"gubernur, olahraga) muncul sebagai lonjakan.")
if ada_klas and "UMUM" in grup_pilih:
    isi_umum = q(kueri.KLASIFIKASI, jenis="sumber", **{**F, "grup": ["UMUM"]})
    isi_umum = isi_umum[isi_umum["label"] != BELUM]
    if not isi_umum.empty:
        kalimat_umum += (f" Isi UMUM terbanyak: berita <b>{escape(isi_umum['label'].iloc[0])}</b> "
                         f"({koma(isi_umum['persen'].iloc[0])}%).")
temuan.append(kalimat_umum)
temuan.append(f"<b>{kpi.persen_hari_kerja:.0f}%</b> berita terbit pada hari kerja, dengan puncak "
              f"sekitar pukul <b>{jam_puncak:02d}.00</b>.")

tab_ring, tab_kat, tab_waktu, tab_kata, tab_banding, tab_data = st.tabs(
    [":material/dashboard: Ringkasan", ":material/category: Kategori",
     ":material/schedule: Pola waktu", ":material/sell: Kata kunci",
     ":material/compare_arrows: 2025 vs 2026", ":material/table_rows: Data"])


def donat(label, nilai, warna, tengah):
    """Grafik donat: porsi dari keseluruhan; angka persen ditulis di legenda."""
    total = float(sum(nilai)) or 1
    fig = go.Figure(go.Pie(
        labels=[f"{n} · {koma(100 * v / total)}%" for n, v in zip(label, nilai)], values=nilai,
        hole=0.68, sort=False, direction="clockwise", textinfo="none",
        domain=dict(x=[0, 1], y=[0.36, 1]),
        marker=dict(colors=warna, line=dict(color=T["kartu"], width=2)),
        customdata=[ribuan(v) for v in nilai],
        hovertemplate="%{label}<br>%{customdata} berita<extra></extra>"))
    fig.add_annotation(text=tengah, x=0.5, y=0.68, yanchor="middle", showarrow=False,
                       font=dict(color=T["teks"], size=14))
    gaya(fig, tinggi=330, legenda=True)
    fig.update_layout(margin=dict(l=8, r=8, t=8, b=8),
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=0.30, yanchor="top",
                                  font=dict(size=11.5)))
    return fig


# ------------------------------------------------------------------ tab Ringkasan
with tab_ring:
    kiri, kanan = st.columns([2.15, 1])
    with kiri:
        st.html(
            '<div class="ubin-grid">'
            f'<div class="ubin ubin-a"><div class="ubin-label">Total berita</div>'
            f'<div class="ubin-nilai">{ribuan(kpi.total)}</div>'
            f'<div class="ubin-ket">{len(per_bulan)} bulan dalam filter</div>'
            '</div>'
            f'<div class="ubin ubin-b"><div class="ubin-label">Rata-rata per hari</div>'
            f'<div class="ubin-nilai">{koma(kpi.rata2_per_hari)} <small>berita</small></div>'
            f'<div class="ubin-ket">terbit setiap hari</div></div>'
            '<div class="ubin-tumpuk">'
            f'<div class="mini"><div class="kpi-ikon">{ikon("grafik")}</div>'
            f'<div class="mini-teks"><small>Bulan terpadat</small><b>{escape(str(kpi.bulan_puncak))}</b></div>'
            f'<span class="mini-chip">{ribuan(kpi.jumlah_bulan_puncak)} berita</span></div>'
            f'<div class="mini"><div class="kpi-ikon">{ikon("jam")}</div>'
            f'<div class="mini-teks"><small>Jam terpadat</small><b>{jam_puncak:02d}.00</b></div>'
            f'<span class="mini-chip">{kpi.persen_hari_kerja:.0f}% hari kerja</span></div>'
            '</div></div>')

        with kartu("tren", "Jumlah berita per bulan",
                   "Garis biru = jumlah berita; garis merah putus-putus = rata-rata bergerak 3 bulan."):
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=per_bulan["label"], y=per_bulan["jumlah"], mode="lines+markers",
                name="Jumlah berita", line=dict(color=UTAMA, width=2),
                fill="tozeroy", fillcolor=rgba(UTAMA, 0.10),
                marker=dict(size=8, color=UTAMA, line=dict(width=2, color=T["kartu"])),
                hovertemplate="%{y} berita<extra></extra>"))
            fig.add_trace(go.Scatter(
                x=per_bulan["label"], y=per_bulan["rata3"], mode="lines",
                name="Rata-rata bergerak 3 bulan", line=dict(color=KEDUA, width=2, dash="dot"),
                hovertemplate="rata-rata 3 bulan: %{y}<extra></extra>"))
            puncak = per_bulan.loc[per_bulan["jumlah"].idxmax()]
            fig.add_annotation(x=puncak["label"], y=puncak["jumlah"], yshift=10, showarrow=False,
                               yanchor="bottom", text=f"<b>Puncak · {ribuan(puncak['jumlah'])}</b>",
                               font=dict(color=T["teks"], size=12))
            fig.update_layout(hovermode="x unified")
            fig.update_xaxes(categoryorder="array", categoryarray=per_bulan["label"], tickangle=-45)
            fig.update_yaxes(rangemode="tozero", range=[0, float(per_bulan["jumlah"].max()) * 1.18])
            tampil(gaya(fig, tinggi=330, legenda=True, y="Berita"))
            if (per_bulan["label"] == "Okt 2026").any():
                st.caption("Catatan: data Oktober 2026 hanya sampai 28 Oktober.")

        d1, d2 = st.columns(2)
        jg = q(kueri.PER_GRUP, **F)
        with d1, kartu("donat_grup", "Berita per grup kategori", "Porsi tiap grup dari total berita."):
            tampil(donat(jg["grup_kategori"], jg["jumlah"],
                         [WARNA_GRUP.get(g, T["seri"][-1]) for g in jg["grup_kategori"]],
                         f"<b>{ribuan(kpi.total)}</b><br>berita"))
        akhir_pekan = int(ph.loc[ph["nama_hari"].isin(["Sabtu", "Minggu"]), "jumlah"].sum())
        with d2, kartu("donat_pekan", "Hari kerja vs akhir pekan", "Kapan berita lebih banyak terbit."):
            tampil(donat(["Hari kerja", "Akhir pekan"], [int(kpi.total) - akhir_pekan, akhir_pekan],
                         [UTAMA, KEDUA], f"<b>{kpi.persen_hari_kerja:.0f}%</b><br>hari kerja"))

    with kanan:
        with kartu("ritme", "Ritme harian", "Jumlah berita menurut jam terbit (00–23)."):
            fig = go.Figure(go.Scatter(
                x=[f"{j:02d}" for j in pj["jam"]], y=pj["jumlah"], mode="lines",
                line=dict(color=UTAMA, width=2), fill="tozeroy", fillcolor=rgba(UTAMA, 0.22),
                hovertemplate="Pukul %{x}.00<br>%{y} berita<extra></extra>"))
            fig.add_trace(go.Scatter(
                x=[f"{int(jam_ramai['jam']):02d}"], y=[jam_ramai["jumlah"]], mode="markers",
                marker=dict(size=10, color=UTAMA, line=dict(width=2, color=T["kartu"])),
                hoverinfo="skip"))
            fig.add_annotation(x=f"{int(jam_ramai['jam']):02d}", y=jam_ramai["jumlah"], yshift=10,
                               showarrow=False, yanchor="bottom",
                               text=f"<b>Pukul {int(jam_ramai['jam']):02d}.00 · {ribuan(jam_ramai['jumlah'])}</b>",
                               font=dict(color=T["teks"], size=12))
            fig.update_xaxes(type="category", dtick=4)
            fig.update_yaxes(rangemode="tozero", range=[0, float(pj["jumlah"].max()) * 1.25])
            tampil(gaya(fig, tinggi=300))

        with kartu("hari", "Berita per hari",
                   f"Tersibuk: {hari_puncak['nama_hari']} ({ribuan(hari_puncak['jumlah'])} berita)."):
            fig = go.Figure(go.Bar(
                x=ph["nama_hari"].str[:3], y=ph["jumlah"],
                marker_color=[KEDUA if v == ph["jumlah"].max() else REDUP for v in ph["jumlah"]],
                customdata=ph["nama_hari"],
                hovertemplate="%{customdata}<br>%{y} berita<extra></extra>"))
            tampil(gaya(fig, tinggi=TINGGI_HARI))

    st.html('<div class="judul-bagian"><b>Temuan utama</b><span>dihitung dari filter saat ini</span></div>'
            '<div class="temuan-grid">'
            + "".join(f'<div class="temuan"><div class="temuan-no">{i:02d}</div>'
                      f'<div class="temuan-isi">{t}</div></div>' for i, t in enumerate(temuan, 1))
            + '</div>')

# ------------------------------------------------------------------ tab Kategori
with tab_kat:
    with kartu("komposisi", "Komposisi grup kategori per bulan",
               "Pilih Persentase untuk melihat porsi tiap grup, terlepas dari naik-turunnya jumlah."):
        tampilan = st.segmented_control("Tampilan", ["Jumlah", "Persentase"], default="Jumlah",
                                        label_visibility="collapsed", key="tampilan_komposisi")
        persen = tampilan == "Persentase"
        pg = q(kueri.KOMPOSISI_BULANAN, **F)
        fig = go.Figure()
        for g in GRUP:
            s = pg[pg["grup_kategori"] == g]
            if s.empty:
                continue
            fig.add_trace(go.Bar(
                x=s["label"], y=s["jumlah"], name=g, marker_color=WARNA_GRUP[g],
                marker_line=dict(width=1.5, color=T["kartu"]),
                hovertemplate=g + (": %{y:.1f}%" if persen else ": %{y}") + "<extra></extra>"))
        fig.update_layout(barmode="stack", barnorm="percent" if persen else None,
                          hovermode="x unified")
        fig.update_xaxes(categoryorder="array", categoryarray=per_bulan["label"], tickangle=-45)
        if persen:
            fig.update_yaxes(ticksuffix="%", range=[0, 100])
        tampil(gaya(fig, tinggi=400, legenda=True, y="Porsi berita" if persen else "Berita"))

    c1, c2 = st.columns(2)
    jg = jg.iloc[::-1]                              # terbanyak di atas pada grafik batang mendatar
    fig = go.Figure(go.Bar(
        x=jg["jumlah"], y=jg["grup_kategori"], orientation="h",
        marker_color=[WARNA_GRUP.get(g, T["seri"][-1]) for g in jg["grup_kategori"]],
        text=[f"{ribuan(v)}  ·  {koma(p)}%" for v, p in zip(jg["jumlah"], jg["persen"])],
        textposition="outside", textfont=dict(color=T["teks2"]),
        hovertemplate="%{y}<br>%{x} berita (%{customdata:.1f}%)<extra></extra>",
        customdata=jg["persen"]))
    fig.update_traces(cliponaxis=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, jg["jumlah"].max() * 1.32])
    with c1, kartu("grup", "Berita per grup kategori", "Jumlah berita dan porsinya dari total."):
        tampil(gaya(fig, tinggi=420))
    jk = q(kueri.KATEGORI_TERBANYAK, n=12, **F).iloc[::-1]
    fig = go.Figure(go.Bar(x=jk["jumlah"], y=jk["nama_kategori"], orientation="h", marker_color=UTAMA,
                           text=[ribuan(v) for v in jk["jumlah"]],
                           textposition="outside", textfont=dict(color=T["teks2"]),
                           hovertemplate="%{y}<br>%{x} berita<extra></extra>"))
    fig.update_traces(cliponaxis=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, jk["jumlah"].max() * 1.18])
    with c2, kartu("kategori", "12 kategori asli terbanyak",
                   "Nama kategori seperti tertulis di situs, sebelum dikelompokkan."):
        tampil(gaya(fig, tinggi=420))
    st.caption("Kategori EVENT KHUSUS mencakup PORPROV, MTQ, STQH, PORNAS, FORDA, FORNAS, "
               "Jatim Digifest, Kabar Haji, dan Pilkada. Pengelompokan dapat diubah di 01_cleaning.sql.")

    st.html('<div class="judul-bagian"><b>Isi berita menurut sumber dan topik</b>'
            '<span>pengelompokan tambahan dari judul; kategori asli tidak diubah</span></div>')
    if not ada_klas:
        st.info("Tabel klasifikasi_berita masih kosong. Jalankan dulu: `python 04_text_mining.py`")
    else:
        with kartu("isi", "Berita ini tentang siapa, dan tentang apa?",
                   "Situs tidak punya kategori wilayah atau topik, sehingga sebagian besar berita masuk "
                   "UMUM. Sumber = siapa yang diberitakan; topik = pokok bahasannya. Setiap berita "
                   "mendapat satu sumber dan satu topik."):
            cakupan = st.segmented_control("Cakupan", ["Hanya UMUM", "Semua grup terpilih"],
                                           default="Hanya UMUM", label_visibility="collapsed",
                                           key="cakupan_isi")
            grup_isi = list(grup_pilih) if cakupan == "Semua grup terpilih" else \
                [g for g in grup_pilih if g == "UMUM"]
            if not grup_isi:
                st.info("Grup UMUM tidak dipilih di filter. Pilih UMUM atau ubah cakupan.")
            else:
                c1, c2 = st.columns(2)
                for kolom, jenis, judul in ((c1, "sumber", "Sumber berita"), (c2, "topik", "Topik berita")):
                    with kolom:
                        st.html(f'<div class="kj">{judul}</div>')
                        tampil(batang_label(q(kueri.KLASIFIKASI, jenis=jenis, **{**F, "grup": grup_isi})))
        with st.expander("Cara pengelompokan sumber dan topik"):
            st.markdown(
                "Pengelompokan dibuat di PostgreSQL oleh `klasifikasi.sql` dengan **aturan kata kunci** "
                "pada judul berita (bukan machine learning):\n"
                "1. Judul diubah menjadi huruf kecil.\n"
                "2. Judul dicocokkan ke aturan di bawah secara berurutan; **aturan pertama yang cocok** "
                "menentukan labelnya.\n"
                "3. Judul yang tidak cocok dengan aturan mana pun diberi label *Belum terkelompok*.\n\n"
                "Karena hanya memakai judul, sebagian berita bisa salah kelompok. Angka ini cocok untuk "
                "melihat pola besar, bukan hitungan pasti. Aturan dapat diubah di `klasifikasi.sql`.")
            st.dataframe(q(kueri.ATURAN), hide_index=True, width="stretch",
                         column_config={"jenis": "Jenis", "urutan": "Urutan", "label": "Label",
                                        "pola": st.column_config.TextColumn("Pola (regex)", width="large")})

# ------------------------------------------------------------------ tab Pola waktu
with tab_waktu:
    st.html('<div class="label-grid">'
            f'<div class="label-info"><small>Hari tersibuk</small><b>{escape(str(hari_puncak["nama_hari"]))}</b></div>'
            f'<div class="label-info"><small>Jam tersibuk</small><b>{int(jam_ramai["jam"]):02d}.00</b></div>'
            f'<div class="label-info"><small>Terbit di hari kerja</small><b>{kpi.persen_hari_kerja:.0f}%</b></div>'
            f'<div class="label-info"><small>Terbit di akhir pekan</small><b>{100 - kpi.persen_hari_kerja:.0f}%</b></div>'
            '</div>')
    hj = q(kueri.HARI_X_JAM, **F)                   # 168 baris: tinggal disusun jadi 7 x 24
    skala = [[i / (len(T["urut"]) - 1), c] for i, c in enumerate(T["urut"])]
    fig = go.Figure(go.Heatmap(z=hj["jumlah"].to_numpy().reshape(7, 24),
                               x=[f"{j:02d}" for j in range(24)], y=ph["nama_hari"],
                               colorscale=skala, xgap=3, ygap=3,
                               colorbar=dict(title="Berita", thickness=10, outlinewidth=0,
                                             tickfont=dict(color=T["teks2"])),
                               hovertemplate="%{y}, pukul %{x}.00<br>%{z} berita<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(type="category")
    with kartu("heatmap", "Kapan berita terbit? (hari × jam)",
               "Semakin pekat warnanya, semakin banyak berita yang terbit pada hari dan jam itu."):
        tampil(gaya(fig, tinggi=380, x="Jam"))
    fig = go.Figure(go.Bar(
        x=[f"{j:02d}" for j in pj["jam"]], y=pj["jumlah"],
        marker_color=[KEDUA if v == pj["jumlah"].max() else REDUP for v in pj["jumlah"]],
        hovertemplate="Pukul %{x}.00<br>%{y} berita<extra></extra>"))
    fig.update_xaxes(type="category")
    with kartu("jam", "Berita per jam publikasi",
               "Warna lebih kuat menandai jam dengan berita terbanyak."):
        tampil(gaya(fig, tinggi=300, x="Jam", y="Berita"))

# ------------------------------------------------------------------ tab Kata kunci
with tab_kata:
    if q(kueri.JUMLAH_TOKEN).iloc[0, 0] == 0:
        st.info("Tabel kata_berita masih kosong. Jalankan dulu: `python 04_text_mining.py`")
    else:
        semua_kata = q(kueri.KATA_TERBANYAK, n=120, **F)
        tk = semua_kata.head(30)                    # 20 teratas untuk grafik, 30 untuk pilihan kata
        with kartu("awan", "Word cloud judul berita",
                   "Semakin besar katanya, semakin sering muncul di judul. Mengikuti filter saat ini."):
            st.image(awan_kata(tuple(zip(semua_kata["kata"], semua_kata["frekuensi"].astype(int)))),
                     width="stretch")
        c1, c2 = st.columns(2)
        g20 = tk.head(20).iloc[::-1]
        fig = go.Figure(go.Bar(x=g20["frekuensi"], y=g20["kata"], orientation="h", marker_color=UTAMA,
                               hovertemplate="%{y}: %{x} judul<extra></extra>"))
        fig.update_xaxes(showgrid=True, gridcolor=T["grid"])
        fig.update_yaxes(showgrid=False)
        with c1, kartu("kata", "20 kata terbanyak di judul",
                       "Setelah kata umum (stopword) dibuang."):
            tampil(gaya(fig, tinggi=520))
        tb = q(kueri.BIGRAM_TERBANYAK, n=15, **F).iloc[::-1]
        fig = go.Figure(go.Bar(x=tb["frekuensi"], y=tb["bigram"], orientation="h", marker_color=UTAMA,
                               hovertemplate="%{y}: %{x} judul<extra></extra>"))
        fig.update_xaxes(showgrid=True, gridcolor=T["grid"])
        fig.update_yaxes(showgrid=False)
        with c2, kartu("bigram", "15 pasangan kata terbanyak",
                       "Dua kata yang muncul bersebelahan dalam satu judul."):
            tampil(gaya(fig, tinggi=520))

        with kartu("tren_kata", "Tren sebuah kata",
                   "Berapa judul per bulan yang memuat kata pilihan Anda."):
            c1, c2 = st.columns([1, 1])
            pilih = c1.selectbox("Pilih kata dari yang terbanyak", tk["kata"].tolist())
            bebas = c2.text_input("…atau ketik kata sendiri (huruf kecil)", "").strip().lower()
            kata = bebas or pilih
            tr = q(kueri.TREN_KATA, kata=kata, **F)
            if tr.empty:
                st.info(f"Kata “{kata}” tidak ditemukan pada filter ini.")
            else:
                fig = go.Figure(go.Scatter(
                    x=tr["label"], y=tr["jumlah"], mode="lines+markers",
                    line=dict(color=UTAMA, width=2), fill="tozeroy", fillcolor=rgba(UTAMA, 0.10),
                    marker=dict(size=8, color=UTAMA, line=dict(width=2, color=T["kartu"])),
                    hovertemplate="%{x}<br>%{y} judul memuat “" + kata + "”<extra></extra>"))
                fig.update_xaxes(categoryorder="array", categoryarray=tr["label"], tickangle=-45)
                fig.update_yaxes(rangemode="tozero")
                tampil(gaya(fig, tinggi=300, y="Judul"))

        with st.expander("Kata paling khas tiap grup kategori (TF-IDF)"):
            st.dataframe(q(kueri.KATA_KHAS, n=8, **F), hide_index=True, width="stretch")

# ------------------------------------------------------------------ tab Perbandingan
with tab_banding:
    if ada_dua_tahun:
        b = q(kueri.BANDING_BULANAN, **F)
        ubah = float(jan_okt.perubahan_persen)
        selisih = int(jan_okt.t2026) - int(jan_okt.t2025)
        st.html('<div class="kpi-grid">'
                + kartu_angka("Jan–Okt 2025", ribuan(jan_okt.t2025), "berita", "kalender")
                + kartu_angka("Jan–Okt 2026", ribuan(jan_okt.t2026), "berita", "kalender")
                + kartu_angka("Perubahan", f"{ubah:+.1f}%".replace(".", ",").replace("-", "−"),
                              f"{'naik' if selisih >= 0 else 'turun'} {ribuan(abs(selisih))} berita "
                              "dibanding 2025", "grafik")
                + '</div>')
        fig = go.Figure()
        for th, warna in ((2025, UTAMA), (2026, KEDUA)):
            fig.add_trace(go.Bar(x=b["nama_bulan"].str[:3], y=b[f"t{th}"], name=str(th),
                                 marker_color=warna,
                                 marker_line=dict(width=1.5, color=T["kartu"]),
                                 hovertemplate=str(th) + ": %{y} berita<extra></extra>"))
        fig.update_layout(barmode="group", hovermode="x unified")
        with kartu("banding", "Berita per bulan, Jan–Okt",
                   "Periode yang sama (Januari–Oktober) karena data 2026 belum lengkap setahun."):
            tampil(gaya(fig, legenda=True, y="Berita"))
        tabel = b.drop(columns="bulan").rename(columns={
            "nama_bulan": "Bulan", "t2025": "2025", "t2026": "2026",
            "selisih": "Selisih", "perubahan_persen": "Perubahan (%)"})
        with kartu("tabel_banding", "Rincian per bulan"):
            st.dataframe(tabel, hide_index=True, width="stretch", column_config={
                "Selisih": st.column_config.NumberColumn(format="%+d"),
                "Perubahan (%)": st.column_config.NumberColumn(format="%+.1f%%")})

        st.html('<div class="judul-bagian"><b>Berita apa yang berkurang?</b>'
                '<span>Jan–Okt, menurut sumber atau topik berita (lihat tab Kategori)</span></div>')
        if not ada_klas:
            st.info("Tabel klasifikasi_berita masih kosong. Jalankan dulu: `python 04_text_mining.py`")
        else:
            with kartu("banding_isi", "Jumlah berita Jan–Okt menurut sumber atau topik",
                       "Angka di ujung batang 2026 = persen perubahan dari 2025. "
                       "Data hanya menunjukkan di mana penurunan terjadi, bukan penyebabnya."):
                pilih_jenis = st.segmented_control("Kelompokkan menurut", ["Sumber", "Topik"],
                                                   default="Sumber", label_visibility="collapsed",
                                                   key="jenis_banding")
                jenis_b = (pilih_jenis or "Sumber").lower()
                bk = q(kueri.BANDING_KLASIFIKASI, jenis=jenis_b, **F)
                gb = pd.concat([bk[bk["label"] == BELUM],              # paling bawah
                                bk[bk["label"] != BELUM].sort_values("t2025")])
                fig = go.Figure()
                # Batang mendatar digambar dari bawah: 2026 dulu supaya 2025 tampil di atas
                for th, warna in ((2026, KEDUA), (2025, UTAMA)):
                    teks = None
                    if th == 2026:
                        teks = [f"{p:+.0f}%".replace("-", "−") if pd.notna(p) else ""
                                for p in gb["perubahan_persen"]]
                    fig.add_trace(go.Bar(
                        x=gb[f"t{th}"], y=gb["label"], orientation="h", name=str(th),
                        marker_color=warna, text=teks, textposition="outside",
                        textfont=dict(color=T["teks"]),
                        hovertemplate=str(th) + ": %{x} berita<extra></extra>"))
                fig.update_traces(cliponaxis=False)
                fig.update_layout(barmode="group", bargap=0.22, bargroupgap=0.06)
                fig.update_xaxes(range=[0, float(gb["t2025"].max()) * 1.12])
                gaya(fig, tinggi=90 + 46 * len(gb), legenda=True, x="Berita")
                tampil(fig.update_layout(legend_traceorder="reversed"))   # legenda: 2025, 2026
                rinci = bk.rename(columns={
                    "label": "Sumber" if jenis_b == "sumber" else "Topik", "t2025": "2025",
                    "t2026": "2026", "selisih": "Selisih", "perubahan_persen": "Perubahan (%)",
                    "porsi_perubahan": "Porsi dari total perubahan (%)"})
                st.dataframe(rinci, hide_index=True, width="stretch", column_config={
                    "Selisih": st.column_config.NumberColumn(format="%+d"),
                    "Perubahan (%)": st.column_config.NumberColumn(format="%+.1f%%"),
                    "Porsi dari total perubahan (%)": st.column_config.NumberColumn(format="%.1f%%")})

            tk = q(kueri.TREN_KLASIFIKASI, jenis=jenis_b, **F)
            with kartu("tren_isi", "Tren per kuartal",
                       "Hanya kuartal yang datanya lengkap, jadi Oktober 2026 tidak ikut. "
                       "Pilih hingga 5 kelompok untuk dibandingkan."):
                if tk.empty:
                    st.info("Belum ada kuartal lengkap pada filter ini.")
                else:
                    total = tk.groupby("label")["jumlah"].sum().sort_values(ascending=False)
                    pilihan = [l for l in total.index if l != BELUM] + ([BELUM] if BELUM in total.index else [])
                    dipilih = st.multiselect("Kelompok", pilihan, default=pilihan[:4], max_selections=5,
                                             label_visibility="collapsed", key=f"tren_isi_{jenis_b}")
                    urutan_periode = tk.drop_duplicates("periode")["periode"].tolist()
                    fig = go.Figure()
                    for i, l in enumerate(dipilih):
                        s = tk[tk["label"] == l].set_index("periode").reindex(urutan_periode, fill_value=0)
                        warna = T["seri"][i % len(T["seri"])]
                        fig.add_trace(go.Scatter(
                            x=urutan_periode, y=s["jumlah"], mode="lines+markers", name=l,
                            line=dict(color=warna, width=2),
                            marker=dict(size=8, color=warna, line=dict(width=2, color=T["kartu"])),
                            hovertemplate=escape(l) + ": %{y} berita<extra></extra>"))
                    fig.update_layout(hovermode="x unified")
                    fig.update_xaxes(categoryorder="array", categoryarray=urutan_periode)
                    fig.update_yaxes(rangemode="tozero")
                    tampil(gaya(fig, tinggi=360, legenda=True, y="Berita"))
    else:
        st.info("Perbandingan butuh data 2025 dan 2026 pada filter. Perluas periode.")

# ------------------------------------------------------------------ tab Data
with tab_data:
    with kartu("data", "Daftar berita", "Tabel menampilkan paling banyak 1.000 baris terbaru; "
               "unduhan CSV berisi seluruh hasil filter."):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        cari = c1.text_input("Cari kata di judul", "", placeholder="mis. banjir, UMKM, gubernur").strip()
        c2.download_button("Unduh CSV", icon=":material/download:", width="stretch",
                           data=q(kueri.DATA, cari=cari, batas=None, **F)
                           .to_csv(index=False).encode("utf-8-sig"),
                           file_name="berita_terfilter.csv", mime="text/csv")
        st.caption(f"{ribuan(q(kueri.DATA_JUMLAH, cari=cari, **F).iloc[0, 0])} berita ditemukan")
        st.dataframe(q(kueri.DATA, cari=cari, batas=1000, **F), hide_index=True, width="stretch",
                     column_config={
                         "tanggal_publikasi": st.column_config.DatetimeColumn(
                             "Tanggal publikasi", format="D MMM YYYY, HH.mm"),
                         "judul": st.column_config.TextColumn("Judul", width="large"),
                         "kategori": "Kategori", "kategori_grup": "Grup kategori",
                         "sumber": "Sumber (dari judul)", "topik": "Topik (dari judul)"})

st.html(f'<div class="kaki"><span>Sumber: kominfo.jatimprov.go.id/berita · diolah dengan PostgreSQL</span>'
        f'<span>Data {tgl(tgl_min)} – {tgl(tgl_max)}</span></div>')
