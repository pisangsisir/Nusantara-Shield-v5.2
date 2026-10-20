"""
Uji Fase 5 (audit #7) — pendaftaran akun & dasbor akun operator.

Prinsip yang dikunci:
- Siapa pun boleh membuat akun PENGAMAT (hanya melihat); kata sandi minimal 12 karakter.
- Akun OPERATOR (bisa memutus jaringan) TIDAK bisa dibuat sendiri tanpa kode undangan yang sah,
  atau harus dibuatkan oleh operator yang sudah login.
- Operator melihat jumlah pengamat terdaftar / sedang login / sedang memantau; pengamat tidak bisa.
- Sandi tidak pernah tersimpan atau tercatat dalam bentuk asli.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import keamanan, main
from app.audit import LOG
from app.keamanan import AKUN, PEMBATAS, muat_akun_terdaftar

SANDI = "sandi-panjang-uji-777"


@pytest.fixture(autouse=True)
def bersihkan(monkeypatch):
    PEMBATAS.reset()
    keamanan._uji_reset_akun()
    monkeypatch.delenv("NS_KODE_OPERATOR", raising=False)
    monkeypatch.delenv("NS_DAFTAR_PENGAMAT", raising=False)
    monkeypatch.delenv("NS_AKUN_FILE", raising=False)
    yield
    keamanan._uji_reset_akun()


@pytest.fixture
def k():
    return TestClient(main.app)


def daftar(k, nama, sandi=SANDI, peran="pengamat", **lain):
    return k.post("/api/akun/daftar", json={"nama": nama, "sandi": sandi, "peran": peran, **lain})


def masuk(k, nama, sandi):
    r = k.post("/api/login", json={"nama": nama, "sandi": sandi})
    return {"Authorization": f"Bearer {r.json()['token']}"} if r.status_code == 200 else r.status_code


def operator(k):
    return masuk(k, "operator", "sandi-operator-uji-123")


# ---------- a. registrasi & login ----------
def test_pengamat_mendaftar_sendiri_lalu_login_dan_hanya_bisa_melihat(k):
    r = daftar(k, "budi_pengamat")
    assert r.status_code == 201 and r.json()["peran"] == "pengamat"
    h = masuk(k, "budi_pengamat", SANDI)
    assert isinstance(h, dict)
    assert k.get("/api/telemetri", headers=h).status_code == 200
    assert k.post("/api/simulasi", headers=h, json={"layanan_id": "pajak", "skenario": "ddos"}).status_code == 403
    assert k.get("/api/akun/ringkasan", headers=h).status_code == 403
    assert masuk(k, "budi_pengamat", "sandi-yang-salah-sekali") == 401


def test_operator_mandiri_tanpa_kode_atau_kode_salah_ditolak(k, monkeypatch):
    assert daftar(k, "penyusup", peran="operator").status_code == 403          # kode tidak diatur sama sekali
    monkeypatch.setenv("NS_KODE_OPERATOR", "kode-undangan-rahasia-42")
    assert daftar(k, "penyusup", peran="operator", kode_operator="tebakan").status_code == 403
    assert "penyusup" not in AKUN
    assert any(e["aksi"] == "DAFTAR_OPERATOR_DITOLAK" for e in LOG.daftar(5))


def test_operator_dengan_kode_undangan_sah_bisa_mengubah(k, monkeypatch):
    monkeypatch.setenv("NS_KODE_OPERATOR", "kode-undangan-rahasia-42")
    r = daftar(k, "sertu_andi", peran="operator", kode_operator="kode-undangan-rahasia-42")
    assert r.status_code == 201 and r.json()["peran"] == "operator"
    h = masuk(k, "sertu_andi", SANDI)
    assert k.post("/api/simulasi", headers=h, json={"layanan_id": "pajak", "skenario": "ddos"}).status_code == 200
    main.LAYANAN = main.salin_layanan_awal()


@pytest.mark.parametrize("nama,sandi,kode", [
    ("Budi", SANDI, 422),                 # huruf besar
    ("ab", SANDI, 422),                   # terlalu pendek
    ("budi!", SANDI, 422),                # simbol
    ("1budi", SANDI, 422),                # harus diawali huruf
    ("budi_ok", "pendek", 422),           # sandi < 12
    ("budi_ok", "xxbudi_okxxxx", 422),    # sandi memuat nama akun
    ("operator", SANDI, 409),             # nama akun bawaan sudah dipakai
])
def test_isian_pendaftaran_divalidasi(k, nama, sandi, kode):
    assert daftar(k, nama, sandi).status_code == kode


def test_nama_ganda_ditolak_dan_kolom_asing_ditolak(k):
    assert daftar(k, "sinta").status_code == 201
    assert daftar(k, "sinta").status_code == 409
    r = k.post("/api/akun/daftar", json={"nama": "rudi", "sandi": SANDI, "peran": "pengamat", "izin": ["ubah"]})
    assert r.status_code == 422                                                  # extra="forbid"
    assert daftar(k, "rudi", peran="admin").status_code == 422                   # peran di luar daftar


def test_pendaftaran_pengamat_bisa_ditutup_administrator(k, monkeypatch):
    monkeypatch.setenv("NS_DAFTAR_PENGAMAT", "0")
    assert daftar(k, "tamu_baru").status_code == 403


def test_pendaftaran_dibatasi_laju(k):
    kode = [daftar(k, f"akun_{i}").status_code for i in range(7)]
    assert kode[:5] == [201] * 5 and kode[5:] == [429, 429]


def test_sandi_tidak_pernah_tercatat_di_log_audit(k):
    daftar(k, "rahasia_ok")
    e = next(e for e in LOG.daftar(5) if e["aksi"] == "AKUN_DIBUAT")
    assert e["detail"] == {"nama": "rahasia_ok", "peran": "pengamat", "cara": "mandiri"}
    assert SANDI not in json.dumps(LOG.daftar(50))


# ---------- b. dasbor akun operator ----------
def test_operator_melihat_jumlah_pengamat_terdaftar_aktif_dan_memantau(k):
    for n in ("pengamat_a", "pengamat_b", "pengamat_c"):
        assert daftar(k, n).status_code == 201
    ha = masuk(k, "pengamat_a", SANDI)
    masuk(k, "pengamat_b", SANDI)
    ho = operator(k)
    keamanan.SIARAN.masuk("pengamat_a")                                          # pengamat_a membuka siaran
    try:
        j = k.get("/api/akun/ringkasan", headers=ho).json()
    finally:
        keamanan.SIARAN.keluar("pengamat_a")
    p = j["hitung"]["pengamat"]
    assert p == {"terdaftar": 4, "aktif": 2, "memantau": 1}                     # 3 baru + 1 bawaan
    assert j["hitung"]["operator"]["aktif"] == 1
    baris = {a["nama"]: a for a in j["akun"]}
    assert baris["pengamat_a"]["sesi"] == 1 and baris["pengamat_c"]["sesi"] == 0
    assert not any(kunci in json.dumps(j) for kunci in ("garam", "hash", "token"))
    # keluar = tidak lagi dihitung aktif
    k.post("/api/logout", headers=ha)
    assert k.get("/api/akun/ringkasan", headers=ho).json()["hitung"]["pengamat"]["aktif"] == 1


def test_ringkasan_wajib_login_operator(k):
    assert k.get("/api/akun/ringkasan").status_code == 401
    h = masuk(k, "pengamat", "sandi-pengamat-uji-123")
    assert k.get("/api/akun/ringkasan", headers=h).status_code == 403


def test_operator_membuat_akun_dari_dasbor(k):
    ho = operator(k)
    r = k.post("/api/akun", headers=ho, json={"nama": "letda_sari", "sandi": SANDI, "peran": "operator"})
    assert r.status_code == 201
    e = next(e for e in LOG.daftar(5) if e["aksi"] == "AKUN_DIBUAT")
    assert e["aktor"] == "operator" and e["detail"]["cara"] == "operator"
    hp = masuk(k, "pengamat", "sandi-pengamat-uji-123")
    assert k.post("/api/akun", headers=hp, json={"nama": "x_baru", "sandi": SANDI}).status_code == 403


# ---------- penyimpanan permanen ----------
def test_akun_tersimpan_tanpa_sandi_asli_dan_bisa_dimuat_ulang(k, tmp_path, monkeypatch):
    berkas = tmp_path / "akun.json"
    monkeypatch.setenv("NS_AKUN_FILE", str(berkas))
    assert daftar(k, "awet_ok").status_code == 201
    isi = berkas.read_text("utf-8")
    assert SANDI not in isi and "awet_ok" in isi and "hash" in isi
    assert "operator" not in json.loads(isi)                                     # akun bawaan tidak ditulis
    del AKUN["awet_ok"]                                                          # = server dinyalakan ulang
    assert muat_akun_terdaftar(berkas) == 1
    assert isinstance(masuk(k, "awet_ok", SANDI), dict)
