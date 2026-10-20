"""
Uji AI lokal — Engine Deteksi Anomali (Isolation Forest, scikit-learn) di app/ai_anomali.py.

Prinsip yang dikunci:
- Model dilatih DI SERVER INI dari profil normal sintetis, dengan benih tetap (hasil dapat diaudit),
  dan bekerja tanpa jaringan sama sekali.
- Lalu lintas wajar tidak memicu alarm palsu; pola tidak wajar menaikkan aset ke WASPADA tanpa
  menunggu kabar CTI (deteksi dini tanpa signature), lengkap dengan ALASAN yang bisa dibaca manusia.
- Skor AI digabung dengan peluang CTI: p = 1 − (1 − p_CTI)(1 − p_AI); Perketat menurunkannya.
- Penilaian 9 aset hanya butuh milidetik dan disimpan (cache) per keadaan.
- Keputusan tetap di tangan manusia: AI hanya menaikkan status, tidak pernah memutus jaringan.
"""

import socket
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ai_anomali, main
from app.ai_anomali import AMBANG_AI, DETEKTOR, DetektorAnomali, ciri_normal, ciri_pola
from app.keamanan import PEMBATAS
from app.telemetri import ASET_BERPORT, SUMBER_AI

JAM = {"t": 9000.0}


@pytest.fixture(autouse=True)
def bersihkan():
    PEMBATAS.reset()
    main.LAYANAN = main.salin_layanan_awal()
    JAM["t"] = 9000.0
    main.MENARA._jam = lambda: JAM["t"]
    main.MENARA.reset()
    main.MENARA.osint.berikut = 1e12        # matikan siaran CTI otomatis: uji yang menentukan


@pytest.fixture
def klien():
    return TestClient(main.app)


def masuk(klien, nama, sandi):
    j = klien.post("/api/login", json={"nama": nama, "sandi": sandi}).json()
    return {"Authorization": f"Bearer {j['token']}"}


@pytest.fixture
def h(klien):
    return masuk(klien, "operator", "sandi-operator-uji-123")


def potret(klien, h):
    return klien.get("/api/telemetri", headers=h).json()


def simpul(k):
    return {s["id"]: s for s in k["topologi"]["simpul"]}


def prediksi(k):
    return {p["id"]: p for p in k["cti"]["prediksi"]}


def test_model_dilatih_lokal_dengan_benih_tetap_dan_hasilnya_dapat_diaudit():
    a, b = DetektorAnomali(), DetektorAnomali()
    ciri = {"genset": ciri_pola("modbus_tulis_asing"), "db": ciri_normal("db")}
    assert {k: v.skor for k, v in a.nilai(ciri).items()} == {k: v.skor for k, v in b.nilai(ciri).items()}
    r = DETEKTOR.ringkasan()
    assert r["luring"] is True and r["pohon"] == 100 and r["fitur"] == 6
    assert "Isolation Forest" in r["model"]


def test_lalu_lintas_wajar_tidak_memicu_alarm_palsu(klien, h):
    skor = DETEKTOR.nilai({aid: ciri_normal(aid) for aid in ASET_BERPORT})
    assert all(not v.anomali and v.skor < AMBANG_AI for v in skor.values())
    k = potret(klien, h)
    assert k["cti"]["prediksi"] == []
    assert all(s["status"] == "normal" for s in k["topologi"]["simpul"] if s["port"] and s["id"] != "rdp")
    assert k["cti"]["ai"]["aset_anomali"] == 0


def test_latihan_modbus_menaikkan_genset_ke_waspada_tanpa_kabar_cti(klien, h):
    r = klien.post("/api/ai/latihan", headers=h, json={"aset_id": "genset"})
    assert r.status_code == 200
    j = r.json()
    assert j["pola"] == "modbus_tulis_asing" and j["anomali"] and j["skor"] >= AMBANG_AI
    assert "perintah tulis Modbus" in j["alasan"]                  # explainability: alasan bisa dibaca
    k = potret(klien, h)
    g = simpul(k)["genset"]
    assert g["status"] == "waspada" and SUMBER_AI in g["catatan"] and g["prob"] >= 50
    p = prediksi(k)["genset"]
    assert p["sumber"] == [SUMBER_AI] and p["ai"]["skor"] >= AMBANG_AI
    assert [i for i, s in simpul(k).items() if SUMBER_AI in s["catatan"]] == ["genset"]   # aset lain tetap wajar
    assert not any(l["insiden"] for l in k["layanan"])           # peringatan dini: belum ada serangan
    assert any("AI lokal ▶" in e["pesan"] and "Pengendali genset" in e["pesan"] for e in k["peristiwa"])


def test_skor_ai_digabung_dengan_peluang_cti(klien, h):
    p_cti = klien.post("/api/cti/siarkan", headers=h, json={"berita_id": "CTI-109"}).json()["korelasi"][0]["persen"]
    main.MENARA.osint.berikut = 1e12
    klien.post("/api/ai/latihan", headers=h, json={"aset_id": "genset"})
    p = prediksi(potret(klien, h))["genset"]
    p_ai = p["ai"]["persen"]
    harapan = 100 * (1 - (1 - p_cti / 100) * (1 - p_ai / 100))
    assert set(p["sumber"]) == {"CTI-109", SUMBER_AI}
    assert abs(p["persen"] - harapan) <= 1 and p["persen"] > max(p_cti, p_ai)


def test_perketat_menurunkan_peluang_ai_di_bawah_ambang(klien, h):
    klien.post("/api/ai/latihan", headers=h, json={"aset_id": "genset"})
    assert klien.post("/api/soar/perketat", headers=h, json={"aset_id": "genset"}).status_code == 200
    g = simpul(potret(klien, h))["genset"]
    assert g["status"] == "normal" and g["prob"] < 50


def test_penilaian_dalam_milidetik_dan_disimpan_per_keadaan():
    d = DetektorAnomali()
    ciri = {aid: ciri_normal(aid) for aid in ASET_BERPORT}
    ciri["genset"] = ciri_pola("modbus_tulis_asing")
    mulai = time.perf_counter()
    pertama = d.nilai(ciri)
    durasi_ms = (time.perf_counter() - mulai) * 1000
    assert durasi_ms < 100 and d.skor_ms < 100                    # 9 aset dinilai dalam hitungan milidetik
    mulai = time.perf_counter()
    assert d.nilai(dict(ciri)) is pertama                         # keadaan sama → tidak dihitung ulang
    assert (time.perf_counter() - mulai) * 1000 < 5


def test_ai_berjalan_luring_tanpa_satu_pun_koneksi_jaringan(monkeypatch):
    def tolak(*a, **kw):
        raise AssertionError("AI lokal mencoba membuka koneksi jaringan")
    monkeypatch.setattr(socket, "socket", tolak)
    monkeypatch.setattr(socket, "create_connection", tolak)
    d = DetektorAnomali()                                         # dilatih ulang tanpa jaringan
    assert d.nilai({"genset": ciri_pola("modbus_tulis_asing")})["genset"].anomali
    sumber = Path(ai_anomali.__file__).read_text(encoding="utf-8")
    for terlarang in ("import requests", "urllib", "http.client", "httpx", "socket", "ollama"):
        assert terlarang not in sumber


def test_latihan_ai_hanya_untuk_operator_dan_pola_harus_dikenal(klien, h):
    hp = masuk(klien, "pengamat", "sandi-pengamat-uji-123")
    assert klien.post("/api/ai/latihan", headers=hp, json={"aset_id": "genset"}).status_code == 403
    assert klien.post("/api/ai/latihan", headers=h, json={"aset_id": "genset", "pola": "serang"}).status_code == 422
    assert klien.post("/api/ai/latihan", headers=h, json={"aset_id": "bukan-aset"}).status_code == 422


def test_insiden_terbaca_ai_dengan_alasan_tetapi_status_tetap_ditentukan_playbook(klien, h):
    assert klien.post("/api/simulasi", headers=h,
                      json={"layanan_id": "kesehatan", "skenario": "ransomware"}).status_code == 200
    JAM["t"] += 1
    k = potret(klien, h)
    assert any("AI lokal ▶" in e["pesan"] and "operasi tulis berkas" in e["pesan"] for e in k["peristiwa"])
    assert not any(p["ai"] for p in k["cti"]["prediksi"])          # aset insiden diurus playbook, bukan prediksi
    assert k["cti"]["ai"]["aset_anomali"] >= 1


def test_latihan_berakhir_dan_ai_mencatat_lalu_lintas_kembali_wajar(klien, h):
    klien.post("/api/ai/latihan", headers=h, json={"aset_id": "genset"})
    JAM["t"] += 301
    k = potret(klien, h)
    assert simpul(k)["genset"]["status"] == "normal"
    assert any("kembali wajar" in e["pesan"] for e in k["peristiwa"])
