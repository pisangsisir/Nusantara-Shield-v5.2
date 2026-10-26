# Sumber poster

`poster-nusantara-shield.html` di folder atas **dibangkitkan** dari `poster_templat.html` oleh `bangun_poster.py`.
Ikon Lucide (v0.460.0, lisensi ISC) disalin ke dalam HTML sebagai *sprite* SVG sebaris, sehingga poster tetap luring.

```bash
npm install lucide-static@0.460.0            # sekali saja, butuh internet
python3 bangun_poster.py node_modules/lucide-static/icons ../poster-nusantara-shield.html
```

Cetak ke PDF dari Chrome: Cetak → Simpan sebagai PDF, kertas A4, margin Tidak ada, centang Grafis latar.
Setiap butir di poster wajib berlabel BERJALAN, SIMULASI, atau PETA JALAN.
