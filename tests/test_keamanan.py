"""
Uji otomatis — "inspeksi mendadak" untuk memastikan semua pengaman bekerja.
Jalankan:  pytest -q
"""

import os

# Sandi uji diatur SEBELUM aplikasi dimuat
os.environ["NS_OPERATOR_PASSWORD"] = "sandi-operator-uji-123"
os.environ["NS_VIEWER_PASSWORD"] = "sandi-pengamat-uji-123"
os.environ.pop("NS_AUDIT_KEY", None)  # log audit di memori saja selama uji

import pytest
from fastapi.testclient import TestClient

from app import main
from app.audit import LOG
from app.keamanan import PEMBATAS


@pytest.fixture(autouse=True)
def bersihkan():
    PEMBATAS.reset()
    main.LAYANAN = main.salin_layanan_awal()
    yield


@pytest.fixture
def klien():
    return TestClient(main.app)


def token(klien, nama="operator", sandi="sandi-operator-uji-123"):
    r = klien.post("/api/login", json={"nama": nama, "sandi": sandi})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------- Autentikasi & otorisasi ----------
@pytest.mark.parametrize("metode,jalur,data", [
    ("get", "/api/layanan", None),
    ("post", "/api/indikator/cari", {"nilai": "203.0.113.45"}),
    ("post", "/api/simulasi", {"layanan_id": "pajak", "skenario": "ransomware"}),
    ("post", "/api/playbook/langkah", {"layanan_id": "pajak", "indeks": 0, "selesai": True}),
    ("post", "/api/pulihkan", {"layanan_id": "pajak"}),
    ("post", "/api/backup/catat", {"layanan_id": "pajak", "uji_pulih": True}),
    ("post", "/api/demo/majukan-waktu", {"jam": 6}),
    ("post", "/api/reset-demo", None),
    ("get", "/api/audit", None),
    ("post", "/api/lapsit", None),
])
def test_semua_endpoint_wajib_login(klien, metode, jalur, data):
    r = getattr(klien, metode)(jalur, **({"json": data} if data else {}))
    assert r.status_code == 401


def test_sandi_salah_ditolak(klien):
    r = klien.post("/api/login", json={"nama": "operator", "sandi": "salah-sekali"})
    assert r.status_code == 401


def test_token_palsu_ditolak(klien):
    r = klien.get("/api/layanan", headers={"Authorization": "Bearer token-palsu"})
    assert r.status_code == 401


def test_pengamat_tidak_boleh_mengubah(klien):
    h = token(klien, "pengamat", "sandi-pengamat-uji-123")
    assert klien.get("/api/layanan", headers=h).status_code == 200
    r = klien.post("/api/simulasi", headers=h, json={"layanan_id": "pajak", "skenario": "ddos"})
    assert r.status_code == 403


def test_logout_mencabut_token(klien):
    h = token(klien)
    assert klien.post("/api/logout", headers=h).status_code == 200
    assert klien.get("/api/layanan", headers=h).status_code == 401


# ---------- Validasi input ----------
@pytest.mark.parametrize("data", [
    {"layanan_id": "tidak-ada", "skenario": "ddos"},
    {"layanan_id": "pajak", "skenario": "hapus-semua"},
    {"layanan_id": "pajak", "skenario": "ddos", "kolom_asing": 1},
])
def test_input_simulasi_aneh_ditolak(klien, data):
    r = klien.post("/api/simulasi", headers=token(klien), json=data)
    assert r.status_code == 422


@pytest.mark.parametrize("nilai", ["<script>alert(1)</script>", "bukan indikator", "1.2.3", "zz"])
def test_indikator_tidak_valid_ditolak(klien, nilai):
    r = klien.post("/api/indikator/cari", headers=token(klien), json={"nilai": nilai})
    assert r.status_code == 422


def test_kiriman_terlalu_besar_ditolak(klien):
    r = klien.post("/api/indikator/cari", headers=token(klien), json={"nilai": "a" * 40000})
    assert r.status_code == 413


# ---------- Rate limiting ----------
def test_tebak_sandi_dibatasi(klien):
    kode = [klien.post("/api/login", json={"nama": "operator", "sandi": "x"}).status_code for _ in range(7)]
    assert kode[:5] == [401] * 5 and kode[5] == 429


# ---------- Header keamanan & CORS ----------
def test_header_keamanan(klien):
    r = klien.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "server" not in r.headers


def test_dokumentasi_api_dimatikan(klien):
    assert klien.get("/docs").status_code == 404
    assert klien.get("/openapi.json").status_code == 404


def test_cors_menolak_situs_asing(klien):
    r = klien.options("/api/layanan", headers={"Origin": "https://situs-jahat.example",
                                                "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "https://situs-jahat.example"


def test_health_tidak_membocorkan_info(klien):
    assert klien.get("/api/health").json() == {"status": "ok"}


# ---------- Fungsi utama ----------
def test_pencarian_indikator(klien):
    h = token(klien)
    j = klien.post("/api/indikator/cari", headers=h, json={"nilai": "203.0.113.45"}).json()
    assert j["cocok"] and j["indikator"]["id"] == "IOC-001"
    j = klien.post("/api/indikator/cari", headers=h, json={"nilai": "192.0.2.10"}).json()
    assert j["jenis"] == "ip" and not j["cocok"]


def test_alur_insiden_lengkap(klien):
    h = token(klien)
    j = klien.post("/api/simulasi", headers=h, json={"layanan_id": "pajak", "skenario": "ransomware"}).json()
    assert j["status"] == "merah" and j["insiden"]["log_peringatan"]
    # belum boleh pulih sebelum semua langkah selesai
    assert klien.post("/api/pulihkan", headers=h, json={"layanan_id": "pajak"}).status_code == 409
    for i in range(len(j["insiden"]["langkah"])):
        klien.post("/api/playbook/langkah", headers=h, json={"layanan_id": "pajak", "indeks": i, "selesai": True})
    j = klien.post("/api/pulihkan", headers=h, json={"layanan_id": "pajak"}).json()
    assert j["status"] == "hijau"


def test_kepatuhan_backup(klien):
    h = token(klien)
    awal = {l["id"]: l["status"] for l in klien.get("/api/layanan", headers=h).json()["layanan"]}
    assert awal["perizinan"] == "kuning" and awal["kesehatan"] == "kuning"
    j = klien.post("/api/backup/catat", headers=h, json={"layanan_id": "perizinan", "uji_pulih": True}).json()
    assert j["status"] == "hijau"
    klien.post("/api/demo/majukan-waktu", headers=h, json={"jam": 24})
    status = {l["id"]: l["status"] for l in klien.get("/api/layanan", headers=h).json()["layanan"]}
    assert status["imigrasi"] == "kuning"  # 6 + 24 jam > batas 24 jam


def test_lapsit_pdf(klien):
    r = klien.post("/api/lapsit", headers=token(klien))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


# ---------- Log audit ----------
def test_audit_minimisasi_data(klien):
    h = token(klien)
    klien.post("/api/indikator/cari", headers=h, json={"nilai": "203.0.113.45"})
    teks = str(LOG.daftar(500))
    assert "203.0.113.45" not in teks  # nilai mentah pencarian tidak disimpan


def test_audit_mendeteksi_manipulasi(klien):
    token(klien)
    assert LOG.verifikasi()["utuh"]
    asli = LOG._entri[0]["aktor"]
    LOG._uji_rusak(0, "aktor", "penyusup")
    hasil = LOG.verifikasi()
    LOG._uji_rusak(0, "aktor", asli)
    assert not hasil["utuh"]


# ---------- Fase 2: middleware ASGI murni (F-08, F-15) ----------
def _potongan(jumlah, ukuran=4096, awal=b'{"nama":"operator","sandi":"'):
    """Body chunked (tanpa Content-Length): httpx mengirim generator sebagai Transfer-Encoding: chunked."""
    yield awal
    for _ in range(jumlah):
        yield b"a" * ukuran
    yield b'"}'


def test_body_chunked_besar_ditolak_sebelum_router(klien):
    sebelum = len(LOG.daftar(10_000))
    r = klien.post("/api/login", content=_potongan(80), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.headers["connection"] == "close"
    assert "script-src 'self'" in r.headers["content-security-policy"]   # 413 tetap berstiker
    assert len(LOG.daftar(10_000)) == sebelum          # router & loket login tidak pernah tersentuh


def test_body_chunked_kecil_tetap_lolos_utuh(klien):
    body = iter([b'{"nama":"operator",', b'"sandi":"sandi-operator-uji-123"}'])
    r = klien.post("/api/login", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and r.json()["peran"] == "operator"


def test_content_length_besar_ditolak_tanpa_membaca_body(klien):
    r = klien.post("/api/login", content=b"x" * 20_000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.headers["connection"] == "close"


def test_tidak_ada_lagi_base_http_middleware():
    from starlette.middleware.base import BaseHTTPMiddleware
    kelas = [m.cls for m in main.app.user_middleware]
    assert not any(isinstance(k, type) and issubclass(k, BaseHTTPMiddleware) for k in kelas)


def test_header_keamanan_juga_pada_penolakan_host_asing():
    r = TestClient(main.app, base_url="http://situs-jahat.example").get("/api/health")
    assert r.status_code == 400 and r.headers["x-frame-options"] == "DENY"
