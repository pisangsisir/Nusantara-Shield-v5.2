"""
Ukur beban server untuk N layar pemantau serentak (siaran SSE), dapat diulang siapa saja.

Cara kerja:
1. Menyalakan server (uvicorn, satu proses) di port lokal dengan sandi demo.
2. Membuka N siaran /api/telemetri/siaran sungguhan lewat HTTP. Klien dibagi ke beberapa alamat
   127.0.0.x supaya pembatas laju per alamat tidak menolak (Linux: seluruh 127.0.0.0/8 adalah loopback).
3. Setelah pemanasan, mencatat waktu CPU proses server (user + system) selama jendela ukur.
   CPU % = waktu CPU server ÷ waktu dinding × 100 (100% = satu inti penuh).
4. Skenario "tenang" lalu "serangan" (insiden ransomware + DDoS, latihan AI, latihan deteksi).

Pemakaian (dari akar repo):  python3 tools/ukur_beban.py --layar 300 --detik 60
Butuh: psutil dan httpx (pip install psutil httpx). Klien berjalan di proses terpisah dari server,
jadi angka CPU hanya milik server. Hasil bergantung pada mesin; catat spesifikasinya bersama angkanya.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

AKAR = Path(__file__).resolve().parent.parent
SANDI_OP, SANDI_PG = "sandi-operator-ukur-123", "sandi-pengamat-ukur-123"


def nyalakan(port: int) -> subprocess.Popen:
    env = {**os.environ, "NS_OPERATOR_PASSWORD": SANDI_OP, "NS_VIEWER_PASSWORD": SANDI_PG,
           "NS_SIARAN_MAKS": "100000"}
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                             "--port", str(port), "--log-level", "warning"], cwd=AKAR, env=env)


async def tunggu_siap(dasar: str) -> None:
    async with httpx.AsyncClient() as k:
        for _ in range(100):
            try:
                if (await k.get(dasar + "/api/health")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    raise SystemExit("server tidak menyala")


async def satu_layar(klien: httpx.AsyncClient, dasar: str, token: str, bita: list[int], henti: asyncio.Event):
    async with klien.stream("GET", dasar + "/api/telemetri/siaran",
                            headers={"Authorization": f"Bearer {token}"}, timeout=None) as r:
        r.raise_for_status()
        async for potong in r.aiter_bytes():
            bita[0] += len(potong)
            if henti.is_set():
                return


async def ukur(proses: psutil.Process, bita: list[int], detik: int) -> dict:
    b0, c0, t0 = bita[0], proses.cpu_times(), time.perf_counter()
    await asyncio.sleep(detik)
    b1, c1, t1 = bita[0], proses.cpu_times(), time.perf_counter()
    cpu = (c1.user + c1.system) - (c0.user + c0.system)
    return {"cpu_persen": round(cpu / (t1 - t0) * 100, 2), "mb_per_detik": round((b1 - b0) / (t1 - t0) / 1e6, 3),
            "memori_mb": round(proses.memory_info().rss / 1e6)}


async def utama(a) -> None:
    dasar = f"http://127.0.0.1:{a.port}"
    srv = nyalakan(a.port)
    try:
        await tunggu_siap(dasar)
        proses = psutil.Process(srv.pid)
        async with httpx.AsyncClient() as k:
            token = (await k.post(dasar + "/api/login", json={"nama": "operator", "sandi": SANDI_OP})).json()["token"]
            h = {"Authorization": f"Bearer {token}"}
            await k.post(dasar + "/api/reset-demo", headers=h, json={})
        alamat = [f"127.0.0.{i}" for i in range(2, 2 + max(1, a.layar // 25 + 1))]
        klien = [httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(local_address=ip),
                                   limits=httpx.Limits(max_connections=None, max_keepalive_connections=None))
                 for ip in alamat]
        bita, henti = [0], asyncio.Event()
        tugas = [asyncio.create_task(satu_layar(klien[i % len(klien)], dasar, token, bita, henti))
                 for i in range(a.layar)]
        await asyncio.sleep(a.panas)
        print(f"# {platform.platform()} · {psutil.cpu_count()} inti · Python {platform.python_version()}")
        print(f"# {a.layar} layar, jendela {a.detik} dtk, pemanasan {a.panas} dtk")
        hidup = lambda: sum(not t.done() for t in tugas)
        print("tenang  :", await ukur(proses, bita, a.detik), f"· siaran hidup {hidup()}/{a.layar}")
        async with httpx.AsyncClient() as k:
            for jalur, data in (("/api/simulasi", {"layanan_id": "kesehatan", "skenario": "ransomware"}),
                                ("/api/simulasi", {"layanan_id": "imigrasi", "skenario": "ddos"}),
                                ("/api/ai/latihan", {"aset_id": "genset"}),
                                ("/api/deteksi/latihan", {"jenis": "login_gagal"}),
                                ("/api/deteksi/latihan", {"jenis": "pindai_port"})):
                r = await k.post(dasar + jalur, headers=h, json=data)
                if r.status_code >= 400:
                    print(f"  (lewati {jalur} {data}: {r.status_code})")
        await asyncio.sleep(a.panas)
        print("serangan:", await ukur(proses, bita, a.detik), f"· siaran hidup {hidup()}/{a.layar}")
        henti.set()
        for t in tugas:
            t.cancel()
        await asyncio.gather(*tugas, return_exceptions=True)
        for kl in klien:
            await kl.aclose()
    finally:
        srv.terminate()
        srv.wait(10)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--layar", type=int, default=300)
    ap.add_argument("--detik", type=int, default=60)
    ap.add_argument("--panas", type=int, default=10)
    ap.add_argument("--port", type=int, default=8790)
    asyncio.run(utama(ap.parse_args()))
