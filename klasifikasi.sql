-- ============================================================
-- klasifikasi.sql | Klasifikasi sumber dan topik berita dari judul
-- Input : tabel berita
-- Output: tabel aturan_klasifikasi dan klasifikasi_berita
-- Dijalankan otomatis oleh 04_text_mining.py. Boleh juga dijalankan
-- ulang di pgAdmin (blok semua, F5) setelah aturan diubah.
--
-- Kenapa perlu: 78% berita di situs berkategori UMUM. Situs tidak punya
-- kategori wilayah atau topik, jadi isi UMUM tidak terlihat. File ini
-- menambah dua label untuk setiap berita, tanpa mengubah kategori asli:
--   sumber = siapa yang diberitakan (Pemkab/Pemkot, kampus, DPRD, ...)
--   topik  = berita itu tentang apa (ekonomi, pendidikan, kesehatan, ...)
--
-- Cara kerja:
--   1. Judul diubah menjadi huruf kecil.
--   2. Judul dicocokkan ke aturan (regex) berurutan, urutan kecil dulu.
--   3. Aturan pertama yang cocok menentukan label. Satu berita = satu label.
--   4. Judul yang tidak cocok dengan aturan mana pun diberi label
--      'Belum terkelompok'.
-- Penulisan pola: \y = batas kata, | = atau, ? = huruf sebelumnya boleh ada/tidak.
-- Ubah atau tambah aturan di bagian A, lalu jalankan ulang file ini.
-- ============================================================

TRUNCATE aturan_klasifikasi, klasifikasi_berita;

-- A. Aturan kata kunci ------------------------------------------

-- A1. SUMBER: siapa yang diberitakan
INSERT INTO aturan_klasifikasi (jenis, urutan, label, pola) VALUES
('sumber',  1, 'DPRD',
 '\ydprd\y|\ykomisi [a-e]\y|raperda|\yperda\y|fraksi|\yreses\y|anggota dewan|ketua dewan|legislator|pansus|banggar'),
('sumber',  2, 'Gubernur/Pemprov Jatim',
 'gubernur|khofifah|\yemil\y|wagub|pemprov|sekdaprov|grahadi|adhy karyono|provinsi jawa timur'),
-- Kominfo Jatim, kecuali yang diikuti nama kabupaten/kota (Kominfo Gresik = Pemkab)
('sumber',  3, 'Diskominfo Jatim',
 'kominfo\y(?!\s+(kab|kabupaten|kota|pacitan|ponorogo|trenggalek|tulungagung|blitar|kediri|malang|lumajang|jember|banyuwangi|bondowoso|situbondo|probolinggo|pasuruan|sidoarjo|mojokerto|jombang|nganjuk|madiun|magetan|ngawi|bojonegoro|tuban|lamongan|gresik|bangkalan|sampang|pamekasan|sumenep|batu|surabaya)\y)|cerdig|\yppid\y|klinik hoaks|jatim connect|media summit'),
-- Perangkat daerah provinsi: nama dinas/badan yang diikuti "jatim"
('sumber',  4, 'Gubernur/Pemprov Jatim',
 '\y(dinas|disnakertrans|dinkes|dindik|disperindag|diskop|disbudpar|dispora|dishub|dkp|dlh|dpmd|dinsos|bkd|bpsdm|bapenda|bappeda|bakorwil|biro|rsud|rsj|bpbd|upt|satpol pp|dpupr|bpkad|inspektorat|dpmptsp|dispertan|dkpp|disperkim)\y[^,]{0,30}\y(jatim|jawa timur)\y'),
('sumber',  5, 'Pemkab/Pemkot',
 'pemkab|pemkot|bupati|wali ?kota|walkot|wabup|wawali|camat|kecamatan|kelurahan|\ylurah\y|kepala desa|\ykades\y|\ypkk\y|\y(dinkes|dishub|dindik|disdik|dinsos|dlh|bpbd|bapenda|bappeda|dpupr|rsud|diskominfo|brida|disdukcapil|dispendukcapil)\y'),
('sumber',  6, 'TNI/Polri/penegak hukum',
 '\ytni\y|polri|polda|polres|polsek|polrestabes|kapolda|kapolres|kodam|korem|kodim|pangdam|danrem|dandim|lanal|lantamal|koarmada|kodiklatal|brimob|kejati|kejari|kejaksaan|\ybnn\y|basarnas|lanud|marinir|\ypolisi\y|bhabinkamtibmas|babinsa|rspal|puspenerbal|pomal|komandan|kodaeral|\ykri\y|tmmd|prajurit|koramil|danramil'),
('sumber',  7, 'Kampus/sekolah',
 'unair|\yits\y|unesa|\yum\y|ubaya|\yumm\y|uinsa|polinema|\ypens\y|\yppns\y|unej|untag|umsida|unusa|\yupn\y|stts|\yuin\y|unitomo|unisma|uwks|ukwms|\yub\y|\yutbk\y|\ysnbp\y|\ysnbt\y|\yprodi\y|universitas|institut|politeknik|poltek|kampus|mahasiswa|dosen|rektor|profesor|guru besar|wisuda|fakultas|alumni|\ykkn\y|\ybbk\y|siswa|pelajar|sekolah|\ysmk|\ysman?\y|\ysmp\y|\ysd\y|madrasah|\ymts\y|\yguru|santri|pesantren|ponpes|\ypaud\y'),
('sumber',  8, 'BUMN/bank/swasta',
 '\ypln\y|\ykai\y|daop|pertamina|telkom|\ybank\y|\ybri\y|\ybni\y|\ybca\y|\ybi\y|\yojk\y|pelindo|jasa tirta|\ypjt\y|\ypgn\y|petrokimia|semen indonesia|\yasdp\y|angkasa pura|bpjs|pegadaian|\ybtn\y|\ybsi\y|\ypt\y|\yperum\y|indosat|astra|\ygrab\y|gojek|kadin|apindo|hipmi|perusahaan|jargas|bulog|pupuk indonesia|ptpn|perhutani|\ylps\y|kereta|\yka\y|jamkrida|\ybumd\y|perumda|perusda|\ypdam\y'),
('sumber',  9, 'Pemerintah pusat',
 'menteri|\ymenko|\y(menkes|mensos|mentan|menpan|menpora|menkeu|menhub|menparekraf|menpar|menkraf|mendag|menperin|menaker|menag|menkomdigi|mendikdasmen|mendikti|mendagri|menlu|menhan|menkop|wamen[a-z]*)\y|kementerian|\ykemen(kes|sos|tan|panrb|pora|keu|hub|parekraf|par|kraf|dag|perin|aker|naker|ag|komdigi|dikdasmen|diktisaintek|dagri|lu|han|kop|kumham|imipas|pu|pkp|desa|investasi|lhk|kp|pppa|bumn|ekraf|ko)\y|presiden|prabowo|wapres|gibran|\ydpr ri\y|\ympr\y|\ydpd\y|\ybpk\y|\ykpk\y|\ybps\y|\ykpu\y|bawaslu|\ybmkg\y|\ybnpb\y|komdigi|\ydjp\y|\ypajak\y|bea cukai|kanwil|\ybpom\y|bp3mi|badan pangan nasional|\ybgn\y|\ybkkbn\y|\yapbn\y|djpb|\ybpn\y|imigrasi|lapas|rutan'),
('sumber', 10, 'Ormas/komunitas',
 '\ynu\y|nahdlatul|muslimat|fatayat|ansor|muhammadiyah|aisyiyah|ldii|\ymui\y|baznas|\ypmi\y|\ypwi\y|\yaji\y|ikatan|himpunan|asosiasi|perhimpunan|\yidi\y|pramuka|karang taruna|komunitas|relawan|yayasan|\ylsm\y|aspikom|\ydwp\y|dharma wanita|\yesi\y|\ykoni\y|organisasi masyarakat|\yormas\y'),
-- Nama kabupaten/kota dicek paling akhir, karena nama kota juga muncul pada
-- berita aktor lain (mis. "KAI Daop 8 Surabaya", "Unair Surabaya").
('sumber', 11, 'Pemkab/Pemkot',
 '\y(pacitan|ponorogo|trenggalek|tulungagung|blitar|kediri|malang|lumajang|jember|banyuwangi|bondowoso|situbondo|probolinggo|pasuruan|sidoarjo|mojokerto|jombang|nganjuk|madiun|magetan|ngawi|bojonegoro|tuban|lamongan|gresik|bangkalan|sampang|pamekasan|sumenep|kota batu|surabaya)\y');

-- A2. TOPIK: berita itu tentang apa
INSERT INTO aturan_klasifikasi (jenis, urutan, label, pola) VALUES
('topik',  1, 'Ekonomi, UMKM & keuangan',
 'umkm|ekonomi|investasi|investor|ekspor|\yimpor\y|inflasi|deflasi|\ypasar\y|harga|koperasi|\yusaha\y|pengusaha|wirausaha|perusahaan|bisnis|\ypajak\y|\ybank\y|kredit|keuangan|pendapatan|\ypad\y|apbd|anggaran|industri|perdagangan|dagang|qris|bumdes|transaksi|rupiah|\yrp ?[0-9]|triliun|miliar|ekraf|\yojk\y|saham|\yutang\y'),
('topik',  2, 'Pangan & pertanian',
 'pangan|\yberas\y|pertanian|petani|panen|\ytanam|\ypadi\y|jagung|pupuk|ternak|peternak|\ysapi\y|\yikan\y|nelayan|perikanan|\ypmk\y|\ymbg\y|makan bergizi|\ygizi\y|sppg|cabai|\ytebu\y|\ykopi\y|bulog|hortikultura|perkebunan|tembakau|\ysusu\y'),
('topik',  3, 'Kesehatan',
 'kesehatan|\ysehat|rumah sakit|\yrsud|\yrs\y|puskesmas|stunting|\ydbd\y|demam|vaksin|imunisasi|penyakit|dokter|pasien|\yobat\y|\yjkn\y|posyandu|\ytbc\y|\yhiv\y|kanker|medis|bidan|perawat|ibu hamil|rspal|khitan|sunat|\yjiwa\y'),
('topik',  4, 'Pendidikan & SDM',
 'pendidikan|sekolah|siswa|kampus|universitas|\yguru|beasiswa|pelatihan|workshop|bimtek|pelajar|santri|pesantren|wisuda|kuliah|\ysdm\y|kompetensi|\yspmb\y|\yppdb\y|sertifikasi|magang|vokasi|\yutbk\y|\ysnbp\y|\ysnbt\y|\yprodi\y|riset|penelitian|peneliti|seminar|kurikulum|perpustakaan'),
('topik',  5, 'Infrastruktur & transportasi',
 'infrastruktur|\yjalan\y|\ytol\y|jembatan|pembangunan|transportasi|kereta|angkutan|mudik|arus balik|lalu lintas|bandara|pelabuhan|irigasi|bendungan|waduk|listrik|air bersih|\ypdam\y|perumahan|rutilahu|\yrtlh\y|drainase|\ydaop|\ykai\y|\ybus\y|penerbangan|\ykapal\y|terminal|stasiun|jargas|gas bumi|energi|\ybbm\y|\ypln\y|kelistrikan'),
('topik',  6, 'Digital & informasi',
 'media sosial|\ymedsos\y'),
('topik',  7, 'Sosial & kemasyarakatan',
 'sosial|bansos|bantuan|kemiskinan|miskin|disabilitas|difabel|lansia|\yanak|perempuan|\ypkk\y|santunan|zakat|baznas|donor|\ypmi\y|warga|masyarakat|keluarga|yatim|pernikahan|kekerasan|ketenagakerjaan|pekerja|buruh|tenaga kerja|pengangguran'),
('topik',  8, 'Budaya, wisata & keagamaan',
 'budaya|wisata|festival|\yseni\y|kesenian|seniman|tradisi|batik|kirab|hari jadi|\yhut\y|ramadan|ramadhan|idul ?fitri|lebaran|idul ?adha|natal|tahun baru|imlek|religi|[sc]h?[ao]lawat|pengajian|masjid|\yhaul\y|wayang|museum|karnaval|reog|pameran|konser|musik|halal ?bi ?halal|\ymtq\y|\ystqh\y|\yhaji\y|umrah|umroh|kurban|qurban'),
('topik',  9, 'Olahraga',
 'olahraga|porprov|pornas|\yliga\y|persebaya|turnamen|kejuaraan|atlet|sepak ?bola|\yvoli|bulu tangkis|badminton|mara?thon|\ylari\y|fun run|\ysenam\y|\ykoni\y|esport|pencak|silat|renang|futsal|basket|proliga'),
('topik', 10, 'Bencana & lingkungan',
 'bencana|banjir|longsor|gempa|kebakaran|erupsi|semeru|kekeringan|lingkungan|sampah|\ysungai|\yhutan|pohon|iklim|cuaca|\ybmkg\y|\ybpbd\y|polusi|mangrove|konservasi|satwa|puting beliung|angin kencang|evakuasi'),
('topik', 11, 'Hukum, keamanan & politik',
 'hukum|korupsi|narkoba|narkotika|keamanan|kamtibmas|pemilu|pilkada|pilkades|politik|partai|\ykpu\y|bawaslu|\yperda\y|raperda|regulasi|pengawasan|patroli|razia|kriminal|penipuan|\ypolisi\y|polda|polres|kejaksaan|kejati|kejari|tersangka|ditangkap|\ytangkap|sidang|pengadilan|unjuk rasa|\yham\y|pencucian uang'),
('topik', 12, 'Penghargaan & prestasi',
 'penghargaan|\yraih|juara|award|prestasi|terbaik|predikat|\ywtp\y|peringkat|medali|anugerah|trofi|rekor'),
('topik', 13, 'Digital & informasi',
 'digital|kominfo|komdigi|literasi|hoaks|\yhoax|siber|internet|aplikasi|teknologi|\yai\y|kecerdasan buatan|\ysmart|informasi|\ymedia\y|\ydata\y|website|\ywifi|cerdig|\yppid\y|statistik|\yspbe\y'),
('topik', 14, 'Pemerintahan & kelembagaan',
 'rapat|\yrakor|koordinasi|sertijab|pelantikan|lantik|audiensi|kunjungan|kunjungi|\ykunker|evaluasi|musrenbang|birokrasi|\yasn\y|pegawai|\ypns\y|pppk|kinerja|program|sinergi|kolaborasi|organisasi|\yapel\y|upacara|pelayanan|layanan|pemerintah|kebijakan|tinjau|monitoring|inovasi|komitmen|kerja ?sama|\ymou\y|nota kesepahaman|reformasi|jabatan');

-- B. Klasifikasi setiap berita ------------------------------------
-- LATERAL: untuk setiap berita, cari aturan pertama (urutan terkecil) yang cocok.
INSERT INTO klasifikasi_berita (id_berita, sumber, topik)
SELECT b.id_berita,
       COALESCE(s.label, 'Belum terkelompok'),
       COALESCE(t.label, 'Belum terkelompok')
FROM berita b
LEFT JOIN LATERAL (
    SELECT a.label FROM aturan_klasifikasi a
    WHERE a.jenis = 'sumber' AND LOWER(b.judul) ~ a.pola
    ORDER BY a.urutan LIMIT 1
) s ON TRUE
LEFT JOIN LATERAL (
    SELECT a.label FROM aturan_klasifikasi a
    WHERE a.jenis = 'topik' AND LOWER(b.judul) ~ a.pola
    ORDER BY a.urutan LIMIT 1
) t ON TRUE;

-- C. Cek hasil: jumlah berita per label --------------------------
SELECT 'sumber' AS jenis, sumber AS label, COUNT(*) AS jumlah
FROM klasifikasi_berita GROUP BY sumber
UNION ALL
SELECT 'topik', topik, COUNT(*)
FROM klasifikasi_berita GROUP BY topik
ORDER BY jenis, jumlah DESC;
