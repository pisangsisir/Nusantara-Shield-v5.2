# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
delta.py — Tambalan struktural ringan (Fase 3, rekomendasi R2).

Analogi: koran langganan. Hari pertama pelanggan menerima satu edisi lengkap; hari berikutnya
loper hanya menyelipkan RALAT ("halaman 3, kolom 2: angka 87 → 91"), bukan koran utuh lagi.

Format satu operasi (subset ringkas RFC 6902, dipendekkan untuk menghemat byte):
    ["r", "/lalu_lintas/beban", 91.2]   ganti (replace) nilai di jalur itu
    ["a", "/soar/mttc/pajak", {...}]    tambah (add) kunci baru di objek
    ["d", "/soar/antre/pajak"]          hapus (delete) kunci dari objek
Jalur memakai "/" seperti JSON Pointer (RFC 6901); "~" → "~0" dan "/" → "~1" di dalam kunci.

Daftar (list):
- panjang berbeda → seluruh daftar diganti satu operasi;
- panjang sama → dibandingkan per elemen, lalu DIPILIH YANG LEBIH HEMAT BYTE:
  * riwayat beban 48 detik yang bergeser satu langkah tiap detik → 48 operasi kecil lebih besar
    daripada daftarnya sendiri → kirim satu "r" untuk seluruh daftar;
  * 3 berita CTI yang hanya berubah 'sisa_detik' & 'kesegaran'-nya → 6 operasi kecil jauh lebih
    hemat daripada mengirim ulang teks berita lengkap → kirim per elemen.
"""

from __future__ import annotations

import json
from typing import Any


def _ukuran(x: Any) -> int:
    return len(json.dumps(x, separators=(",", ":"), ensure_ascii=False))


def _kunci(k: str) -> str:
    return str(k).replace("~", "~0").replace("/", "~1")


def beda(lama: Any, baru: Any, jalur: str = "") -> list[list]:
    """Operasi minimal yang mengubah `lama` menjadi `baru`. Kedua argumen = data hasil json.loads."""
    if type(lama) is not type(baru):
        return [["r", jalur, baru]]
    if isinstance(baru, dict):
        ops: list[list] = [["d", f"{jalur}/{_kunci(k)}"] for k in lama.keys() - baru.keys()]
        for k, v in baru.items():
            j = f"{jalur}/{_kunci(k)}"
            if k not in lama:
                ops.append(["a", j, v])
            elif lama[k] != v:
                ops += beda(lama[k], v, j)
        return ops
    if isinstance(baru, list):
        if len(lama) != len(baru):
            return [["r", jalur, baru]]
        ops = []
        for i, (a, b) in enumerate(zip(lama, baru)):
            if a != b:
                ops += beda(a, b, f"{jalur}/{i}")
        if ops and _ukuran(ops) >= _ukuran(baru):             # per elemen justru lebih boros
            return [["r", jalur, baru]]
        return ops
    return [] if lama == baru else [["r", jalur, baru]]


def terapkan(dok: Any, ops: list[list]) -> Any:
    """Cermin Python dari terapkanTambalan() di app.js — dipakai uji untuk membuktikan keduanya setara."""
    for op in ops:
        jenis, jalur = op[0], op[1]
        if jalur == "":
            dok = op[2]
            continue
        bagian = [b.replace("~1", "/").replace("~0", "~") for b in jalur.split("/")[1:]]
        induk = dok
        for b in bagian[:-1]:
            induk = induk[int(b)] if isinstance(induk, list) else induk[b]
        akhir: Any = int(bagian[-1]) if isinstance(induk, list) else bagian[-1]
        if jenis == "d":
            del induk[akhir]
        else:
            induk[akhir] = op[2]
    return dok
