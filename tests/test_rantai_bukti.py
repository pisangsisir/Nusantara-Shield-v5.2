"""
Uji KETAT Fase 4 — rantai bukti forensik (chain of custody) & isolasi darurat.

Doktrin yang dikunci uji ini:
  1. Bukti diamankan (SHA-256 + berita acara berantai HMAC) SEBELUM satu kabel pun diputus.
  2. Peladen menolak (409) SETIAP jalan memutus tanpa bukti: tombol isolasi saat bukti gagal, aksi
     tunggal, centang manual, bahkan antrean yang disusupkan. Satu-satunya pengecualian: ISOLASI DARURAT
     dengan alasan tertulis — dan alasan itu tercatat di buku rantai bukti, log audit HMAC, dan laporan.
  3. Pemulihan (tombol, centang manual, tutup insiden) MUTLAK mensyaratkan pencocokan ulang SHA-256.
Jalankan:  pytest -q tests/test_rantai_bukti.py
"""

import re

import pytest
from fastapi.testclient import TestClient

from app import main
from app.audit import LOG, LogAudit
from app.bukti import (BUKTI_DIAMANKAN, BUKTI_DIVERIFIKASI, BUKTI_GAGAL, ISOLASI_DARURAT, VERIFIKASI_GAGAL,
                       RantaiBukti)
from app.data_contoh import PLAYBOOK, PLAYBOOK_RINGKAS
from app.istilah import ISTILAH
from app.keamanan import PEMBATAS
from app.penomoran import PencacahIR
from app.telemetri import SOAR, aksi_berjenis, langkah_bukti, langkah_pemulihan, langkah_pemutus

JAM = {"t": 20000.0}
SKENARIO = [("ransomware", "imigrasi"), ("ddos", "kesehatan"), ("backup_dimatikan", "pajak"), ("sabotase_ot", "listrik")]
ALASAN = "Enkripsi menyebar ke 3 server per menit, agen forensik tidak merespons"
SHA = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(autouse=True)
def bersihkan():
    PEMBATAS.reset()
    main.LAYANAN = main.salin_layanan_awal()
    JAM["t"] = 20000.0
    main.MENARA._jam = lambda: JAM["t"]
    main.MENARA.reset()
    main.MENARA.osint.berikut = 1e12
    asli = main.MENARA.rantai
    # Buku rantai bukti SEGAR per uji, supaya uji perusakan tidak menular ke uji lain.
    main.MENARA.rantai = RantaiBukti(LogAudit("NS_BUKTI_FILE_UJI", "-", "buku uji"), PencacahIR(None))
    yield
    main.MENARA.rantai = asli


@pytest.fixture
def k():
    return TestClient(main.app)


def masuk(k, nama="operator", sandi="sandi-operator-uji-123"):
    j = k.post("/api/login", json={"nama": nama, "sandi": sandi}).json()
    return {"Authorization": f"Bearer {j['token']}"}


def picu(k, h, lid, sk, gangguan=False):
    r = k.post("/api/simulasi", headers=h, json={"layanan_id": lid, "skenario": sk, "gangguan_bukti": gangguan})
    assert r.status_code == 200
    return r


def soar(k, h, lid, aksi):
    return k.post("/api/soar/jalankan", headers=h, json={"layanan_id": lid, "aksi": aksi})


def darurat(k, h, lid, alasan=ALASAN):
    return k.post("/api/soar/darurat", headers=h, json={"layanan_id": lid, "alasan": alasan})


def centang(k, h, lid, i, selesai=True):
    return k.post("/api/playbook/langkah", headers=h, json={"layanan_id": lid, "indeks": i, "selesai": selesai})


def potret(k, h):
    return k.get("/api/telemetri", headers=h).json()


def langkah(k, h, lid):
    return next(l for l in potret(k, h)["layanan"] if l["id"] == lid)["insiden"]["langkah_selesai"]


def buku():
    return main.MENARA.rantai.buku


def halaman(aksi):
    return buku().cari(aksi)


def maju(detik):
    JAM["t"] += detik


# ======================================================================
# 1. Struktur doktrin
# ======================================================================
@pytest.mark.parametrize("sk", list(SOAR))
def test_setiap_playbook_diawali_amankan_bukti_sebelum_pemutusan(sk):
    assert langkah_bukti(sk) == 0
    assert PLAYBOOK[sk][0].startswith("AMANKAN BUKTI") and "SHA-256" in PLAYBOOK[sk][0]
    assert PLAYBOOK_RINGKAS[sk][0] == ISTILAH["langkah_bukti"]
    assert min(langkah_pemutus(sk)) > langkah_bukti(sk)
    assert all(i > langkah_bukti(sk) for i in langkah_pemulihan(sk))


# ======================================================================
# 2. Isolasi standar: bukti DULU, kabel SESUDAHNYA
# ======================================================================
@pytest.mark.parametrize("sk,lid", SKENARIO)
def test_isolasi_standar_mengamankan_bukti_sebelum_memutus(k, sk, lid):
    h = masuk(k)
    picu(k, h, lid, sk)
    r = soar(k, h, lid, "isolasi")
    assert r.status_code == 200 and r.json()["dijadwalkan"][0] == "amankan_bukti"
    pemutus = langkah_pemutus(sk)
    s = langkah(k, h, lid)
    assert s[0] is True and not any(s[i] for i in pemutus)       # bukti ada, kabel BELUM diputus
    e = halaman(BUKTI_DIAMANKAN)
    assert len(e) == 1 and SHA.match(e[0]["detail"]["sha256"]) and len(e[0]["detail"]["barang"]) == 3
    assert all(SHA.match(b["sha256"]) for b in e[0]["detail"]["barang"])
    maju(1.3 * len(pemutus))
    s = langkah(k, h, lid)
    assert all(s[i] for i in pemutus)
    # Urutan di buku peristiwa: catatan bukti lahir sebelum tindakan SOAR pemutus pertama
    peristiwa = [p for p in potret(k, h)["peristiwa"] if p["layanan"] == lid]
    seq_bukti = min(p["seq"] for p in peristiwa if p["jenis"] == "bukti")
    seq_putus = min(p["seq"] for p in peristiwa if p["jenis"] == "soar" and "selesai otomatis" in p["pesan"]
                    and ISTILAH["langkah_bukti"] not in p["pesan"])
    assert seq_bukti < seq_putus
    # Laporan ke manajemen merujuk berita acara bukti
    ir = potret(k, h)["komando"][lid]["ir"]
    assert ir["bukti"]["nomor"] == e[0]["detail"]["nomor"] and ir["bukti"]["hash_buku"] == e[0]["hash"]


# ======================================================================
# 3. SEMUA jalan pintas memutus tanpa bukti ditolak 409 — dan tidak mengubah apa pun
# ======================================================================
@pytest.mark.parametrize("sk,lid", SKENARIO)
def test_aksi_pemutus_tunggal_ditolak_tanpa_bukti(k, sk, lid):
    h = masuk(k)
    picu(k, h, lid, sk)
    for a in aksi_berjenis(sk, "pemutus"):
        r = soar(k, h, lid, a["id"])
        assert r.status_code == 409 and "Bukti forensik belum diamankan" in r.json()["detail"]
    assert not any(langkah(k, h, lid)) and buku().jumlah == 0


@pytest.mark.parametrize("sk,lid", SKENARIO)
def test_centang_manual_pemutus_ditolak_tanpa_bukti(k, sk, lid):
    h = masuk(k)
    picu(k, h, lid, sk)
    for i in sorted(langkah_pemutus(sk)):
        assert centang(k, h, lid, i).status_code == 409
    assert not any(langkah(k, h, lid))


def test_antrean_yang_disusupkan_tetap_tidak_bisa_memutus_tanpa_bukti(k):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware")
    with main._kunci_state:
        main.MENARA._antre_soar.append((JAM["t"], "imigrasi", "isolasi_otomatis"))   # jalan belakang
    s = langkah(k, h, "imigrasi")
    assert s[1] is False
    assert any("dibatalkan: bukti belum diamankan" in p["pesan"] for p in potret(k, h)["peristiwa"])


@pytest.mark.parametrize("sk,lid", SKENARIO)
def test_pemulihan_dan_tutup_insiden_ditolak_tanpa_bukti(k, sk, lid):
    h = masuk(k)
    picu(k, h, lid, sk)
    if langkah_pemulihan(sk):
        assert soar(k, h, lid, "pulihkan").status_code == 409
        assert centang(k, h, lid, min(langkah_pemulihan(sk))).status_code == 409
    assert k.post("/api/pulihkan", headers=h, json={"layanan_id": lid}).status_code == 409


# ======================================================================
# 4. Centang manual "Amankan bukti" = pengambilan bukti sungguhan; tidak bisa dibatalkan
# ======================================================================
def test_centang_bukti_mengambil_bukti_dan_tidak_bisa_dibatalkan(k):
    h = masuk(k)
    picu(k, h, "pajak", "ransomware")
    assert centang(k, h, "pajak", 0).status_code == 200
    e = halaman(BUKTI_DIAMANKAN)
    assert len(e) == 1 and e[0]["aktor"] == "operator" and e[0]["detail"]["metode"] == "manual"
    r = centang(k, h, "pajak", 0, selesai=False)
    assert r.status_code == 409 and "tambah-saja" in r.json()["detail"]
    assert centang(k, h, "pajak", 0).status_code == 409             # tidak ada bukti ganda
    assert len(halaman(BUKTI_DIAMANKAN)) == 1
    assert centang(k, h, "pajak", 1).status_code == 200             # sekarang boleh memutus


# ======================================================================
# 5. ISOLASI DARURAT: hanya bila bukti belum bisa diamankan, alasan wajib, tercatat di tiga tempat
# ======================================================================
def test_bukti_gagal_menahan_isolasi_standar_tanpa_memutus_apa_pun(k):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    r = soar(k, h, "imigrasi", "isolasi")
    assert r.status_code == 409 and ISTILAH["tombol_darurat"] in r.json()["detail"]
    assert not any(langkah(k, h, "imigrasi")) and not main.MENARA._antre_soar
    assert len(halaman(BUKTI_GAGAL)) == 1                          # kegagalan pun masuk berita acara


@pytest.mark.parametrize("alasan", ["", "ok", "   darurat    "])
def test_isolasi_darurat_menolak_alasan_kosong_atau_asal(k, alasan):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    r = darurat(k, h, "imigrasi", alasan)
    assert r.status_code in (409, 422)
    assert not any(langkah(k, h, "imigrasi")) and not halaman(ISOLASI_DARURAT)


def test_isolasi_darurat_terikat_ke_buku_bukti_log_audit_dan_laporan(k):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    assert soar(k, h, "imigrasi", "isolasi").status_code == 409
    r = darurat(k, h, "imigrasi")
    assert r.status_code == 200 and r.json()["dijadwalkan"] == ["isolasi_otomatis", "amankan_backup"]
    assert langkah(k, h, "imigrasi")[1] is True                    # darurat: memutus SEKETIKA
    maju(1.3)
    # (a) buku rantai bukti
    hal = halaman(ISOLASI_DARURAT)
    assert len(hal) == 1 and hal[0]["detail"]["alasan"] == ALASAN and hal[0]["aktor"] == "operator"
    assert hal[0]["detail"]["status_bukti"].startswith("BELUM DIAMANKAN") and buku().entri_utuh(hal[0])
    # (b) log audit HMAC: halaman yang sama dicerminkan, dengan sidik jari buku
    audit = next(e for e in LOG.daftar(50) if e["aksi"] == ISOLASI_DARURAT and e["detail"]["hash_buku"] == hal[0]["hash"])
    assert audit["detail"]["alasan"] == ALASAN and audit["aktor"] == "operator"
    assert LOG.verifikasi()["utuh"]
    # (c) laporan ke manajemen + entri audit laporannya
    ir = potret(k, h)["komando"]["imigrasi"]["ir"]
    assert ir["darurat"]["alasan"] == ALASAN and ir["darurat"]["hash_buku"] == hal[0]["hash"] and ir["bukti"] is None
    e_ir = next(e for e in LOG.daftar(50) if e["aksi"] == "IR_OTOMATIS" and e["detail"]["nomor"] == ir["nomor"])
    assert e_ir["detail"]["darurat_alasan"] == ALASAN and e_ir["detail"]["darurat_hash_buku"] == hal[0]["hash"]
    assert any(ALASAN in p["pesan"] and p["jenis"] == "bukti" for p in potret(k, h)["peristiwa"])


def test_setelah_darurat_pemulihan_tetap_terkunci_sampai_bukti_susulan(k):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    darurat(k, h, "imigrasi")
    maju(1.3)
    centang(k, h, "imigrasi", 4)                                   # "Jangan bayar"
    r = soar(k, h, "imigrasi", "pulihkan")
    assert r.status_code == 409 and "tanpa bukti" in r.json()["detail"]
    assert centang(k, h, "imigrasi", 5).status_code == 409
    # jaringan sudah diputus → beban turun → agen forensik merespons → bukti SUSULAN berhasil
    assert soar(k, h, "imigrasi", "amankan_bukti").status_code == 200
    e = halaman(BUKTI_DIAMANKAN)
    assert len(e) == 1 and e[0]["detail"]["susulan"] is True
    ir = potret(k, h)["komando"]["imigrasi"]["ir"]
    assert ir["bukti"]["nomor"] == e[0]["detail"]["nomor"] and ir["darurat"]["alasan"] == ALASAN   # adendum
    assert soar(k, h, "imigrasi", "pulihkan").status_code == 200
    assert halaman(BUKTI_DIVERIFIKASI)[-1]["detail"]["cocok"] is True


def test_darurat_ditolak_bila_bukti_sudah_aman_atau_sudah_dipakai(k):
    h = masuk(k)
    picu(k, h, "kesehatan", "ddos")
    soar(k, h, "kesehatan", "amankan_bukti")
    r = darurat(k, h, "kesehatan")
    assert r.status_code == 409 and "isolasi standar" in r.json()["detail"]
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    assert darurat(k, h, "imigrasi").status_code == 200
    assert darurat(k, h, "imigrasi").status_code == 409
    assert len(halaman(ISOLASI_DARURAT)) == 1


def test_pengamat_tidak_bisa_memicu_isolasi_darurat(k):
    h = masuk(k)
    picu(k, h, "imigrasi", "ransomware", gangguan=True)
    hp = masuk(k, "pengamat", "sandi-pengamat-uji-123")
    assert darurat(k, hp, "imigrasi").status_code == 403
    assert not halaman(ISOLASI_DARURAT)


# ======================================================================
# 6. Pemulihan MUTLAK mensyaratkan pencocokan hash
# ======================================================================
def _siap_pulih(k, h, lid="imigrasi"):
    picu(k, h, lid, "ransomware")
    soar(k, h, lid, "isolasi")
    maju(2.6)
    centang(k, h, lid, 4)
    return main.MENARA._bukti[lid]["nomor"]


def test_pemulihan_berhasil_mencatat_pencocokan_hash(k):
    h = masuk(k)
    _siap_pulih(k, h)
    assert potret(k, h)["soar"]["syarat_pulih"]["imigrasi"] is None
    assert soar(k, h, "imigrasi", "pulihkan").status_code == 200
    v = halaman(BUKTI_DIVERIFIKASI)
    assert len(v) == 1 and v[0]["detail"]["cocok"] is True and v[0]["detail"]["keperluan"] == "pemulihan"
    assert any(e["aksi"] == BUKTI_DIVERIFIKASI for e in LOG.daftar(10))


@pytest.mark.parametrize("pintu", ["tombol", "centang"])
def test_bukti_dirusak_pemulihan_dikunci_di_semua_pintu(k, pintu):
    h = masuk(k)
    nomor = _siap_pulih(k, h)
    main.MENARA.rantai._uji_rusak_brankas(nomor, "memori_server_berkas.raw")
    syarat = potret(k, h)["soar"]["syarat_pulih"]["imigrasi"]
    assert "TIDAK COCOK" in syarat
    assert potret(k, h)["forensik"]["insiden"]["imigrasi"]["bukti"]["cocok"] is False
    r = soar(k, h, "imigrasi", "pulihkan") if pintu == "tombol" else centang(k, h, "imigrasi", 5)
    assert r.status_code == 409 and "TIDAK COCOK" in r.json()["detail"]
    assert langkah(k, h, "imigrasi")[5] is False


def test_tutup_insiden_tanpa_tombol_pulihkan_juga_mencocokkan_hash(k):
    h = masuk(k)
    picu(k, h, "pajak", "backup_dimatikan")                         # skenario tanpa pemulihan otomatis
    soar(k, h, "pajak", "isolasi")
    maju(1.3)
    for i in range(1, 6):
        centang(k, h, "pajak", i)
    nomor = main.MENARA._bukti["pajak"]["nomor"]
    main.MENARA.rantai._uji_rusak_brankas(nomor, "jejak_login_admin.log")
    r = k.post("/api/pulihkan", headers=h, json={"layanan_id": "pajak"})
    assert r.status_code == 409 and "TIDAK COCOK" in r.json()["detail"]
    assert len(halaman(VERIFIKASI_GAGAL)) == 1
    assert next(l for l in potret(k, h)["layanan"] if l["id"] == "pajak")["insiden"] is not None


def test_halaman_berita_acara_diubah_terdeteksi_dan_pemulihan_dikunci(k):
    h = masuk(k)
    nomor = _siap_pulih(k, h)
    i = next(n for n, e in enumerate(buku()._entri) if e["detail"].get("nomor") == nomor)
    palsu = dict(buku()._entri[i]["detail"], petugas_palsu="penyusup")
    buku()._uji_rusak(i, "detail", palsu)
    assert k.get("/api/bukti", headers=h).json()["verifikasi"]["utuh"] is False
    r = soar(k, h, "imigrasi", "pulihkan")
    assert r.status_code == 409 and "TIDAK COCOK" in r.json()["detail"]


# ======================================================================
# 7. Buku rantai bukti terbuka untuk diperiksa & setiap halamannya dicerminkan ke log audit
# ======================================================================
def test_buku_bukti_tersaji_utuh_dan_dicerminkan_ke_log_audit(k):
    h = masuk(k)
    _siap_pulih(k, h)
    soar(k, h, "imigrasi", "pulihkan")
    j = k.get("/api/bukti", headers=h).json()
    assert j["verifikasi"]["utuh"] is True
    aksi = [e["aksi"] for e in reversed(j["entri"])]
    assert aksi == [BUKTI_DIAMANKAN, BUKTI_DIVERIFIKASI]
    hash_buku = {e["hash"] for e in j["entri"]}
    dicermin = {e["detail"].get("hash_buku") for e in LOG.daftar(50)}
    assert hash_buku <= dicermin
    # dan di log audit, berita acara bukti tercatat SEBELUM laporan otomatis
    log = list(reversed(LOG.daftar(50)))
    i_bukti = max(n for n, e in enumerate(log) if e["aksi"] == BUKTI_DIAMANKAN)
    i_ir = max(n for n, e in enumerate(log) if e["aksi"] == "IR_OTOMATIS")
    assert i_bukti < i_ir
    f = potret(k, h)["forensik"]
    assert f["buku"]["utuh"] is True and f["min_alasan"] == 15
