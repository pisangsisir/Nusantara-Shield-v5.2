# Contoh LAPSIT (Laporan Situasi) PDF

Dua berkas ini diekspor langsung dari aplikasi Nusantara Shield **v5.1.3** (commit `d1fbfdc`) pada 29 Oktober 2026,
lewat tombol **Ekspor LAPSIT (PDF)** (`POST /api/lapsit`). Isinya tidak disunting. **Seluruh data sintetis**: nama
layanan bertanda "(contoh)", alamat IP dari blok dokumentasi RFC 5737, dan perintah ke perangkat jaringan masih simulasi.
Waktu di dalam PDF tertulis dalam UTC.

| Berkas | Keadaan saat diekspor | Halaman |
| --- | --- | --- |
| [`contoh-lapsit-kondisi-normal.pdf`](contoh-lapsit-kondisi-normal.pdf) | Laporan rutin sesaat setelah *server* menyala dan Operator masuk: tidak ada insiden dan tidak ada peringatan | 1 |
| [`contoh-lapsit-insiden.pdf`](contoh-lapsit-insiden.pdf) | Setelah tiga latihan: *Akses OT tanpa izin*, *Ransomware* di RS Kesdam lalu isolasi (bukti BB-2026-001 lebih dulu), dan impor `docs/contoh-log/auth.log` | 2 |

Bagian yang selalu ada: **1. Status layanan**, **2. Insiden aktif**, **3. Peringatan terbaru** (dengan teknik MITRE
ATT&CK dan label sumber data), **4. Integritas log audit** (hasil verifikasi rantai HMAC), dan **5. Pengesahan** dua
tanda tangan. Kotak tanda tangan sengaja kosong untuk diisi tangan.

## Membuat ulang

1. Jalankan *server* (lihat README utama), masuk sebagai Operator.
2. Untuk laporan rutin: buka tab **Audit & LAPSIT** → **Ekspor LAPSIT (PDF)**.
3. Untuk laporan insiden: di bilah **Latihan** klik **Akses OT tanpa izin**; pilih target *RS Kesdam · SIMRS (contoh)* →
   **Ransomware** → tahan **EKSEKUSI ISOLASI**; klik **Impor log…** dan pilih `docs/contoh-log/auth.log`; lalu ekspor LAPSIT.

Nomor, jam, dan sidik jari rantai audit akan berbeda di setiap percobaan karena mengikuti waktu dan isi sesi.
