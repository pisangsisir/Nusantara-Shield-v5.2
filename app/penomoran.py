# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
penomoran.py — Nomor laporan yang TIDAK PERNAH berulang (temuan audit F-03).

Analogi: buku kuitansi bernomor seri. Kertasnya boleh dirobek (demo direset), tetapi nomor
seri berikutnya tetap melanjutkan, tidak mulai lagi dari 001.

- Nomor tampilan : IR-2026-001, IR-2026-002, ... (urut per tahun, mudah dibacakan di radio).
- Identitas mesin: UUID4 per laporan, untuk jaga-jaga bila dua server pernah dipakai bersamaan.
- Penyimpanan    : bila log audit permanen (NS_AUDIT_KEY diatur) atau NS_IR_FILE diisi, hitungan
                   ditulis ke berkas JSON secara atomik, sehingga juga selamat dari restart server.
                   Tanpa itu (mode demo/uji), hitungan hidup di memori selama proses berjalan.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _berkas_bawaan() -> Path | None:
    jalur = os.getenv("NS_IR_FILE")
    if jalur:
        return Path(jalur)
    if os.getenv("NS_AUDIT_KEY"):                  # log audit permanen → penomoran ikut permanen
        return Path("data/nomor_ir.json")
    return None


class PencacahIR:
    def __init__(self, berkas: Path | None = None) -> None:
        self._berkas = berkas
        self._hitung: dict[str, int] = {}          # {"2026": 7}
        if berkas and berkas.exists():
            self._hitung = {str(k): int(v) for k, v in json.loads(berkas.read_text("utf-8")).items()}

    def berikutnya(self, prefiks: str) -> tuple[str, str]:
        """Mengembalikan (nomor tampilan, uuid). Dipanggil SAMBIL memegang _kunci_state."""
        tahun = str(datetime.now(timezone.utc).year)
        n = self._hitung.get(tahun, 0) + 1
        self._hitung[tahun] = n
        self._simpan()
        return f"{prefiks}-{tahun}-{n:03d}", uuid.uuid4().hex

    def _simpan(self) -> None:
        if not self._berkas:
            return
        self._berkas.parent.mkdir(parents=True, exist_ok=True)
        sementara = self._berkas.with_suffix(".tmp")
        sementara.write_text(json.dumps(self._hitung), "utf-8")
        os.replace(sementara, self._berkas)        # atomik: tidak pernah setengah tertulis


PENCACAH = PencacahIR(_berkas_bawaan())
