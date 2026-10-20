# Nusantara Shield v5.1

Dasbor pusat operasi keamanan siber (SOC) **defensif** untuk Kartika Cyber Hackathon 2026.
Peladen FastAPI + browser Vanilla JS/Canvas, siaran langsung (SSE), dan jejak audit berantai HMAC.

- Semua data **sintetis**: alamat IP dari blok dokumentasi RFC 5737, nama orang & instansi **fiktif**.
- Berjalan **luring** (tanpa internet): tidak ada CDN, font, atau gambar dari luar.
- Tidak menyimpan data pribadi; log audit tidak menyimpan alamat IP pengunjung.

## Struktur Repositori

```
app/            kode server: FastAPI, dapur situasi, rantai bukti, LAPSIT, AI lokal
static/         dasbor (HTML, CSS, JavaScript polos; tanpa pustaka luar atau CDN)
tests/          196 uji otomatis (pytest), dijalankan dengan ./run_tests.sh
tools/          alat bantu (pengemasan rilis)
docs/           Proposal, Dokumentasi Teknis, Panduan Belajar (PDF), dan diagram alur
presentation/   dek presentasi: index.html (satu berkas mandiri, bisa dibuka luring)
CHANGELOG.md    riwayat versi v1.0 (15 Okt 2026) sampai v5.1 (20 Okt 2026)
```

## Daftar isi

1. [Cara menjalankan](#1-cara-menjalankan)
2. [Akun & peran](#2-akun--peran)
3. [Bagaimana data mengalir](#3-bagaimana-data-mengalir)
4. [Isi dasbor](#4-isi-dasbor)
5. [Doktrin penanganan insiden](#5-doktrin-penanganan-insiden)
6. [Menjalankan uji otomatis](#6-menjalankan-uji-otomatis)
7. [Loket API](#7-loket-api)
8. [Lapisan keamanan](#8-lapisan-keamanan)
9. [Struktur berkas](#9-struktur-berkas)
10. [Catatan data & langkah berikutnya](#10-catatan-data--langkah-berikutnya)

---

## 1. Cara menjalankan

**Prasyarat:** Python 3.10 atau lebih baru.

> **Penting — folder `.venv` tidak ikut repositori/zip.** `.venv` adalah "ruang kerja" Python yang
> dirakit khusus untuk satu komputer (berisi path dan versi Python komputer itu), sehingga pasti rusak
> bila disalin ke komputer lain. Setiap orang membuatnya sendiri dengan langkah 2 di bawah.
> `.venv/` sudah tercantum di `.gitignore`.

### macOS / Linux

```bash
# 1. Masuk ke folder proyek
cd nusantara-shield-v5.1

# 2. Buat ruang kerja Python milik Anda sendiri (sekali saja)
python3 -m venv .venv
source .venv/bin/activate

# 3. Pasang perlengkapan
pip install -r requirements.txt

# 4. Nyalakan peladen
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

### Windows (PowerShell)

```powershell
cd nusantara-shield-v5.1
python -m venv .venv
.venv\Scripts\Activate.ps1          # CMD: .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

Buka **http://127.0.0.1:8000**. Sandi sementara akun bawaan `operator` dan `pengamat` tercetak di
terminal saat peladen menyala. Dua opsi pada perintah uvicorn sengaja dipakai:

- `--no-access-log` — alamat IP pengunjung tidak dicatat (minimisasi data).
- `--no-server-header` — peladen tidak mengumumkan mereknya kepada penyerang.

### Mode permanen (opsional)

Salin `.env.example` menjadi `.env`, isi nilainya, lalu jalankan uvicorn dengan `--env-file .env`
(perlu `pip install python-dotenv`). Dengan `NS_AUDIT_KEY` terisi, log audit, buku rantai bukti, akun
terdaftar, dan nomor laporan tersimpan di folder `data/` dan selamat dari restart.

### Mengemas zip untuk juri / repositori

```bash
python tools/kemas_rilis.py            # → dist/nusantara-shield-v5.1.zip
python tools/kemas_rilis.py --periksa  # hanya menampilkan daftar berkas
```

Alat ini membuang `.venv/`, `data/`, `.env`, cache, dan sampah sistem (`.DS_Store`, `__MACOSX`) —
aturan yang sama dengan `.gitignore`. Hasilnya ±160 KB, bukan ±28 MB.

---

## 2. Akun & peran

| Peran | Boleh | Cara mendapatkan akun |
| --- | --- | --- |
| **Pengamat** | Melihat seluruh dasbor | Bawaan `pengamat`, **atau daftar sendiri** lewat "Buat akun" di halaman masuk |
| **Operator** | Melihat + memicu latihan, isolasi, pemulihan, mengelola akun | Bawaan `operator`, **atau** daftar sendiri dengan **kode undangan** (`NS_KODE_OPERATOR`), **atau** dibuatkan operator lain dari tab **Akun** |

- Nama akun 3–20 karakter (huruf kecil, angka, `_`, diawali huruf); kata sandi minimal 12 karakter dan
  tidak boleh memuat nama akun. Sandi disimpan sebagai hash PBKDF2 (200.000 putaran) + garam acak.
- Tanpa `NS_KODE_OPERATOR`, pendaftaran operator mandiri **tertutup**: akun yang bisa memutus jaringan
  tidak boleh dicetak sendiri oleh siapa pun.
- Pendaftaran dibatasi 5 kali per 5 menit per alamat. `NS_DAFTAR_PENGAMAT=0` menutup pendaftaran pengamat.
- **Tab Akun (khusus operator)** menampilkan jumlah pengamat **terdaftar**, **sedang login**, dan
  **sedang memantau** dasbor (siaran terbuka), diperbarui otomatis tiap 5 detik, plus formulir tambah akun.

---

## 3. Bagaimana data mengalir

Gambar statis (untuk penampil yang tidak mendukung Mermaid): [`docs/alur-data.svg`](docs/alur-data.svg),
[`docs/urutan-insiden.svg`](docs/urutan-insiden.svg).

```mermaid
flowchart TB
    subgraph S1["① Sumber data sintetis"]
        direction LR
        SENSOR["📡 Sensor jaringan<br/>topologi · beban · radar"]
        OSINT["📻 Radio CTI / OSINT<br/>berita ancaman tiap 30 dtk"]
    end

    subgraph S2["② Peladen FastAPI"]
        KORELASI["🔎 Korelasi CTI ⇄ inventaris aset<br/>peluang serangan per aset"]
        DAPUR["🍳 Dapur tunggal<br/>masak gambaran situasi 1×/detik"]
        HUB["📢 Hub siaran SSE<br/>potret utuh sekali, lalu tambalan delta"]
        GERBANG["🛂 Gerbang keamanan<br/>login · peran · batas laju · maks 16 KB"]
        APPROVAL{"✅ Persetujuan & kunci urutan<br/>bukti → isolasi → pulihkan<br/>dilanggar = 409"}
    end

    subgraph S3["③ Browser"]
        DASBOR["🖥️ Dasbor operator & pengamat<br/>peta · radar · Action Center"]
        OPERATOR(["👤 Operator<br/>tahan ⚡ 0,6 dtk<br/>atau darurat 1,5 dtk + alasan"])
    end

    subgraph S4["④ Jejak HMAC berantai"]
        BUKTI[("🔒 Buku Rantai Bukti<br/>SHA-256 barang bukti")]
        LAPSIT["📄 LAPSIT otomatis<br/>IR-2026-001 → manajemen"]
        AUDIT[("📒 Log audit<br/>siapa · apa · kapan")]
    end

    SENSOR --> DAPUR
    OSINT --> KORELASI --> DAPUR
    DAPUR --> HUB -->|"siaran langsung"| DASBOR
    DASBOR --> OPERATOR -->|"POST /api/soar/…"| GERBANG --> APPROVAL
    APPROVAL -->|"1 · amankan bukti"| BUKTI
    APPROVAL -->|"2 · putus jaringan"| DAPUR
    APPROVAL -->|"3 · semua pemutusan tuntas"| LAPSIT
    BUKTI -.->|"dicerminkan"| AUDIT
    LAPSIT -.->|"dicatat"| AUDIT
    APPROVAL -.->|"setiap tindakan"| AUDIT

    classDef sumber fill:#0f2a24,stroke:#3ef0a1,color:#d7e3f2
    classDef peladen fill:#101a2d,stroke:#7aa2d6,color:#d7e3f2
    classDef keputusan fill:#2a2208,stroke:#f2c14e,color:#f6dc9c
    classDef jejak fill:#1a1030,stroke:#b48cff,color:#e6dcff
    class SENSOR,OSINT sumber
    class KORELASI,DAPUR,HUB,GERBANG,DASBOR peladen
    class APPROVAL,OPERATOR keputusan
    class BUKTI,LAPSIT,AUDIT jejak
```

**Cara membacanya:** data dari sensor & radio CTI (①) dimasak SEKALI per detik oleh peladen (②) lalu
disiarkan ke semua layar (③). Ketika operator menekan tombol, perintahnya melewati gerbang keamanan dan
kunci urutan; setiap keputusan meninggalkan jejak di buku-buku berantai HMAC (④) yang tidak bisa diubah
diam-diam.

### Urutan saat insiden ditangani

```mermaid
sequenceDiagram
    autonumber
    actor Op as Operator
    participant UI as Browser
    participant SV as Peladen
    participant BB as Buku Rantai Bukti
    participant LA as Log audit (HMAC)
    participant MJ as Manajemen

    Op->>UI: Tahan ⚡ EKSEKUSI ISOLASI 0,6 detik
    UI->>SV: POST /api/soar/jalankan (isolasi)
    SV->>BB: Salin bukti + SHA-256 + berita acara
    BB-->>LA: Dicerminkan
    alt Bukti berhasil diamankan
        SV->>SV: ±1,2 detik kemudian: putus jaringan
    else Agen forensik gagal
        SV-->>UI: 409 · gunakan isolasi darurat
        Op->>UI: Isi alasan + tahan ⚠ 1,5 detik
        UI->>SV: POST /api/soar/darurat (alasan)
        SV->>BB: Alasan dicatat permanen
        SV->>SV: Putus jaringan seketika
    end
    SV->>MJ: LAPSIT otomatis (rujukan bukti / alasan darurat)
    SV->>LA: Laporan dicatat
    Op->>UI: PULIHKAN
    UI->>SV: POST /api/soar/jalankan (pulihkan)
    SV->>BB: Cocokkan ulang SHA-256 semua barang bukti
    alt Sidik jari cocok
        SV-->>UI: 200 · layanan dipulihkan
    else Tidak cocok
        SV-->>UI: 409 · pemulihan dikunci
    end
```

---

## 4. Isi dasbor

| Bagian | Fungsinya | Analogi |
| --- | --- | --- |
| Executive Overview | Postur AMAN/WASPADA/KRITIS, KPI, sakelar **Peta Global (Makro)** ⇄ **Topologi Internal (Mikro)** | Satelit pemantau & denah markas |
| Peta Ancaman Global | Peta dunia titik-titik; trayektori dari wilayah asal (fiktif) ke markas | Satelit pemantau |
| Radar Anomali | Jarak dari pusat = **zona jaringan**, warna/bentuk = **keparahan**, arah = penanda tetap per alamat IP (**bukan** geografis). Legenda "Cara membaca radar" + tooltip pada titik & cincin | Penjaga malam bersenter |
| Prediksi CTI + AI | Berita ancaman sintetis → korelasi port ke inventaris aset (IT **dan OT**) → peluang serangan; ≥ 50% = waspada proaktif. **AI lokal** (Isolation Forest) menilai lalu lintas tiap aset dan menambah peluang bila tidak wajar, lengkap dengan alasan. Tombol **Latihan OT** menyiarkan kabar Modbus; tombol **Latihan AI** menyuntikkan lalu lintas Modbus tak wajar ke genset | Alarm rumah, radio satpam, & satpam yang hafal suasana normal |
| Action Center | Satu kartu per insiden: status bukti, ⚡ isolasi, isolasi darurat, langkah playbook, ♻ pemulihan | Panel komando |
| Beban Jaringan | Gauge + riwayat 48 detik | Meteran air |
| Aset (triase) | Status 6 layanan contoh; klik untuk laci PIC & Quick Call | Papan triase IGD |
| Log | Peristiwa dari peladen (ringkas 2 baris ⇄ semua) | Rekam gejala pasien |
| Alat operator | Cek indikator, kepatuhan backup, Audit & SITREP PDF, **Akun** (khusus operator) | Pos satpam & buku piket |

---

## 5. Doktrin penanganan insiden

| Aturan | Cara sistem menegakkannya |
| --- | --- |
| **Pre-authorized containment** | Isolasi tidak menunggu izin; tombol ⚡ cukup **ditahan 0,6 detik** (mencegah klik tak sengaja) |
| **Bukti sebelum pemutusan** | Setiap playbook diawali *Amankan bukti*: salinan (simulasi), SHA-256 tiap berkas, berita acara di Buku Rantai Bukti. Pemutusan tanpa bukti ditolak **409** di semua jalur |
| **Isolasi darurat** | Bila bukti gagal diamankan: alasan tertulis (min. 15 karakter) + tahan **1,5 detik**. Alasan tercatat di Buku Rantai Bukti, log audit, dan LAPSIT |
| **LAPSIT otomatis** | Terbit hanya setelah SEMUA tindakan pemutus tuntas; nomor `IR-2026-001` tidak pernah berulang (+ UUID) |
| **Pemulihan terkunci** | Pintu terpisah; terbuka hanya bila aset terisolasi, playbook dicentang, dan SHA-256 bukti **cocok ulang** |
| **Isolasi OT** | Skenario *Sabotase OT*: bukti diamankan, lalu webhook (simulasi) ke sakelar terkelola memutus uplink kantor → zona kendali ± 1,2 detik. Genset **tidak dimatikan**; beralih ke kendali lokal (NIST SP 800-82) |
| **Kamus istilah** | Semua label dari `app/istilah.py` (kini istilah satuan: Dansat, Kasi Siber, TTIS Satuan); mengganti terminologi tidak memecahkan uji |

Latihan kegagalan forensik: centang **"Latih kegagalan agen forensik"** di panel Latihan sebelum memicu skenario.

---

## 6. Menjalankan uji otomatis

```bash
./run_tests.sh              # macOS / Linux  (otomatis memakai .venv bila ada)
run_tests.bat               # Windows
python -m pytest            # cara langsung; pengaturan tampilan ada di pytest.ini
```

Setiap uji dicetak **satu baris beserta hasilnya** (`PASSED`/`FAILED`) dan persentase kemajuan; judul
kelompok muncul setiap kali pytest pindah bagian, dan di akhir tampil ringkasan + 5 uji paling lambat.
Contoh memilih sebagian: `./run_tests.sh -k akun`, `./run_tests.sh tests/test_rantai_bukti.py`,
`./run_tests.sh --lf` (ulangi yang gagal). **Jangan memakai `-q`** — opsi itu menyembunyikan nama uji.

**Total: 196 uji** dalam 9 kelompok.

**Keamanan & akses** — `tests/test_keamanan.py` (38 uji)
- Semua loket menolak permintaan tanpa login; token palsu & sandi salah ditolak; logout mencabut token
- Pengamat tidak bisa mengubah data; tebak sandi dibatasi 5×/menit
- Input aneh & indikator tidak valid ditolak; kiriman > 16 KB ditolak sebelum mencapai router (termasuk *chunked*)
- Header keamanan terpasang (juga pada penolakan); dokumentasi API dimatikan; CORS menolak situs asing
- Log audit menyimpan data seminimal mungkin dan mendeteksi manipulasi; SITREP PDF terbentuk

**Manajemen akun** — `tests/test_akun.py` (18 uji)
- Pengamat bisa daftar sendiri lalu login, tetapi hanya bisa melihat
- Operator tanpa kode undangan / dengan kode salah ditolak; dengan kode sah bisa bertindak
- Validasi nama & sandi; nama ganda dan kolom asing ditolak; pendaftaran dibatasi laju
- Dasbor operator menghitung pengamat terdaftar / login / memantau; pengamat tidak bisa melihatnya
- Sandi tidak pernah tercatat di log maupun berkas; akun terdaftar bisa dimuat ulang setelah restart

**Telemetri & siaran** — `tests/test_telemetri.py` (19 uji)
- DDoS menggerakkan semua panel; langkah playbook memutus kabel di peta & radar; kronologi diteteskan bertahap
- Siaran menutup diri saat logout; jumlah siaran per akun dibatasi
- Satu dapur: biaya tidak bertambah dengan jumlah layar; dapur tetap hidup walau satu masakan gagal
- Tambalan delta: layar yang merakit tambalan selalu identik dengan peladen, dan tambalan jauh lebih kecil

**Intelijen ancaman & SOAR** — `tests/test_cti_soar.py` (18 uji)
- Berita relevan menaikkan aset ke waspada sebelum serangan; berita tak relevan hanya dicatat; berita memudar
- Pengerasan menurunkan peluang; peringatan dini terbukti
- SOAR memutus kabel & memotong beban seketika; isolasi bertahap lalu pemulihan lewat pintu terpisah
- Peta global selalu sinkron dengan topologi

**Sinergi IT/OT** — `tests/test_ot.py` (6 uji)
- Pengendali genset (Modbus/TCP, port 502) terdaftar di topologi (zona kendali), radar, dan profil Kendali Fasilitas
- Kabar ancaman Modbus menaikkan genset ke waspada (± 66%) sebelum ada serangan
- Perketat menurunkan peluang genset di bawah ambang
- Kabar OT tidak memicu aset IT, dan sebaliknya (tidak ada alarm palsu)
- Sabotase OT: bukti dulu, lalu webhook (simulasi) ke sakelar terkelola memutus uplink kantor → zona kendali ± 1,2 detik; genset tetap menyala (kendali lokal)
- Pemulihan jalur kendali terkunci bila sidik jari bukti tidak cocok

**AI lokal: deteksi anomali** — `tests/test_ai.py` (10 uji)
- Model Isolation Forest dilatih di server ini dengan benih tetap (hasil sama setiap menyala, dapat diaudit)
- Lalu lintas wajar tidak memicu alarm palsu; lalu lintas Modbus tak wajar menaikkan genset ke waspada tanpa kabar CTI
- Setiap deteksi disertai alasan ("perintah tulis Modbus 10× normal"); skor AI digabung dengan CTI: 1 − (1 − p_CTI)(1 − p_AI)
- Perketat menurunkan peluang AI di bawah ambang; latihan berakhir → lalu lintas dicatat kembali wajar
- Penilaian 9 aset dalam milidetik dan disimpan per keadaan; berjalan tanpa satu pun koneksi jaringan
- Hanya operator yang boleh menjalankan latihan AI; aset dalam insiden tetap diurus playbook

**Rantai komando & laporan** — `tests/test_komando.py` (22 uji)
- Isolasi tanpa menunggu izin; LAPSIT terkirim otomatis dengan keparahan & nomor berurutan
- Laporan hanya terbit setelah SEMUA pemutus selesai, tepat satu kali (juga bila manual)
- Pemulihan terkunci sampai terisolasi & playbook dicentang; Quick Call ke admin cabang
- Nomor laporan tidak berulang setelah reset maupun restart

**Rantai bukti forensik** — `tests/test_rantai_bukti.py` (36 uji, termasuk skenario Sabotase OT)
- Setiap playbook diawali *Amankan bukti*; isolasi standar mengamankan bukti sebelum memutus
- Semua jalan pintas (aksi tunggal, centang manual, antrean disusupkan) ditolak 409 tanpa bukti
- Isolasi darurat menolak alasan kosong; alasannya terikat ke buku bukti, log audit, dan LAPSIT
- Bukti atau berita acara yang dirusak → pemulihan dikunci di semua pintu

**Kamus istilah** — `tests/test_istilah.py` (29 uji)
- Tidak ada label yang tertanam di luar `app/istilah.py`; playbook dirakit dari kamus

---

## 7. Loket API

Semua loket di bawah `/api/` wajib login kecuali yang ditandai *publik*. Loket yang mengubah data
dibatasi lajunya dan dicatat di log audit.

| Loket | Peran | Fungsi |
| --- | --- | --- |
| `POST /api/login` · `POST /api/logout` | publik · semua | Masuk (token 8 jam) / keluar |
| `POST /api/akun/daftar` | publik | Daftar mandiri `{nama, sandi, peran, kode_operator?}` |
| `POST /api/akun` | operator | Operator membuat akun `{nama, sandi, peran}` |
| `GET /api/akun/ringkasan` | operator | Jumlah & daftar akun (terdaftar / login / memantau) |
| `GET /api/telemetri` · `GET /api/telemetri/siaran` | semua | Potret situasi · siaran langsung SSE (tambalan delta) |
| `POST /api/simulasi` | operator | Picu latihan `{layanan_id, skenario, gangguan_bukti?}` |
| `POST /api/soar/jalankan` | operator | `aksi` = `isolasi` · `pulihkan` · `amankan_bukti` · id tindakan |
| `POST /api/soar/darurat` | operator | Isolasi darurat `{layanan_id, alasan}` |
| `POST /api/soar/perketat` | operator | Pengerasan proaktif aset `{aset_id}` |
| `POST /api/ai/latihan` | operator | Latihan AI lokal: suntik pola lalu lintas tak wajar `{aset_id, pola?}` (data sintetis) |
| `POST /api/playbook/langkah` · `POST /api/pulihkan` | operator | Centang langkah · tutup insiden |
| `POST /api/cti/siarkan` | operator | Siarkan berita CTI sekarang (`NS_CTI_JEDA`, bawaan 30 dtk) |
| `POST /api/komando/panggil` | operator | Quick Call ke PIC cabang (simulasi) |
| `GET /api/bukti` | semua | Buku Rantai Bukti + verifikasi rantai |
| `GET /api/audit` · `GET /api/audit/verifikasi` | semua | Log audit + verifikasi rantai |
| `POST /api/sitrep` | semua | Ekspor SITREP PDF |
| `POST /api/indikator/cari`, `/api/backup/catat`, `/api/demo/majukan-waktu`, `/api/reset-demo` | campuran | Alat operator |
| `GET /api/health` · `GET /api/istilah` | publik | Status minimal · kamus label |

---

## 8. Lapisan keamanan

| Syarat | Penerapan | Berkas |
| --- | --- | --- |
| Autentikasi | Token acak 8 jam; peladen hanya menyimpan hash token; sandi PBKDF2 200.000 putaran | `app/keamanan.py` |
| Otorisasi | Peran `pengamat` (lihat) dan `operator` (lihat, ubah, kelola akun) | `app/keamanan.py` |
| Pendaftaran aman | Operator hanya dengan kode undangan atau oleh operator; pembatasan laju | `app/keamanan.py`, `app/main.py` |
| Batas laju | Login 5/menit, daftar 5/5 menit, ubah 30/menit, PDF 5/menit, baca 120/menit | `app/keamanan.py` |
| Batas ukuran | Kiriman > 16 KB ditolak di middleware ASGI sebelum router | `app/keamanan.py` |
| Header keamanan | CSP ketat, nosniff, anti-iframe, no-referrer, HSTS bila HTTPS | `app/keamanan.py` |
| Validasi input | Pydantic `extra="forbid"`, daftar nilai tetap, batas panjang | `app/main.py` |
| Anti-XSS | Semua teks dipasang via `textContent` | `static/app.js` |
| Jejak audit | Dua buku berantai HMAC-SHA256 (log audit & Buku Rantai Bukti) | `app/audit.py`, `app/bukti.py` |
| Siaran aman | Token di header (bukan URL), diperiksa ulang tiap 2 detik; maks 4 siaran/akun | `app/main.py` |

Batas yang perlu diketahui: peladen berjalan sebagai **satu proses** (Hub siaran ada di memori proses itu).

---

## 9. Struktur berkas

```
app/main.py           loket-loket API
app/keamanan.py       akun, pendaftaran, token, peran, batas laju, middleware
app/audit.py          buku berantai HMAC (dipakai log audit & Buku Rantai Bukti)
app/bukti.py          brankas bukti, SHA-256, berita acara
app/telemetri.py      "dapur": topologi, dampak skenario, SOAR, radar, CTI, kunci urutan
app/ai_anomali.py     AI lokal: Isolation Forest (scikit-learn), dilatih & dijalankan di server ini
app/siaran.py         Hub siaran tunggal
app/delta.py          tambalan delta untuk siaran
app/istilah.py        kamus label (satu-satunya sumber istilah)
app/penomoran.py      nomor laporan & berita acara yang tidak pernah berulang
app/data_contoh.py    data sintetis, skenario, playbook
app/sitrep.py         pembuat PDF
static/index.html     kerangka dasbor
static/app.js         login & pendaftaran, siaran, semua panel, alat operator
static/radar.js       Radar Anomali (Canvas)
static/peta.js        Peta Ancaman Global (Canvas)
static/penjadwal.js   satu mesin animasi berbasis visibilitas
static/style.css      tema gelap + aksen hijau neon
docs/                 diagram alur (sumber Mermaid + SVG)
tests/                196 uji otomatis (lihat bagian 6)
tools/kemas_rilis.py  pembuat zip rilis bersih
tools/buat_peta.mjs   pembuat titik peta dunia (sekali pakai)
run_tests.sh / .bat   menjalankan uji dengan umpan balik per uji
pytest.ini            pengaturan tampilan pytest
```

---

## 10. Catatan data & langkah berikutnya

- IP memakai blok dokumentasi RFC 5737, domain `.example`/`.test` (RFC 2606); hash contoh = berkas uji **EICAR**.
- Titik daratan peta dibuat SEKALI oleh `tools/buat_peta.mjs` dari Natural Earth (domain publik). Wilayah asal
  serangan di peta **fiktif**, bukan atribusi pelaku sungguhan.
- Pengambilan bukti forensik adalah **simulasi**: isi "berkas" dibangkitkan acak agar sidik jarinya unik dan
  bisa diverifikasi; tidak ada memori atau log sungguhan yang disalin.

**Langkah berikutnya (setelah lomba):**
1. Ganti data contoh dengan umpan indikator resmi (misalnya dari BSSN atau komunitas MISP).
2. Simpan status di basis data; Hub siaran di perantara pesan bersama agar bisa lebih dari satu proses.
3. Login lewat sistem identitas instansi (SSO) dengan verifikasi dua langkah.
4. Jalankan di belakang HTTPS (`NS_HTTPS=1`).
5. **Engine Deteksi Anomali (AI lokal) sudah berjalan** (`app/ai_anomali.py`). Yang masih **rencana**: Engine Asisten
   Narasi (LLM lokal, mis. Llama 3 lewat Ollama) untuk draf LAPSIT, serta otomasi alur kerja (n8n).
   Ciri lalu lintas AI di purwarupa masih sintetis; penerapan nyata mengambilnya dari sensor satuan (Wazuh, Suricata, Zeek).
6. Perluasan OT: sensor protokol industri (Modbus/DNP3) dan webhook ke sakelar terkelola **sungguhan**
   (di purwarupa, perintah sakelar masih simulasi) — **rencana**.
