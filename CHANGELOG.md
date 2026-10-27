# Riwayat Perubahan — Nusantara Shield

Seluruh kode dikembangkan sejak **15 Oktober 2026**, setelah publikasi program Kartika Cyber Hackathon 2026 (12 Oktober 2026), sesuai Deklarasi di Proposal §6.1 (Rulebook bagian G). Repositori Git ini dimulai pada **20 Oktober 2026**; riwayat sebelumnya disusun dari folder versi dan folder cadangan per fase yang tersimpan di laptop pengembang (beserta catatan `BACA-SAYA.txt`), bukan dari commit.

## v5.1 — 15–27 Oktober 2026

### Spanduk halaman depan — 27 Oktober 2026 (branch `docs/banner-readme`)
- README dibuka dengan spanduk lebar: simbol, nama, tiga kata kerja Penangkalan, dan keterangan lomba. Disertakan juga `social-preview.png` (1280 × 640) untuk pratinjau tautan GitHub.

### Logo resmi dan penyesuaian Rulebook — 27 Oktober 2026 (branch `docs/rulebook-logo-v2`)
- **Logo Nusantara Shield** menggantikan logo generik di dasbor (beserta favicon), dek presentasi, dan poster: perisai, Merah Putih 3:2, radar dua cincin, Nusantara, dan ancaman yang terkunci di perimeter. Berkas, makna, dan aturan pemakaian ada di `docs/logo/`. Poster kini mengambil logo langsung dari `docs/logo/simbol.svg`.
- **Rujukan aturan** di Proposal, Dokumentasi Teknis, dan riwayat ini diganti dari "pasal 5.3/5.4 Syarat dan Ketentuan" ke **Rulebook bagian G (Ketentuan Karya)**, karena Rulebook terbaru tidak lagi memakai nomor pasal. Isi deklarasi tidak berubah.
- **Atribusi** ditambah Gemini (eksplorasi awal konsep logo) dan huruf Inter (OFL) untuk logo horizontal.
- **Dek:** slide Lampiran kini memuat tautan ke repositori dan folder `docs/`, karena dokumentasi teknis tidak lagi diserahkan sebagai berkas terpisah tetapi tetap dinilai.

### Susunan tim di Proposal — 26 Oktober 2026 (branch `docs/nama-tim`)
- Baris **Tim** di Proposal diisi: Muhammad Isa Ananta · Hasan Basri · Melia Fajar Hasanah (sebelumnya masih *placeholder*).

### Tata letak penuh: tanpa ruang kosong di monitor posko — 26 Oktober 2026 (branch `feature/tata-letak-penuh`)
- **Baris Radar | Aset | Beban disamakan tingginya.** Ruang kosong di dalam panel turun dari ±300–580 px menjadi 1 px (diukur di 1440, 1920, dan 2880 px). Ruang lebih dipakai isi: kartu aset merata, dan linimasa 60 menit membesar dengan garis ambang waspada/kritis yang diambil dari *server*.
- **Peringatan terbaru menjadi tabel lebar penuh**: keparahan, peringatan, aset, status, waktu, satu baris per peringatan. Di ponsel, tabel berubah menjadi kartu bertumpuk.
- **Latihan menjadi satu bilah alat mendatar** (target, 4 skenario, latihan deteksi).
- **Pita anomali AI** dibatasi 3 (yang berlangsung lebih dulu), dengan tombol "+N aset lainnya".
- **Rel keputusan setinggi layar.** Log mengisi sisa ruang dan digulir di dalam, sehingga ±880 px kosong di bawah rel (1920 px) hilang. Mode ringkas Log kini memotong tiap entri menjadi 2 baris, bukan menyembunyikannya.
- **Executive Overview:** Postur dan Kesiapan ditumpuk di kiri, 6 KPI (3 × 2) di kanan, sehingga tidak ada kartu setengah kosong.
- **Monitor 1280–1679 px:** Radar dan Aset berdampingan, Beban Jaringan selebar baris (meteran di kiri, linimasa di kanan).
- **Layar sangat lebar atau di-*zoom out*:** isi melebar sampai 2.400 px, dan bilah judul berbagi tepi yang sama dengan isi.
- Hanya HTML, CSS, dan JavaScript tampilan; logika *server* tidak berubah. 254 uji lulus. Tanpa galat konsol. Ponsel 390 px tanpa gulir samping. Tombol latihan tetap nonaktif untuk Pengamat.
- README dan Panduan (PDF serta Claude Docs) diperbarui untuk letak Peringatan terbaru yang baru.

### Dokumentasi akhir: tiga kata kerja, deteksi, linimasa, angka terukur ulang — 26 Oktober 2026 (branch `docs/deteksi-linimasa-tiga-kata-kerja`)
- Paragraf pembuka Proposal, Dokumentasi Teknis, README, dek, poster, dan Panduan kini menempatkan Nusantara Shield sebagai perisai pertahanan (*Defensive Shield*) dengan tiga kata kerja: **mendeteksi**, **mencegah**, dan **membantu merespons**. Respons ditulis "otomatis setelah satu keputusan Operator", dengan catatan bahwa perintah ke perangkat masih simulasi.
- Engine Deteksi Aturan didokumentasikan dengan ambang yang dikunci uji (8 gagal/60 dtk, tembus ≤ 120 dtk, 15 kombinasi/10 dtk, aktif 300 dtk), di Dokumentasi Teknis §2.8 yang baru dan Panduan Bab 7. Ikut didokumentasikan: linimasa 60 menit berlabel data latihan, pita anomali AI, serta KPI MTTC dan insiden.
- Jumlah uji 224 → **254** di semua dokumen; cuplikan terminal dari keluaran asli (`254 passed in 33.82s`).
- CPU: angka versi akhir **±1,5% siaga, ±1,7% serangan** untuk 300 layar (`tools/ukur_beban.py`, Linux 2 inti). Angka 10,8% → 2,8% tetap dicatat sebagai riwayat optimasi siaran ralat (17 Okt), dengan keterangan bahwa alat dan mesinnya berbeda, sehingga tidak dibandingkan langsung.
- NIST CSF: DE.CM dan DE.AE kini memuat aturan deteksi; peristiwa identitas nyata dari Active Directory tetap peta jalan.
- Peta jalan baru: **respons bertingkat menurut kritikalitas aset**. Aset vital tetap dua kunci; *endpoint* kantor berisiko rendah dapat diisolasi otomatis dengan *playbook* praotorisasi.
- Poster dan PDF Panduan dibangun ulang; tanpa perubahan kode aplikasi.

### Linimasa 60 menit, pita anomali AI, dan KPI posko — 26 Oktober 2026 (branch `feature/timeline-ai-kpi`)
- Panel Beban Jaringan: grafik 48 detik diganti **linimasa 60 menit** (60 titik × 1 menit, ditambah menit berjalan) berlabel **"data latihan"**. Saat posko baru dibuka, 60 menit sebelumnya diisi data latihan bangkitan berbenih tetap (batang redup, tanpa insiden dan tanpa anomali karangan); setiap 60 detik beban posko yang sebenarnya menjadi satu titik baru. Menit yang memuat insiden diberi tanda merah.
- **Pita anomali AI per aset** di bawah linimasa: nama aset, lama anomali, alasan dari model, dan penanda "berlangsung". Pita hanya lahir dari penilaian AI di sesi ini. Klik pita untuk menyorot aset itu di topologi.
- KPI baru: **Waktu respons (MTTC)**, yaitu rata-rata dari insiden dimulai sampai langkah penahanan selesai, dan **Insiden sejak posko aktif**. Keduanya dihitung dari kejadian yang tercatat, lalu dimulai ulang saat demo diatur ulang.
- `tools/ukur_beban.py` (baru): pengukur beban yang dapat diulang. Alat ini menyalakan *server*, membuka N siaran SSE sungguhan, lalu mencatat waktu CPU proses *server*. Hasil untuk 300 layar di Linux 2 inti (Python 3.13), metode dan mesin sama: sebelum PR ini 1,43% (tenang) dan 1,60% (serangan); sesudahnya **1,47%** dan **1,67%**, dengan 300/300 siaran tetap hidup. Lalu lintas siaran naik dari 0,25–0,33 menjadi 0,28–0,40 MB/s karena linimasa ikut dikirim sekali per menit. Angka 2,8% di dokumen lama diukur dengan skrip yang tidak tersimpan di repositori, jadi tidak dibandingkan langsung.
- 6 uji baru (`tests/test_linimasa.py`); 254 uji lulus.

### Engine deteksi aturan: login gagal berulang dan pemindaian port — 26 Oktober 2026 (branch `feature/deteksi-login-portscan`)
- `app/deteksi.py` (baru): aturan deteksi **sungguhan** yang membaca peristiwa mentah sintetis (percobaan login, koneksi masuk), bukan baris log yang disuntikkan. Ambang terbuka di kode: **≥ 8 login gagal dari satu IP dalam 60 dtk** (sedang); **login berhasil ≤ 120 dtk setelah rentetan itu** (tinggi); **≥ 15 kombinasi aset:port berbeda dari satu IP dalam 10 dtk** (tinggi). Temuan aktif 300 dtk sejak peristiwa terakhir; rentetan yang berlanjut tidak menggandakan temuan.
- Temuan menjadi sumber ketiga prediksi (`DET-…`) di samping CTI dan AI, digabung dengan noisy-OR yang sama. Dua kunci tidak berubah: deteksi hanya menaikkan aset ke WASPADA; isolasi tetap keputusan Operator. Perketat memotong sumbangannya; triase dapat menutupnya. Aset yang sedang ditangani *playbook* insiden tidak dinilai ulang dan diberi label jujur "Aset ditangani lewat playbook insiden".
- Panel **Peringatan terbaru**: label status diambil dari data sebenarnya, misalnya "Diisolasi oleh operator · bukti BB-2026-001" (nama Operator dan nomor berita acara bukti yang tercatat), bukan teks tetap.
- Latihan deteksi (Operator saja): `POST /api/deteksi/latihan` memutar rangkaian peristiwa sintetis berlabel (IP dokumentasi RFC 5737); tercatat di log audit.
- 24 uji baru (`tests/test_deteksi.py`), termasuk uji yang mengunci ambang terdokumentasi dan uji waktu (gagal ke-7 belum, ke-8 terdeteksi). Uji mutasi: mengubah ambang kini menggagalkan 3 uji. 248 uji lulus.

### Sistem pendukung keputusan, NIST CSF 2.0, dan keamanan posko — 26 Oktober 2026 (branch `docs/spk-nist-keamanan-posko`)
- Pembingkaian **sistem pendukung keputusan (SPK)** di Proposal, Dokumentasi Teknis, dek, dan Panduan: mesin mempercepat, manusia memutuskan. Alasan sengaja **tidak** otonom penuh dituliskan: peringatan keliru yang memutus layanan sendiri, respons yang dapat dipancing pihak luar, dan pemutusan tanpa pejabat yang bertanggung jawab.
- Dokumentasi Teknis §2.6: pemetaan fitur ke **NIST CSF 2.0** (CSWP 29) per kategori, dengan status (berjalan, simulasi, peta jalan) dan berkas uji yang membuktikannya. Pemetaan mandiri, bukan sertifikasi.
- Dokumentasi Teknis §2.7: **keamanan posko itu sendiri**, berupa tabel ancaman → pengamanan → uji, beserta batasnya (HTTPS lewat *proxy* balik, sesi di memori, belum ada verifikasi dua langkah, belum ada uji penetrasi independen, syarat saat tersambung ke perangkat nyata).
- Peta jalan: pemantauan peristiwa identitas (Active Directory) dan pengamanan integrasi nyata (brankas kredensial, hak minimum per *playbook*, *playbook* bertanda tangan, persetujuan dua orang).
- `docs/poster/`: poster satu halaman A4 (HTML, PDF, PNG); setiap butir berlabel BERJALAN, SIMULASI, atau PETA JALAN. Bendera Merah Putih, ikon Lucide (ISC) sebagai SVG sebaris pada metrik, alur, enam fungsi CSF, dan jenis aset, ilustrasi jaringan abstrak, baris format laporan siap lapor (bahan pelaporan ke BSSN dan UU PDP; belum diaudit kepatuhan), dan peta jalan "Integrasi Direktori Aktif (IAM) & Pemantauan Login". Sumber dan pembangkitnya di `docs/poster/sumber/`.
- Tanpa perubahan kode aplikasi; 224 uji lulus.

### Perbaikan uji paket lintas-OS — 26 Oktober 2026 (branch `fix/uji-paket-lintas-os`)
- `test_kebutuhan_lintas_sistem_operasi_disesuaikan_target` kini memakai `requirements.txt` contohnya sendiri. Sebelumnya uji membaca berkas di folder tempat ia dijalankan, sehingga **gagal di dalam paket luring lintas-OS** (misalnya paket Mac yang dibuat di Linux), karena di sana `uvicorn[standard]` memang sengaja diganti `uvicorn` polos. Ditemukan saat paket Mac dipasang langsung di Mac.
- Zip dibangun dari salinan kerja yang izin berkasnya sudah dinormalkan (644/755). Sebelumnya 9 berkas berizin baca-saja (444) ikut terbawa ke zip; di Mac (`ditto`/Finder) izin itu dipertahankan dan membuat satu uji gagal menulis `requirements.txt`.
- Tanpa perubahan kode aplikasi; 224 uji lulus.

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
