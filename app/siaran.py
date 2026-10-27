# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
siaran.py — SATU dapur, SATU pengeras suara (Fase 2, R1) + TAMBALAN (Fase 3, R2).

Analogi: dulu setiap meja punya koki pribadi. Sekarang ada satu koki (dapur() di main.py) dan satu
pengeras suara (Hub). Sejak Fase 3 pengeras suara tidak lagi membacakan menu lengkap tiap detik,
melainkan hanya RALAT-nya (tambalan). Meja yang baru datang diberi satu menu lengkap terkini,
lalu ikut mendengar ralat berikutnya.

Rantai pesan per layar:   keadaan#n  →  tambalan(dari n)#n+1  →  tambalan(dari n+1)#n+2 …
Nomor #n dikirim di baris SSE "id:"; setiap tambalan menyebut "dari" nomor yang menjadi dasarnya.
Bila layar mendapati rantainya putus, ia menyambung ulang dan menerima menu lengkap lagi.

Aturan pakai: semua metode Hub dipanggil dari event loop yang sama (dapur dan _alirkan),
jadi tidak butuh kunci. Dari thread lain, bangunkan Hub lewat loop.call_soon_threadsafe.
"""

from __future__ import annotations

import asyncio

MAKS_ANTRE = 64     # kotak surat per layar; penuh = layar terlalu lambat membaca


class Hub:
    def __init__(self, maks_antre: int = MAKS_ANTRE) -> None:
        self._maks_antre = maks_antre
        self.mulai()

    def mulai(self) -> None:
        """Dipanggil setiap aplikasi menyala (lifespan): Event & antrean terikat pada loop yang berjalan."""
        self.bangun: asyncio.Event | None = None
        self._pelanggan: set[asyncio.Queue[bytes]] = set()
        self.keadaan_terakhir: bytes | None = None    # menu lengkap TERKINI (bukan yang terakhir disiarkan)

    # -- dipanggil dari event loop ----------------------------------------------------
    def siapkan(self) -> None:
        self.bangun = asyncio.Event()

    def bangunkan(self) -> None:
        if self.bangun is not None:
            self.bangun.set()

    @property
    def jumlah(self) -> int:
        return len(self._pelanggan)

    def langganan(self) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(self._maks_antre)
        if self.keadaan_terakhir:
            q.put_nowait(self.keadaan_terakhir)       # layar baru: satu menu lengkap terkini
        self._pelanggan.add(q)
        return q

    def lepas(self, q: asyncio.Queue[bytes]) -> None:
        self._pelanggan.discard(q)

    def terbitkan(self, keadaan: bytes, tambalan: bytes | None) -> None:
        """keadaan  = potret utuh terkini; DISIMPAN untuk layar yang baru datang, tidak disiarkan.
        tambalan = selisih terhadap potret sebelumnya; INI yang disiarkan ke semua layar.
        tambalan None (detak pertama / pemaksaan) → potret utuh disiarkan ke semua layar."""
        self.keadaan_terakhir = keadaan
        pesan = tambalan if tambalan is not None else keadaan
        for q in self._pelanggan:
            if q.full():
                # Layar lambat (jaringan cabang tersendat): buang tumpukannya dan ganti dengan satu
                # menu lengkap terkini. Rantai nomor tetap utuh karena menu itu memuat nomor terbaru.
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(keadaan)
            else:
                q.put_nowait(pesan)


HUB = Hub()
