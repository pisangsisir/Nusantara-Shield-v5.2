# Riwayat Perubahan — Nusantara Shield

Seluruh kode dikembangkan sejak **15 Oktober 2026**, setelah publikasi program Kartika Cyber Hackathon 2026 (12 Oktober 2026), sesuai Deklarasi pasal 5.3 di Proposal. Repositori Git ini dimulai pada **20 Oktober 2026**; riwayat sebelumnya disusun dari folder versi dan folder cadangan per fase yang tersimpan di laptop pengembang (beserta catatan `BACA-SAYA.txt`), bukan dari commit.

## v5.1 — 15–20 Oktober 2026

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
