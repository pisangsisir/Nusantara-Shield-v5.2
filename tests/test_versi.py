# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
Uji satu sumber versi dan nama peran yang tampil.

Latar: rilis v5.2.0 masih menampilkan "v5.1" di dasbor dan kop LAPSIT karena label versi ditulis langsung
di beberapa berkas. Sekarang semuanya membaca app/versi.py; uji ini gagal bila label versi muncul lagi
di teks yang tampil ke pengguna, atau bila alat pengemas memakai nomor yang berbeda.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.istilah import ISTILAH
from app.main import app
from app.versi import VERSI

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR / "tools"))
import kemas_installer  # noqa: E402
import kemas_rilis  # noqa: E402

LABEL_VERSI = re.compile(r"\bv\d+\.\d+(\.\d+)?\b")


def _bukan_komentar(baris: str) -> bool:
    s = baris.strip()
    return not (s.startswith(("#", "//", "*", "<!--")) or s.lower().startswith("rem "))


def test_format_versi():
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSI)


def test_alat_pengemas_membaca_versi_yang_sama():
    assert kemas_rilis.baca_versi() == VERSI
    assert kemas_rilis.NAMA == f"nusantara-shield-v{VERSI}"
    assert kemas_installer.VERSI_BAWAAN == VERSI


def test_tidak_ada_label_versi_tertulis_langsung():
    """Docstring dan komentar riwayat ("v5.1: laci minimalis") boleh; teks yang tampil tidak."""
    temuan = []
    for p in [*sorted((AKAR / "app").glob("*.py")), AKAR / "static" / "index.html", AKAR / "static" / "app.js",
              AKAR / "run_tests.sh", AKAR / "run_tests.bat"]:
        if p.name == "versi.py":
            continue
        teks = p.read_text(encoding="utf-8")
        if p.suffix == ".py":                       # buang docstring (riwayat), sisakan kode
            teks = re.sub(r'"""[\s\S]*?"""', lambda m: "\n" * m.group(0).count("\n"), teks)
        teks = re.sub(r"<!--[\s\S]*?-->", lambda m: "\n" * m.group(0).count("\n"), teks)
        for no, baris in enumerate(teks.splitlines(), 1):
            kode = baris.split(" # ")[0].split(" // ")[0]
            if _bukan_komentar(baris) and LABEL_VERSI.search(kode):
                temuan.append(f"{p.relative_to(AKAR)}:{no}: {baris.strip()[:90]}")
    assert not temuan, "label versi ditulis langsung:\n" + "\n".join(temuan)


def test_dasbor_dan_lapsit_memakai_versi():
    with TestClient(app) as c:
        assert c.get("/api/istilah").json()["nama_versi"] == f"Nusantara Shield v{VERSI}"
    sumber = (AKAR / "app" / "lapsit.py").read_text(encoding="utf-8")
    assert 'Luring \\u00b7 v{VERSI}"' in sumber


def test_nama_peran_berhuruf_kapital():
    assert ISTILAH["peran_operator"] == "Operator" and ISTILAH["peran_pengamat"] == "Pengamat"
    js = (AKAR / "static" / "app.js").read_text(encoding="utf-8")
    # header sesi, chip tabel akun, dan toast tidak lagi menampilkan nilai mentah S.peran / a.peran / j.peran
    assert "teks: a.peran }" not in js and "`· ${S.peran}`" not in js and "(${j.peran})" not in js
