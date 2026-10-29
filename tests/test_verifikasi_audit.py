# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
Uji tools/verifikasi_audit.py: auditor memverifikasi log audit dan Buku Rantai Bukti TANPA menyalakan server.

Log ditulis oleh kelas yang sama dengan server (app.audit.LogAudit, app.bukti.RantaiBukti), lalu diperiksa oleh
alat baris perintah yang berdiri sendiri. Setiap jenis manipulasi harus tertangkap beserta letaknya:
isi diubah, entri dihapus di tengah, baris rusak, kunci salah, dan log yang dipotong di ujung (lewat --cocokkan).
"""

import importlib.util
import io
import json
from pathlib import Path

import pytest

from app.audit import LogAudit
from app.bukti import RantaiBukti
from app.penomoran import PencacahIR

AKAR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("verifikasi_audit", AKAR / "tools" / "verifikasi_audit.py")
alat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alat)

KUNCI = "kunci-audit-uji-0123456789abcdef0123456789abcdef"


@pytest.fixture
def log(tmp_path, monkeypatch):
    """Log audit ASLI berisi 5 entri, ditulis ke berkas oleh kelas yang dipakai server."""
    monkeypatch.setenv("NS_AUDIT_KEY", KUNCI)
    monkeypatch.setenv("NS_AUDIT_FILE", str(tmp_path / "audit_log.jsonl"))
    buku = LogAudit()
    for i, aksi in enumerate(["LOGIN", "SIMULASI_INSIDEN", "BUKTI_DIAMANKAN", "SOAR_JALANKAN", "EKSPOR_LAPSIT"]):
        buku.catat("operator", aksi, {"langkah": i})
    return buku, tmp_path / "audit_log.jsonl"


def jalankan(*argv):
    keluar = io.StringIO()
    kode = alat.main(list(argv), keluar=keluar)
    return kode, keluar.getvalue()


def baris(berkas: Path) -> list[str]:
    return berkas.read_text(encoding="utf-8").splitlines()


def test_log_asli_dinyatakan_utuh_dan_sidik_jari_terakhir_sama_dengan_server(log):
    buku, berkas = log
    kode, teks = jalankan(str(berkas))
    assert kode == 0 and "[UTUH]" in teks and "5 entri" in teks
    assert buku.verifikasi()["hash_terakhir"] in teks              # angka yang sama dengan yang dicetak LAPSIT


def test_isi_entri_diubah_tertangkap_beserta_nomornya(log):
    _, berkas = log
    b = baris(berkas)
    e = json.loads(b[2])
    e["detail"]["langkah"] = 99                                      # sunting diam-diam entri #3
    b[2] = json.dumps(e, ensure_ascii=False)
    berkas.write_text("\n".join(b) + "\n", encoding="utf-8")
    kode, teks = jalankan(str(berkas))
    assert kode == 1 and "[RUSAK]" in teks and "entri #3" in teks


def test_entri_dihapus_di_tengah_tertangkap(log):
    _, berkas = log
    b = baris(berkas)
    berkas.write_text("\n".join(b[:1] + b[2:]) + "\n", encoding="utf-8")
    kode, teks = jalankan(str(berkas))
    assert kode == 1 and "Nomor urut loncat" in teks


def test_entri_sah_dari_log_lain_disisipkan_tertangkap_oleh_mata_rantai(log, tmp_path, monkeypatch):
    """Entri #3 diganti entri #3 dari log lain berkunci SAMA: nomor urut dan HMAC-nya sah, hanya mata rantai yang
    membongkarnya (hash_sebelumnya tidak menunjuk entri #2 log ini)."""
    _, berkas = log
    monkeypatch.setenv("NS_AUDIT_FILE", str(tmp_path / "log_lain.jsonl"))
    lain = LogAudit()
    for aksi in ("LOGIN", "LOGIN", "TUTUP_INSIDEN"):
        lain.catat("penyusup", aksi, {})
    b = baris(berkas)
    b[2] = baris(tmp_path / "log_lain.jsonl")[2]
    berkas.write_text("\n".join(b) + "\n", encoding="utf-8")
    kode, teks = jalankan(str(berkas))
    assert kode == 1 and "Rantai putus di entri #3" in teks


def test_baris_rusak_disebut_nomor_barisnya(log):
    _, berkas = log
    with berkas.open("a", encoding="utf-8") as f:
        f.write('{"urutan": 6, "aksi": "TERPOT\n')
    kode, teks = jalankan(str(berkas))
    assert kode == 1 and "Baris 6 bukan JSON" in teks


def test_kunci_salah_tidak_pernah_lolos(log, monkeypatch):
    _, berkas = log
    monkeypatch.setenv("NS_AUDIT_KEY", "kunci-lain-yang-bukan-milik-sistem-ini")
    kode, teks = jalankan(str(berkas))
    assert kode == 1 and "entri #1" in teks and "kunci" in teks


def test_tanpa_kunci_atau_argumen_salah_berhenti_dengan_kode_2(log, monkeypatch):
    _, berkas = log
    monkeypatch.delenv("NS_AUDIT_KEY")
    kode, teks = jalankan(str(berkas))
    assert kode == 2 and "kunci tidak ada" in teks
    monkeypatch.setenv("NS_AUDIT_KEY", KUNCI)
    assert jalankan(str(berkas), "--cocokkan", "bukan-sidik-jari")[0] == 2
    assert jalankan(str(berkas.with_name("tidak-ada.jsonl")))[0] == 2


def test_kunci_dari_berkas_dan_tidak_pernah_dicetak(log, monkeypatch, tmp_path):
    _, berkas = log
    monkeypatch.delenv("NS_AUDIT_KEY")
    berkas_kunci = tmp_path / "kunci.txt"
    berkas_kunci.write_text(KUNCI + "\n", encoding="utf-8")
    for tambahan in ([], ["--json"]):
        kode, teks = jalankan(str(berkas), "--kunci-berkas", str(berkas_kunci), *tambahan)
        assert kode == 0 and KUNCI not in teks


def test_cocokkan_sidik_jari_dokumen_menangkap_log_yang_dipotong(log):
    buku, berkas = log
    dari_lapsit = buku.daftar(50)[1]["hash"]                          # sidik jari entri #4, seolah dicetak di LAPSIT
    kode, teks = jalankan(str(berkas), "--cocokkan", dari_lapsit)
    assert kode == 0 and "[COCOK]" in teks and "entri #4" in teks and "1 entri tercatat sesudahnya" in teks
    berkas.write_text("\n".join(baris(berkas)[:3]) + "\n", encoding="utf-8")   # buang 2 entri terakhir
    kode, teks = jalankan(str(berkas), "--cocokkan", dari_lapsit)
    assert "[UTUH]" in teks                                          # rantai sendiri tidak bisa melihat pemotongan…
    assert kode == 1 and "[TIDAK COCOK]" in teks                     # …tetapi sidik jari dokumen bisa


def test_buku_rantai_bukti_ikut_diperiksa(log, tmp_path, monkeypatch):
    _, berkas_audit = log
    monkeypatch.setenv("NS_BUKTI_FILE", str(tmp_path / "rantai_bukti.jsonl"))
    rantai = RantaiBukti(LogAudit("NS_BUKTI_FILE", "data/rantai_bukti.jsonl", "buku rantai bukti"), PencacahIR())
    rantai.amankan(layanan_id="kesehatan", insiden_id="uji", skenario="ransomware", petugas="operator", metode="soar")
    kode, teks = jalankan(str(berkas_audit), str(tmp_path / "rantai_bukti.jsonl"))
    assert kode == 0 and teks.count("[UTUH]") == 2 and "rantai_bukti.jsonl · 1 entri" in teks


def test_keluaran_json_untuk_alat_lain(log):
    buku, berkas = log
    kode, teks = jalankan(str(berkas), "--json", "--cocokkan", buku.verifikasi()["hash_terakhir"])
    j = json.loads(teks)
    assert kode == 0 and j["utuh"] and j["berkas"][0]["jumlah"] == 5
    assert j["cocokkan"]["ditemukan"]["aksi"] == "EKSPOR_LAPSIT"


def test_alat_berdiri_sendiri_tanpa_kode_aplikasi_dan_tanpa_jaringan():
    sumber = (AKAR / "tools" / "verifikasi_audit.py").read_text(encoding="utf-8")
    for terlarang in ("from app", "import app", "import socket", "import urllib", "import requests",
                      "import httpx", "subprocess"):
        assert terlarang not in sumber, terlarang
