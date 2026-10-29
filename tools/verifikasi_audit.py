# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
Verifikasi log audit dan Buku Rantai Bukti TANPA menyalakan server.

Untuk auditor: alat ini membaca berkas JSONL yang ditulis Nusantara Shield (data/audit_log.jsonl dan
data/rantai_bukti.jsonl), lalu menghitung ulang seluruh rantai HMAC-SHA256 dengan kunci NS_AUDIT_KEY.
Sengaja berdiri sendiri: hanya pustaka bawaan Python, tidak mengimpor kode aplikasi, tidak membuka jaringan.
Jadi auditor tidak perlu memercayai server untuk memeriksa server.

Yang diperiksa pada setiap entri (sama dengan app/audit.py):
  1. nomor urut berurutan 1, 2, 3, ... (tidak ada yang disisipkan atau dihapus di tengah);
  2. "hash_sebelumnya" sama dengan sidik jari entri sebelumnya (rantai tidak putus);
  3. sidik jari HMAC-SHA256 atas isi entri cocok (isi tidak diubah, dan kuncinya benar).

Batas yang perlu diketahui: memotong entri di UJUNG berkas tidak membuat rantai putus. Karena itu cocokkan juga
sidik jari dari dokumen yang sudah diserahkan (LAPSIT bagian "Integritas log audit" atau berita acara):
    --cocokkan <sidik jari>  → harus ditemukan di rantai; bila tidak, log dipotong, kuncinya lain, atau berkasnya lain.

Kunci TIDAK diterima sebagai argumen baris perintah (agar tidak tersimpan di riwayat shell). Sumbernya:
variabel lingkungan NS_AUDIT_KEY, atau berkas kunci lewat --kunci-berkas. Kunci tidak pernah dicetak.

Pemakaian (dari akar repo):
    NS_AUDIT_KEY=... python3 tools/verifikasi_audit.py
    python3 tools/verifikasi_audit.py data/audit_log.jsonl --kunci-berkas /media/usb/kunci-audit.txt
    python3 tools/verifikasi_audit.py --cocokkan 9a829ef7534962403f68a25acb79deba8c44ddb7c1866f4dd3c91e4f26542971
    python3 tools/verifikasi_audit.py --json

Kode keluar: 0 = semua berkas utuh (dan sidik jari yang dicocokkan ditemukan), 1 = rusak atau tidak cocok,
2 = tidak bisa memeriksa (kunci atau berkas tidak ada, argumen salah).
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

HASH_AWAL = "0" * 64
BERKAS_BAWAAN = ("data/audit_log.jsonl", "data/rantai_bukti.jsonl")
POLA_HASH = re.compile(r"^[0-9a-f]{64}$")
CATATAN_UJUNG = ("Catatan: memotong entri di ujung berkas tidak memutus rantai. Cocokkan sidik jari dari dokumen "
                 "yang sudah diserahkan (LAPSIT/berita acara) dengan --cocokkan.")


def sidik_jari(kunci: bytes, entri: dict) -> str:
    """HMAC-SHA256 atas JSON kanonik entri tanpa kolom 'hash' (sama persis dengan app/audit.py)."""
    isi = {k: v for k, v in entri.items() if k != "hash"}
    kanonik = json.dumps(isi, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(kunci, kanonik.encode(), hashlib.sha256).hexdigest()


def periksa_berkas(berkas: Path, kunci: bytes) -> dict:
    """Periksa satu berkas JSONL. Berhenti di kerusakan PERTAMA dan menyebut nomor baris serta sebabnya."""
    hasil = {"berkas": str(berkas), "utuh": False, "jumlah": 0, "hash_terakhir": None,
             "pertama": None, "terakhir": None, "pesan": "", "entri": []}
    sebelumnya, urutan = HASH_AWAL, 0
    with berkas.open(encoding="utf-8") as f:
        for nomor_baris, baris in enumerate(f, start=1):
            if not baris.strip():
                continue
            try:
                e = json.loads(baris)
            except json.JSONDecodeError:
                hasil["pesan"] = f"Baris {nomor_baris} bukan JSON yang sah (berkas terpotong atau disunting)"
                return hasil
            if not isinstance(e, dict):
                hasil["pesan"] = f"Baris {nomor_baris} bukan entri log"
                return hasil
            urutan += 1
            if e.get("urutan") != urutan:
                hasil["pesan"] = f"Nomor urut loncat di baris {nomor_baris}: tertulis #{e.get('urutan')}, seharusnya #{urutan}"
                return hasil
            if e.get("hash_sebelumnya") != sebelumnya:
                hasil["pesan"] = f"Rantai putus di entri #{urutan}: entri sebelumnya hilang, disisipkan, atau diubah"
                return hasil
            if not hmac.compare_digest(sidik_jari(kunci, e), str(e.get("hash", ""))):
                hasil["pesan"] = (f"Sidik jari entri #{urutan} tidak cocok: isinya diubah, atau kunci yang dipakai "
                                  f"bukan kunci sistem ini")
                return hasil
            sebelumnya = e["hash"]
            hasil["entri"].append({k: e.get(k) for k in ("urutan", "waktu", "aktor", "aksi", "hash")})
    hasil["jumlah"] = urutan
    if urutan == 0:
        hasil["pesan"] = "Berkas kosong: tidak ada entri untuk diperiksa"
        return hasil
    hasil.update(utuh=True, hash_terakhir=sebelumnya, pertama=hasil["entri"][0], terakhir=hasil["entri"][-1],
                 pesan="Rantai utuh, tidak ada manipulasi terdeteksi")
    return hasil


def baca_kunci(berkas_kunci: str | None) -> bytes | None:
    if berkas_kunci:
        teks = Path(berkas_kunci).read_text(encoding="utf-8").strip().splitlines()
        return teks[0].strip().encode() if teks and teks[0].strip() else None
    nilai = os.getenv("NS_AUDIT_KEY", "")
    return nilai.encode() if nilai else None


def main(argv: list[str] | None = None, keluar=sys.stdout) -> int:
    p = argparse.ArgumentParser(prog="verifikasi_audit.py",
                                description="Verifikasi rantai HMAC log audit dan Buku Rantai Bukti tanpa server.")
    p.add_argument("berkas", nargs="*", help=f"berkas JSONL (bawaan: {', '.join(BERKAS_BAWAAN)} yang ada)")
    p.add_argument("--kunci-berkas", help="berkas berisi kunci NS_AUDIT_KEY (baris pertama); bawaan: variabel lingkungan")
    p.add_argument("--cocokkan", metavar="SIDIK_JARI", help="sidik jari dari LAPSIT/berita acara yang harus ada di rantai")
    p.add_argument("--json", action="store_true", help="keluaran JSON untuk diolah alat lain")
    a = p.parse_args(argv)

    tulis = lambda teks="": print(teks, file=keluar)
    if a.cocokkan and not POLA_HASH.match(a.cocokkan.strip().lower()):
        tulis("GAGAL: --cocokkan harus 64 karakter heksadesimal (sidik jari SHA-256).")
        return 2
    try:
        kunci = baca_kunci(a.kunci_berkas)
    except OSError as e:
        tulis(f"GAGAL: berkas kunci tidak bisa dibaca ({e.strerror}).")
        return 2
    if not kunci:
        tulis("GAGAL: kunci tidak ada. Atur NS_AUDIT_KEY atau pakai --kunci-berkas. Tanpa kunci yang sama dengan "
              "sistem, sidik jari HMAC tidak bisa dihitung ulang.")
        return 2
    daftar = [Path(b) for b in a.berkas] or [Path(b) for b in BERKAS_BAWAAN if Path(b).exists()]
    if not daftar:
        tulis(f"GAGAL: tidak ada berkas untuk diperiksa ({', '.join(BERKAS_BAWAAN)} tidak ditemukan). "
              "Log hanya tersimpan ke berkas bila server berjalan dengan NS_AUDIT_KEY.")
        return 2
    hilang = [str(b) for b in daftar if not b.is_file()]
    if hilang:
        tulis(f"GAGAL: berkas tidak ditemukan: {', '.join(hilang)}")
        return 2

    hasil = [periksa_berkas(b, kunci) for b in daftar]
    cocok = None
    if a.cocokkan:
        dicari = a.cocokkan.strip().lower()
        for h in hasil:
            for i, e in enumerate(h["entri"]):
                if e["hash"] == dicari:
                    cocok = {"berkas": h["berkas"], **e, "sesudahnya": len(h["entri"]) - i - 1}
                    break
            if cocok:
                break
    semua_utuh = all(h["utuh"] for h in hasil)
    kode = 0 if semua_utuh and (not a.cocokkan or cocok) else 1

    if a.json:
        tulis(json.dumps({"utuh": semua_utuh, "kode_keluar": kode,
                          "berkas": [{k: v for k, v in h.items() if k != "entri"} for h in hasil],
                          "cocokkan": ({"dicari": a.cocokkan.strip().lower(), "ditemukan": cocok} if a.cocokkan
                                       else None)}, ensure_ascii=False, indent=2))
        return kode
    for h in hasil:
        if h["utuh"]:
            tulis(f"[UTUH]  {h['berkas']} · {h['jumlah']} entri · #1 {h['pertama']['waktu']} s.d. "
                  f"#{h['jumlah']} {h['terakhir']['waktu']}")
            tulis(f"        Sidik jari terakhir: {h['hash_terakhir']}")
        else:
            tulis(f"[RUSAK] {h['berkas']} · {h['pesan']}")
    if a.cocokkan:
        if cocok:
            tulis(f"[COCOK] Sidik jari ditemukan di {cocok['berkas']} entri #{cocok['urutan']} "
                  f"({cocok['aksi']} oleh {cocok['aktor']}, {cocok['waktu']}); {cocok['sesudahnya']} entri tercatat sesudahnya.")
        else:
            tulis("[TIDAK COCOK] Sidik jari tidak ada di bagian rantai yang lolos pemeriksaan: log dipotong, diganti, "
                  "atau rusak sebelum entri itu; kuncinya lain; atau dokumen berasal dari sistem lain.")
    tulis(CATATAN_UJUNG)
    return kode


if __name__ == "__main__":
    sys.exit(main())
