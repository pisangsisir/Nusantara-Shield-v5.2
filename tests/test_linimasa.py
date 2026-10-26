"""
Uji linimasa 60 menit, pita anomali AI per aset, dan KPI posko (MTTC, insiden sejak posko aktif).

Prinsip yang dikunci:
- Linimasa selalu 60 titik × 1 menit. Saat posko baru dibuka, isinya DATA LATIHAN berbenih tetap (sama di
  setiap layar dan setiap kali dijalankan), bertanda asal "latihan", tanpa insiden dan tanpa anomali karangan.
- Setiap 60 detik beban nyata posko menjadi satu titik baru bertanda asal "posko"; titik latihan tergeser keluar.
- Pita AI lahir hanya dari penilaian AI di sesi ini, menyebut nama aset dan alasannya, dan tahu apakah masih berlangsung.
- KPI dihitung dari kejadian sebenarnya: insiden yang dimulai dan waktu penahanan yang tercatat (bukan angka tetap).
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.keamanan import PEMBATAS
from app.telemetri import DURASI_LATIHAN_AI, MENIT_LINIMASA

JAM = {"t": 5000.0}


@pytest.fixture(autouse=True)
def bersihkan():
    PEMBATAS.reset()
    main.LAYANAN = main.salin_layanan_awal()
    JAM["t"] = 5000.0
    main.MENARA._jam = lambda: JAM["t"]
    main.MENARA.reset()
    main.MENARA.osint.berikut = 1e12


@pytest.fixture
def k():
    return TestClient(main.app)


def masuk(k):
    j = k.post("/api/login", json={"nama": "operator", "sandi": "sandi-operator-uji-123"}).json()
    return {"Authorization": f"Bearer {j['token']}"}


def potret(k, h):
    return k.get("/api/telemetri", headers=h).json()


def jalan(detik):
    """Majukan jam dalam langkah kecil (mesin waktu memproses paling banyak 48 detak per panggilan)."""
    for _ in range(detik // 20):
        JAM["t"] += 20
        main.MENARA.maju(main.LAYANAN)


def test_posko_baru_berisi_60_menit_data_latihan_yang_bersih(k):
    lm = potret(k, masuk(k))["linimasa"]
    assert len(lm["menit"]) == MENIT_LINIMASA == 60
    assert {m["asal"] for m in lm["menit"]} == {"latihan"}
    assert not any(m["insiden"] or m["ai"] for m in lm["menit"])        # tidak ada kejadian karangan
    assert lm["pita"] == []
    assert all(0 < m["rata"] <= m["puncak"] <= 100 for m in lm["menit"])


def test_data_latihan_berbenih_tetap():
    a = [m["rata"] for m in main.MENARA._linimasa]
    main.MENARA.reset()
    assert [m["rata"] for m in main.MENARA._linimasa] == a


def test_setiap_60_detik_menjadi_satu_titik_posko(k):
    h = masuk(k)
    jalan(40)
    p = potret(k, h)
    assert {m["asal"] for m in p["linimasa"]["menit"]} == {"latihan"}
    assert p["lalu_lintas"]["berjalan"]["detik"] == 40                 # menit berjalan tampil tiap detik
    jalan(20)
    menit = potret(k, h)["linimasa"]["menit"]
    assert len(menit) == 60 and menit[-1]["asal"] == "posko" and menit[-2]["asal"] == "latihan"
    assert 2 <= menit[-1]["rata"] <= menit[-1]["puncak"] <= 100
    jalan(120)
    assert [m["asal"] for m in potret(k, h)["linimasa"]["menit"][-3:]] == ["posko"] * 3


def test_menit_saat_insiden_ditandai(k):
    h = masuk(k)
    assert k.post("/api/simulasi", headers=h, json={"layanan_id": "kesehatan", "skenario": "ransomware"}).status_code == 200
    jalan(60)
    m = potret(k, h)["linimasa"]["menit"][-1]
    assert m["asal"] == "posko" and m["insiden"] is True


def test_pita_ai_menyebut_aset_dan_alasan_lalu_berakhir(k):
    h = masuk(k)
    assert k.post("/api/ai/latihan", headers=h, json={"aset_id": "genset"}).status_code == 200
    pita = potret(k, h)["linimasa"]["pita"]
    assert len(pita) == 1
    b = pita[0]
    assert b["aset"] == "genset" and b["nama"] == "Pengendali genset" and b["alasan"]
    assert b["berlangsung"] is True and b["sampai"] == MENIT_LINIMASA   # indeks 60 = menit berjalan
    jalan(DURASI_LATIHAN_AI + 120)                                       # pola latihan habis, AI kembali wajar
    pita = potret(k, h)["linimasa"]["pita"]
    assert len(pita) == 1 and pita[0]["berlangsung"] is False
    assert pita[0]["sampai"] - pita[0]["dari"] + 1 >= DURASI_LATIHAN_AI // 60   # lebarnya sesuai lamanya anomali


def test_kpi_insiden_dan_mttc_dari_kejadian_sebenarnya(k):
    h = masuk(k)
    kpi = potret(k, h)["kpi"]
    assert kpi["insiden_sejak"] == 0 and kpi["mttc_rata"] is None and kpi["mttc_n"] == 0
    assert kpi["posko_sejak"]
    assert k.post("/api/simulasi", headers=h, json={"layanan_id": "kesehatan", "skenario": "ransomware"}).status_code == 200
    JAM["t"] += 30
    assert k.post("/api/soar/jalankan", headers=h, json={"layanan_id": "kesehatan", "aksi": "isolasi"}).status_code == 200
    JAM["t"] += 5
    p = potret(k, h)
    detik = p["soar"]["mttc"]["kesehatan"]["detik"]
    assert p["kpi"]["insiden_sejak"] == 1 and p["kpi"]["mttc_n"] == 1 and p["kpi"]["mttc_rata"] == detik >= 30
    main.MENARA.reset()                                                  # reset demo = hitungan baru
    assert potret(k, h)["kpi"]["insiden_sejak"] == 0
