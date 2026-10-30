"""
Uji Fase 1 (F-01, F-10, F-12) — kamus istilah adalah SATU-SATUNYA sumber label.
Bila uji ini gagal, berarti ada label yang ditulis langsung di kode: pindahkan ke app/istilah.py.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.data_contoh import KEBIJAKAN, PLAYBOOK, PLAYBOOK_RINGKAS
from app.istilah import ISTILAH, kepada_manajemen
from app.keamanan import PEMBATAS

AKAR = Path(__file__).resolve().parent.parent


def _label(nilai):
    """Semua teks label di kamus (termasuk isi daftar manajemen)."""
    if isinstance(nilai, str):
        yield nilai
    elif isinstance(nilai, dict):
        for v in nilai.values():
            yield from _label(v)
    elif isinstance(nilai, list):
        for v in nilai:
            yield from _label(v)


# Nama peran ("Operator", "Pengamat") juga kata biasa dalam kalimat ("keputusan Operator"); yang dijaga kamus
# hanyalah label chip/header peran, dan itu diuji di test_versi.py::test_nama_peran_berhuruf_kapital.
LABEL = sorted({t for k, v in ISTILAH.items() if not k.startswith("peran_")
                for t in _label(v) if len(t) >= 6 and "{" not in t})
BERKAS = [p for p in [*AKAR.glob("app/*.py"), *AKAR.glob("static/*.js"), AKAR / "static/index.html"]
          if p.name != "istilah.py"]


@pytest.mark.parametrize("label", LABEL)
def test_tidak_ada_label_tertanam_di_luar_kamus(label):
    tertanam = [p.relative_to(AKAR).as_posix() for p in BERKAS if label in p.read_text(encoding="utf-8")]
    assert not tertanam, f"Label {label!r} tertulis langsung di {tertanam}; pakai ISTILAH[...]"


def test_skrip_patch_terminologi_sudah_dihapus():
    assert not (AKAR / "app/patch_pussiber.py").exists()


def test_kamus_tersaji_untuk_browser_tanpa_login():
    PEMBATAS.reset()
    r = TestClient(main.app).get("/api/istilah")
    assert r.status_code == 200 and r.json() == ISTILAH


def test_playbook_dan_kebijakan_dirakit_dari_kamus():
    for langkah in PLAYBOOK.values():
        lapor = next(t for t in langkah if t.startswith("LAPOR"))
        assert ISTILAH["laporan"] in lapor and kepada_manajemen() in lapor
    assert all(ISTILAH["laporan_singkat"] in r for r in PLAYBOOK_RINGKAS.values())
    assert ISTILAH["tim_insiden"] in KEBIJAKAN["isi"]
