# Riwayat Perubahan — Nusantara Shield

Seluruh kode dikembangkan sejak **15 Oktober 2026**, setelah publikasi program Kartika Cyber Hackathon 2026 (12 Oktober 2026), sesuai Deklarasi pasal 5.3 di Proposal. Repositori Git ini dimulai pada **20 Oktober 2026**; riwayat sebelumnya disusun dari folder versi dan folder cadangan per fase yang tersimpan di laptop pengembang (beserta catatan `BACA-SAYA.txt`), bukan dari commit.

## v5.1 — 15–23 Oktober 2026

### Tata posko 24 jam — 23 Oktober 2026 (branch `feature/ui-posko-24jam`)
- **Rel keputusan** di kanan layar (≥ 1280 px), lengket saat digulir: Action Center → Prediksi CTI + AI → Log. Di monitor 1920×1080, tombol Eksekusi Isolasi kini terlihat tanpa menggulir (sebelumnya di bawah lipatan layar, y ≈ 1.076 px). Insiden baru mengembalikan rel ke Action Center.
- Layar sempit: satu kolom; selama ada insiden yang belum diisolasi, Action Center naik ke paling atas.
- Gerak hanya untuk yang tidak normal: arus topologi normal diam (redup), hanya arus waspada/kritis yang bergerak; kedip keras 1 Hz diganti denyut lembut 2,4 dtk; tombol Isolasi tidak lagi berdenyut tanpa henti. Animasi tak henti saat tenang: 13 → 2.
- Satu skala warna keparahan: warna yang ditulis langsung (#ff9a6b, #ff9f5a, #c9d36b, #8fe3b4) menjadi token; peluang "sedang" (di bawah ambang) netral, kuning disimpan untuk WASPADA; kartu prediksi WASPADA disorot.
- Kontras: `--teks-samar` 3,0–3,5:1 → ≥ 4,6:1 (WCAG AA); pendar dekoratif (latar, logo, judul panel, panel kritis, meteran) dihapus; huruf label minimum ±10,5 px.
- Panduan radar dilipat bawaan; Action Center saat SIAGA cukup satu baris.
- Hanya `static/` (HTML, CSS, 3 baris JS); backend tidak berubah; 224 uji tetap lulus.

### Kesiapan Siber dan triase — 22 Oktober 2026 (branch `feature/kesiapan-dan-triase`)
- Kartu **Nilai Kesiapan Siber** A–E di Executive Overview: dua sub-skor (Kerawanan, Insiden) per layanan, nilai posko tertimbang jumlah aset; rumus terbuka di `app/telemetri.py` dan Dokumentasi Teknis §2.5.
- **Triase peringatan**: Operator menutup peringatan WASPADA sebagai Selesai ditangani atau Positif Palsu (*False Positive*) dengan alasan tertulis (`POST /api/peringatan/tutup`). Penutupan menjadi halaman `PERINGATAN_DITUTUP` di Buku Rantai Bukti; tidak ada yang dihapus, dan bukti baru membuka peringatan lagi.
- 16 uji baru (+4 uji kamus untuk label baru); total 224 uji dalam 11 kelompok.

### Penajaman narasi — 22 Oktober 2026 (branch `docs/penajaman-narasi`)
- "Dua kunci konfirmasi" ditulis eksplisit di Proposal, Dokumentasi Teknis, dan dek: CTI dan AI lokal hanya menaikkan WASPADA; isolasi hanya bisa diperintahkan Operator (Pengamat ditolak 403, dikunci uji yang sudah ada).
- Pelajaran PDNS 2024 dikaitkan ke Mode Berdaulat: inti pertahanan berjalan di posko sendiri, tidak bergantung pada pusat data atau awan.
- Dokumentasi Teknis: daftar komponen (FastAPI, scikit-learn, HMAC-SHA256 bawaan Python) dan subbab 1.4 Data Latihan Sintetis (RFC 5737, RFC 2606, EICAR).
- Rujukan ISO/IEC 27037:2012 ("mengikuti prinsip", belum diaudit) di Proposal, Dokumentasi Teknis, dan Panduan; kotak Batasan Penggunaan (UU ITE, UU PDP) di Panduan.
- Tanpa perubahan kode; 204 uji tetap lulus.

### Paket pasang luring — 22 Oktober 2026
- `tools/kemas_luring.py` membundel kode dan semua pustaka (`pip download`) beserta daftar sidik jari `SHA256SUMS`; `pasang_luring.py` memeriksa sidik jari lalu memasang dengan `pip install --no-index`, tanpa internet.
- 8 uji baru; total 204 uji.

### Narasi penangkalan — 22 Oktober 2026
- Alur cerita dokumen dan dek dibuka dengan peringatan dini (CTI + AI lokal → WASPADA → Perketat), lalu isolasi ±1,2 detik bila ancaman tetap tembus.

### Finalisasi hackathon — 20 Oktober 2026 (branch `feature/finalisasi-hackathon`)
- Skrip pembuatan ulang `.venv` setelah folder proyek dipindah (`tools/perbaiki_venv.sh`).
- Nama enam aset contoh disesuaikan dengan konteks RS dan markas TNI AD; ID, IP, *port*, dan logika deteksi tidak berubah.
- Istilah SITREP diganti LAPSIT di kode dan antarmuka: `app/sitrep.py` → `app/lapsit.py`, rute `/api/sitrep` → `/api/lapsit`. Kata "peladen" diganti *server*.
- Dokumen: penyisiran PUEBI, tabel status fitur (sudah berjalan vs peta jalan), dua pilar AI (Engine Deteksi Anomali berjalan; Engine Asisten Narasi Llama 3 8B masih peta jalan).

### AI lokal — 20 Oktober 2026
- Engine Deteksi Anomali: *Isolation Forest* (scikit-learn), dilatih dan dijalankan luring di *server*; skornya digabung dengan peluang CTI; disertai alasan yang bisa dibaca.
- 10 uji khusus AI; total 196 uji.

### Fase 7 — 20 Oktober 2026
- Aset rumah sakit, skenario Sabotase OT (isolasi jalur kantor → zona kendali), istilah satuan.

### Fase 6 — 20 Oktober 2026
- Aset OT pertama: pengendali genset (Modbus/TCP, *port* 502); uji OT (`tests/test_ot.py`).

### Fase 5 — 18 Oktober 2026
- Tujuh perbaikan hasil audit; manajemen akun (`tests/test_akun.py`).
- `docs/` (diagram alur), `pytest.ini`, `run_tests.sh`/`run_tests.bat`, `tools/kemas_rilis.py`.

### Fase 4 — 18 Oktober 2026
- Rantai bukti forensik: `app/bukti.py`, sidik jari SHA-256, Buku Rantai Bukti HMAC; `tests/test_rantai_bukti.py`.

### Fase 3 — 17 Oktober 2026
- Siaran ralat (delta) `app/delta.py` dan penjadwal layar `static/penjadwal.js`: CPU *server* 10,8% → 2,8% dan lalu lintas −80% untuk 300 layar.

### Fase 2 — 17 Oktober 2026
- Pembaruan *server*, keamanan, dan telemetri beserta ujinya.

### Fase 1 — 16 Oktober 2026
- Penyesuaian istilah dari korporat ke istilah Pussiber AD (kamus istilah).

## v5.0 — 16 Oktober 2026
- Penyempurnaan *server*, dasbor, dan uji (CTI/SOAR, komando, telemetri).

## v4.0 — 16 Oktober 2026
- Rantai komando dan laporan (`tests/test_komando.py`).

## v3.0 — 16 Oktober 2026
- Peta Global (`static/peta.js`), korelasi CTI dan SOAR (`tests/test_cti_soar.py`).

## v2.0 — 16 Oktober 2026
- Arsitektur klien–*server*: dapur situasi (`app/telemetri.py`), Radar Anomali (`static/radar.js`), siaran langsung SSE; `tests/test_telemetri.py`.

## v1.0 — 15 Oktober 2026
- *Server* FastAPI, dasbor awal, login dan peran (`app/keamanan.py`), log audit berantai HMAC (`app/audit.py`), ekspor laporan situasi ke PDF, data contoh sintetis; `tests/test_keamanan.py`.
