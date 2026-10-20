"""
Uji v3 — Threat Intelligence (korelasi proaktif), SOAR, dan Peta Ancaman Global.
Jalankan:  pytest -q
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main
from app.keamanan import KONFIG, PEMBATAS

JAM = {"t": 5000.0}


@pytest.fixture(autouse=True)
def bersihkan():
    PEMBATAS.reset()
    main.LAYANAN = main.salin_layanan_awal()
    JAM["t"] = 5000.0
    main.MENARA._jam = lambda: JAM["t"]
    main.MENARA.reset()
    main.MENARA.osint.berikut = 1e12        # matikan siaran otomatis: uji yang menentukan berita
    umur = KONFIG.umur_siaran_detik
    yield
    KONFIG.umur_siaran_detik = umur


@pytest.fixture
def klien():
    return TestClient(main.app)


def masuk(klien, nama="operator", sandi="sandi-operator-uji-123"):
    j = klien.post("/api/login", json={"nama": nama, "sandi": sandi}).json()
    return {"Authorization": f"Bearer {j['token']}"}


def potret(klien, h):
    return klien.get("/api/telemetri", headers=h).json()


def simpul(k):
    return {s["id"]: s for s in k["topologi"]["simpul"]}


def majukan(detik):
    JAM["t"] += detik


def siarkan(klien, h, berita_id):
    """Siarkan satu berita lalu matikan lagi jadwal otomatis (siaran manual menjadwal ulang radio)."""
    r = klien.post("/api/cti/siarkan", headers=h, json={"berita_id": berita_id})
    main.MENARA.osint.berikut = 1e12
    return r


# ---------- akses ----------
@pytest.mark.parametrize("jalur,data", [
    ("/api/cti/siarkan", {}),
    ("/api/soar/jalankan", {"layanan_id": "pajak", "aksi": "isolasi"}),
    ("/api/soar/perketat", {"aset_id": "api"}),
])
def test_loket_baru_wajib_login_dan_hanya_operator(klien, jalur, data):
    assert klien.post(jalur, json=data).status_code == 401
    h = masuk(klien, "pengamat", "sandi-pengamat-uji-123")
    assert klien.post(jalur, headers=h, json=data).status_code == 403


@pytest.mark.parametrize("data", [{"berita_id": "CTI-999"}, {"berita_id": "<script>"}, {"kolom_asing": 1}])
def test_siarkan_menolak_input_aneh(klien, data):
    assert klien.post("/api/cti/siarkan", headers=masuk(klien), json=data).status_code in (404, 422)


# ---------- radio satpam & korelasi proaktif ----------
def test_berita_terbit_otomatis_berkala(klien):
    h = masuk(klien)
    main.MENARA.osint.berikut = JAM["t"] + 6
    assert potret(klien, h)["cti"]["berita"] == []
    majukan(7)
    k = potret(klien, h)
    assert len(k["cti"]["berita"]) == 1
    assert any(p["jenis"] == "cti" for p in k["peristiwa"])


def test_berita_relevan_menaikkan_aset_ke_waspada_sebelum_serangan(klien):
    h = masuk(klien)
    awal = potret(klien, h)
    assert simpul(awal)["api"]["status"] == "normal"
    r = siarkan(klien, h, "CTI-103").json()
    assert r["korelasi"][0]["id"] == "api"
    k = potret(klien, h)
    api = simpul(k)["api"]
    assert api["status"] == "waspada" and "Waspada proaktif" in api["catatan"]
    assert 80 <= api["prob"] <= 90                     # 0,85 × 0,9 × 1,1 ≈ 84%
    assert k["cti"]["prediksi"][0]["id"] == "api"
    assert k["versi"] > awal["versi"]
    assert not any(l["insiden"] for l in k["layanan"])  # belum ada serangan sama sekali
    serangan = {s["id"]: s for s in k["peta"]["serangan"]}
    assert serangan["cti-CTI-103"]["status"] == "waspada"
    assert serangan["cti-CTI-103"]["asal"]["id"] == "asia_timur"


def test_berita_tidak_relevan_hanya_dicatat(klien):
    h = masuk(klien)
    siarkan(klien, h, "CTI-110")   # VPN SSL port 1194 — satuan tidak punya aset di port ini
    k = potret(klien, h)            # (Fase 6: Modbus/502 kini RELEVAN karena ada aset OT genset)
    assert k["cti"]["prediksi"] == []
    assert any("tidak ada aset dengan port 1194" in p["pesan"] for p in k["peristiwa"])
    assert {s["id"]: s for s in k["peta"]["serangan"]}["cti-CTI-110"]["status"] == "abaikan"


def test_berita_memudar_lalu_kedaluwarsa(klien):
    h = masuk(klien)
    siarkan(klien, h, "CTI-103")
    majukan(110)                                       # kesegaran turun → peluang < 50%
    k = potret(klien, h)
    assert simpul(k)["api"]["status"] == "normal" and simpul(k)["api"]["prob"] < 50
    majukan(25)                                        # lewat ttl 130 detik
    k = potret(klien, h)
    assert k["cti"]["berita"] == [] and simpul(k)["api"]["prob"] is None
    assert any("kedaluwarsa" in p["pesan"] for p in k["peristiwa"])


def test_berita_berlapis_menggabungkan_peluang(klien):
    h = masuk(klien)
    siarkan(klien, h, "CTI-102")
    satu = simpul(potret(klien, h))["rdp"]["prob"]
    main.MENARA.siarkan_berita(main.LAYANAN, "CTI-102")    # siaran ulang = segarkan, bukan dobel
    assert simpul(potret(klien, h))["rdp"]["prob"] == satu


def test_perketat_menurunkan_peluang(klien):
    h = masuk(klien)
    siarkan(klien, h, "CTI-103")
    assert klien.post("/api/soar/perketat", headers=h, json={"aset_id": "api"}).status_code == 200
    api = simpul(potret(klien, h))["api"]
    assert api["status"] == "normal" and api["prob"] < 30
    assert klien.post("/api/soar/perketat", headers=h, json={"aset_id": "api"}).status_code == 409


def test_peringatan_dini_terbukti(klien):
    h = masuk(klien)
    siarkan(klien, h, "CTI-101")   # SMBv3
    majukan(20)
    klien.post("/api/simulasi", headers=h, json={"layanan_id": "kesehatan", "skenario": "ransomware"})
    pesan = [p["pesan"] for p in potret(klien, h)["peristiwa"]]
    assert any("Peringatan dini terbukti" in p and "Berbagi berkas" in p for p in pesan)


# ---------- SOAR ----------
def test_soar_blokir_ip_memutus_kabel_dan_memotong_beban_seketika(klien):
    h = masuk(klien)
    klien.post("/api/simulasi", headers=h, json={"layanan_id": "kesehatan", "skenario": "ddos"})
    majukan(30)
    assert potret(klien, h)["lalu_lintas"]["beban"] >= 85
    # Fase 4: pemutusan tunggal DITOLAK sampai bukti diamankan; sesudahnya langsung boleh (pre-authorized)
    blokir = lambda: klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "kesehatan", "aksi": "blokir_ip"})
    assert blokir().status_code == 409
    assert klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "kesehatan", "aksi": "amankan_bukti"}).status_code == 200
    r = blokir()
    assert r.status_code == 200 and r.json()["ir"]["keparahan"] == "SEV-1"
    k = potret(klien, h)                               # TANPA memajukan jam
    assert k["lalu_lintas"]["beban"] < 60
    kabel = {(c["dari"], c["ke"]): c["status"] for c in k["topologi"]["kabel"]}
    assert kabel[("ancaman", "internet")] == "putus"
    assert {s["id"]: s for s in k["peta"]["serangan"]}["ins-198.51.100.23"]["status"] == "diblokir"
    assert k["soar"]["mttc"]["kesehatan"]["metode"] == "soar"
    assert blokir().status_code == 409                 # sudah dijalankan


def test_soar_menolak_aksi_yang_tidak_cocok(klien):
    h = masuk(klien)
    assert klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "pajak", "aksi": "blokir_ip"}).status_code == 409
    klien.post("/api/simulasi", headers=h, json={"layanan_id": "pajak", "skenario": "ddos"})
    r = klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "pajak", "aksi": "isolasi_otomatis"})
    assert r.status_code == 409


def test_soar_isolasi_bertahap_lalu_pemulihan_lewat_pintu_terpisah(klien):
    h = masuk(klien)
    klien.post("/api/simulasi", headers=h, json={"layanan_id": "imigrasi", "skenario": "ransomware"})
    j = klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "imigrasi", "aksi": "isolasi"}).json()
    # Fase 4: bukti DULU, lalu pemutus (TANPA pulihkan_sistem, F-04)
    assert j["dijadwalkan"] == ["amankan_bukti", "isolasi_otomatis", "amankan_backup"]
    selesai = lambda: next(l for l in potret(klien, h)["layanan"] if l["id"] == "imigrasi")["insiden"]["langkah_selesai"]
    assert selesai() == [True, False, False, False, False, False, False]   # baru bukti; kabel BELUM diputus
    majukan(1.3)
    assert selesai() == [True, True, False, False, False, False, False]    # pemutus pertama
    majukan(1.3)
    assert selesai() == [True, True, True, True, False, False, False]      # pemutus tuntas → laporan → LAPOR
    majukan(10)
    assert selesai()[5] is False                                   # isolasi tidak pernah memulihkan
    pulih = lambda: klien.post("/api/soar/jalankan", headers=h, json={"layanan_id": "imigrasi", "aksi": "pulihkan"})
    assert pulih().status_code == 409                              # "Jangan bayar" belum dicentang
    klien.post("/api/playbook/langkah", headers=h, json={"layanan_id": "imigrasi", "indeks": 4, "selesai": True})
    assert pulih().status_code == 200 and selesai()[5] is True
    assert klien.post("/api/pulihkan", headers=h, json={"layanan_id": "imigrasi"}).status_code == 409
    klien.post("/api/playbook/langkah", headers=h, json={"layanan_id": "imigrasi", "indeks": 6, "selesai": True})
    assert klien.post("/api/pulihkan", headers=h, json={"layanan_id": "imigrasi"}).status_code == 200


# ---------- Peta global ⇄ topologi internal ----------
def test_peta_global_dan_topologi_selalu_sinkron(klien):
    h = masuk(klien)
    klien.post("/api/simulasi", headers=h, json={"layanan_id": "kesehatan", "skenario": "ddos"})
    k = potret(klien, h)
    assert k["peta"]["markas"]["gerbang"] == simpul(k)["fw"]["status"] == "kritis"
    assert k["peta"]["markas"]["status"] == "kritis"
    botnet = [s for s in k["peta"]["serangan"] if s["id"].startswith("bot-")]
    assert len(botnet) >= 3 and all(s["status"] == "kritis" for s in botnet)
    dampak = {d["id"]: d["status"] for d in k["peta"]["dampak"]}
    assert dampak["fw"] == "kritis" and dampak["portal"] == "kritis"


# ---------- siaran: berita yang terbit di tengah jalan sampai ke layar sebagai tambalan ----------
def test_siaran_mengantar_tambalan_saat_berita_terbit(klien):
    tok = klien.post("/api/login", json={"nama": "operator", "sandi": "sandi-operator-uji-123"}).json()["token"]
    KONFIG.umur_siaran_detik = 2.5

    async def kumpulkan():
        async with main.umur_aplikasi(main.app):                  # dapur tunggal menyala
            gen = main._alirkan(tok, "operator")
            pesan = [await gen.__anext__()]
            main.MENARA.osint.berikut = JAM["t"]                  # berita terbit pada detak berikutnya
            pesan += [x async for x in gen]
            return [p.decode() if isinstance(p, bytes) else p for p in pesan]

    pesan = asyncio.run(kumpulkan())
    assert "event: keadaan" in pesan[0]
    tambalan = [p for p in pesan[1:] if "event: tambalan" in p]
    assert tambalan and all("event: keadaan" not in p for p in pesan[1:])
    assert any('"/cti/berita"' in p for p in tambalan)             # berita baru = ralat pada bagian CTI
