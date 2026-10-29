# Kunci rilis

Folder ini hanya berisi **kunci publik** rilis Nusantara Shield (`kunci-publik-rilis.pem`, Ed25519).
Kunci publik dipakai `pasang.sh` di Ubuntu untuk memverifikasi tanda tangan `SHA256SUMS.sig` sebelum paket dipasang.

**Kunci privat tidak pernah ada di repo ini.** Ia dibuat dan disimpan terenkripsi (kata sandi minimal 16 karakter,
izin 600) di komputer pembuat rilis, di `~/.nusantara-shield/kunci-rilis.pem`, oleh:

```sh
python3 tools/kunci_rilis.py buat
```

**Sidik jari kunci rilis yang berlaku** (dibuat 29 Oktober 2026 di Mac pembuat rilis):

```
00a223f10fe2848df6b5a1fcd016857dd0cfdb8506d9a96efbcb9bb006e5240a
```

Angka ini juga tertanam di `pasang.sh` setiap paket dan dicatat di berita acara. Bila kunci pernah diganti,
paket lama tetap diverifikasi dengan kunci publik yang ikut di dalam paket itu.

Sidik jari kunci publik (yang dicatat di berita acara) dihitung dengan:

```sh
openssl pkey -pubin -in kunci/kunci-publik-rilis.pem -outform DER | sha256sum
python3 tools/kunci_rilis.py sidik-jari kunci/kunci-publik-rilis.pem      # hasilnya sama
```

Uji otomatis `tests/test_paket_ubuntu.py` memeriksa bahwa tidak ada kunci privat di berkas mana pun yang ikut rilis.
