# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
keamanan.py — Lapisan pengaman aplikasi.

Analogi besar: aplikasi ini adalah sebuah kantor.
- Autentikasi        = satpam yang memeriksa kartu tanda pegawai.
- Rate limiting      = antrean bernomor: satu orang tidak boleh menyerobot
                       loket ratusan kali per menit.
- Header keamanan    = stiker "dilarang merekam / dilarang membawa barang
                       dari luar" yang ditempel di setiap pintu ruangan.
- CORS               = daftar alamat kantor lain yang boleh menelepon kita.
- Validasi input     = petugas yang menolak formulir yang diisi ngawur.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


# --------------------------------------------------------------------------
# KONFIGURASI — semua rahasia dibaca dari environment variable, tidak ditulis
# langsung di kode (analogi: kunci brankas tidak ditempel di pintu brankas).
# --------------------------------------------------------------------------
def _daftar(env: str, bawaan: str) -> list[str]:
    return [x.strip() for x in os.getenv(env, bawaan).split(",") if x.strip()]


class Konfigurasi:
    def __init__(self) -> None:
        self.mode_dev = os.getenv("NS_MODE", "dev") == "dev"
        self.origin_diizinkan = _daftar(
            "NS_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
        )
        self.host_diizinkan = _daftar("NS_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
        self.pakai_https = os.getenv("NS_HTTPS", "0") == "1"
        self.masa_berlaku_token_detik = int(os.getenv("NS_TOKEN_TTL", str(8 * 3600)))
        self.batas_body_byte = 16 * 1024  # 16 KB cukup untuk semua formulir aplikasi ini
        # Siaran langsung (telemetri): umur maksimal satu sambungan & jumlah per akun.
        # Sambungan lama ditutup rapi lalu browser menyambung ulang, sehingga tidak ada
        # "sambungan hantu" yang menumpuk dan menghabiskan memori server.
        self.umur_siaran_detik = int(os.getenv("NS_SIARAN_UMUR", "900"))
        self.maks_siaran_per_akun = int(os.getenv("NS_SIARAN_MAKS", "4"))


KONFIG = Konfigurasi()


# --------------------------------------------------------------------------
# AKUN PENGGUNA
# --------------------------------------------------------------------------
# Hanya dua peran (prinsip "hak akses seminimal mungkin"):
#   pengamat : boleh melihat
#   operator : boleh melihat + mengubah (simulasi, pulihkan, ekspor)
PERAN_IZIN = {
    "pengamat": {"lihat"},
    "operator": {"lihat", "ubah", "kelola_akun"},
}


def _hash_sandi(sandi: str, garam: bytes) -> bytes:
    # PBKDF2 = mengaduk kata sandi 200.000 kali agar sulit ditebak paksa.
    return hashlib.pbkdf2_hmac("sha256", sandi.encode(), garam, 200_000)


@dataclass
class Akun:
    nama: str
    peran: str
    garam: bytes
    hash_sandi: bytes
    dibuat: str = ""
    asal: str = "bawaan"      # bawaan (dari environment) | mandiri | kode_undangan | operator


def _muat_akun() -> dict[str, Akun]:
    """Membaca kata sandi dari environment. Kata sandi asli tidak disimpan;
    yang disimpan hanya hasil 'aduknya' (hash)."""
    akun: dict[str, Akun] = {}
    for nama, peran, env in (
        ("operator", "operator", "NS_OPERATOR_PASSWORD"),
        ("pengamat", "pengamat", "NS_VIEWER_PASSWORD"),
    ):
        sandi = os.getenv(env)
        if not sandi:
            if not KONFIG.mode_dev:
                raise RuntimeError(f"{env} wajib diisi di mode produksi")
            # Mode demo: buat sandi acak dan tampilkan SEKALI di terminal.
            sandi = secrets.token_urlsafe(12)
            print(f"[DEMO] Sandi sementara untuk '{nama}': {sandi}  (atur {env} agar tetap)")
        if len(sandi) < 12:
            raise RuntimeError(f"{env} minimal 12 karakter")
        garam = secrets.token_bytes(16)
        akun[nama] = Akun(nama, peran, garam, _hash_sandi(sandi, garam))
    return akun


AKUN = _muat_akun()


# --------------------------------------------------------------------------
# PENDAFTARAN AKUN (Fase 5, temuan audit #7)
# --------------------------------------------------------------------------
# Analogi: kantor punya dua jenis kartu.
#   - Kartu TAMU (pengamat) boleh dibuat sendiri di meja resepsionis: hanya bisa melihat.
#   - Kartu PETUGAS (operator) bisa memutus jaringan, jadi TIDAK boleh dicetak sendiri:
#     harus membawa surat undangan (kode NS_KODE_OPERATOR) atau dibuatkan oleh petugas yang sudah ada.
POLA_NAMA = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
MIN_SANDI = 12
_kunci_akun = threading.Lock()


class GalatAkun(Exception):
    def __init__(self, kode: int, pesan: str) -> None:
        super().__init__(pesan)
        self.kode, self.pesan = kode, pesan


def pendaftaran_pengamat_terbuka() -> bool:
    return os.getenv("NS_DAFTAR_PENGAMAT", "1") == "1"


def kode_operator_sah(kode: str | None) -> bool:
    """Tanpa NS_KODE_OPERATOR di environment, pendaftaran operator mandiri tertutup sama sekali."""
    rahasia = os.getenv("NS_KODE_OPERATOR", "")
    if not rahasia or not kode:
        return False
    return hmac.compare_digest(kode.encode(), rahasia.encode())


def _berkas_akun() -> Path | None:
    jalur = os.getenv("NS_AKUN_FILE")
    if jalur:
        return Path(jalur)
    if os.getenv("NS_AUDIT_KEY"):                   # mode permanen → akun terdaftar ikut permanen
        return Path("data/akun.json")
    return None


def _simpan_akun() -> None:
    """Hanya akun TERDAFTAR yang ditulis (akun bawaan selalu dari environment). Sandi asli tidak
    pernah ditulis: hanya garam + hash PBKDF2. Penulisan atomik (berkas sementara lalu ganti)."""
    berkas = _berkas_akun()
    if not berkas:
        return
    isi = {a.nama: {"peran": a.peran, "garam": a.garam.hex(), "hash": a.hash_sandi.hex(),
                    "dibuat": a.dibuat, "asal": a.asal}
           for a in AKUN.values() if a.asal != "bawaan"}
    berkas.parent.mkdir(parents=True, exist_ok=True)
    sementara = berkas.with_suffix(".tmp")
    sementara.write_text(json.dumps(isi, ensure_ascii=False, indent=1), "utf-8")
    os.chmod(sementara, 0o600)
    os.replace(sementara, berkas)


def muat_akun_terdaftar(berkas: Path | None = None) -> int:
    """Dipanggil saat server menyala. Nama yang bentrok dengan akun bawaan diabaikan."""
    berkas = berkas or _berkas_akun()
    if not berkas or not berkas.exists():
        return 0
    n = 0
    with _kunci_akun:
        for nama, d in json.loads(berkas.read_text("utf-8")).items():
            if nama in AKUN or d.get("peran") not in PERAN_IZIN or not POLA_NAMA.match(nama):
                continue
            AKUN[nama] = Akun(nama, d["peran"], bytes.fromhex(d["garam"]), bytes.fromhex(d["hash"]),
                              d.get("dibuat", ""), d.get("asal", "mandiri"))
            n += 1
    return n


def daftarkan_akun(nama: str, sandi: str, peran: str, asal: str) -> Akun:
    """Membuat akun baru. GalatAkun(422) = isian tidak memenuhi syarat; GalatAkun(409) = nama dipakai.
    Pemeriksaan HAK (siapa boleh membuat operator) dilakukan di loket, sebelum fungsi ini dipanggil."""
    if not POLA_NAMA.match(nama):
        raise GalatAkun(422, "Nama akun 3–20 karakter: huruf kecil, angka, atau garis bawah, diawali huruf")
    if peran not in PERAN_IZIN:
        raise GalatAkun(422, "Peran tidak dikenal")
    if len(sandi) < MIN_SANDI or len(sandi) > 128:
        raise GalatAkun(422, f"Kata sandi minimal {MIN_SANDI} karakter")
    if nama in sandi.lower():
        raise GalatAkun(422, "Kata sandi tidak boleh memuat nama akun")
    garam = secrets.token_bytes(16)
    hash_sandi = _hash_sandi(sandi, garam)               # diaduk DI LUAR kunci: 200.000 putaran itu lambat
    with _kunci_akun:
        if nama in AKUN:
            raise GalatAkun(409, "Nama akun sudah dipakai")
        akun = Akun(nama, peran, garam, hash_sandi,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"), asal)
        AKUN[nama] = akun
        _simpan_akun()
    return akun


muat_akun_terdaftar()          # akun yang didaftarkan sebelum server dinyalakan ulang (mode permanen)

# Hash palsu untuk menyamakan waktu respons bila nama pengguna tidak ada,
# supaya penyerang tidak bisa menebak nama akun dari lamanya jawaban.
_GARAM_PALSU = secrets.token_bytes(16)
_HASH_PALSU = _hash_sandi(secrets.token_urlsafe(16), _GARAM_PALSU)


def periksa_sandi(nama: str, sandi: str) -> Akun | None:
    akun = AKUN.get(nama)
    garam = akun.garam if akun else _GARAM_PALSU
    target = akun.hash_sandi if akun else _HASH_PALSU
    cocok = hmac.compare_digest(_hash_sandi(sandi, garam), target)
    return akun if (akun and cocok) else None


# --------------------------------------------------------------------------
# TOKEN SESI (kartu tamu sementara)
# --------------------------------------------------------------------------
# Setelah login, pengguna menerima token acak. Server hanya menyimpan HASH
# token-nya, jadi bila memori server bocor pun token tidak bisa dipakai ulang.
_sesi: dict[str, tuple[str, float]] = {}  # hash_token -> (nama_akun, kedaluwarsa)
_kunci_sesi = threading.Lock()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def buat_token(akun: Akun) -> str:
    token = secrets.token_urlsafe(32)
    with _kunci_sesi:
        _sesi[_hash_token(token)] = (akun.nama, time.time() + KONFIG.masa_berlaku_token_detik)
    return token


def cabut_token(token: str) -> None:
    with _kunci_sesi:
        _sesi.pop(_hash_token(token), None)


_bearer = HTTPBearer(auto_error=False)


def akun_dari_token(token: str) -> Akun | None:
    """Memeriksa satu token. Dipakai satpam di pintu DAN oleh siaran langsung
    yang memeriksa ulang secara berkala (agar logout langsung memutus siaran)."""
    kunci = _hash_token(token)
    with _kunci_sesi:
        data = _sesi.get(kunci)
        if data and data[1] < time.time():
            _sesi.pop(kunci, None)  # token kedaluwarsa dibuang
            data = None
    return AKUN[data[0]] if data else None


def pengguna_saat_ini(
    kred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Akun:
    """Satpam: setiap permintaan ke API wajib membawa token yang sah."""
    if kred is None or kred.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Perlu login",
                            headers={"WWW-Authenticate": "Bearer"})
    akun = akun_dari_token(kred.credentials)
    if not akun:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesi tidak sah atau kedaluwarsa",
                            headers={"WWW-Authenticate": "Bearer"})
    return akun


class PengelolaSiaran:
    """Menghitung siaran langsung yang sedang terbuka per akun.
    Analogi: satu meja hanya boleh memesan beberapa pelayan pribadi sekaligus."""

    def __init__(self) -> None:
        self._aktif: dict[str, int] = defaultdict(int)
        self._kunci = threading.Lock()

    def masuk(self, nama: str) -> bool:
        with self._kunci:
            if self._aktif[nama] >= KONFIG.maks_siaran_per_akun:
                return False
            self._aktif[nama] += 1
            return True

    def keluar(self, nama: str) -> None:
        with self._kunci:
            self._aktif[nama] = max(0, self._aktif[nama] - 1)

    def jumlah(self, nama: str) -> int:
        with self._kunci:
            return self._aktif[nama]


SIARAN = PengelolaSiaran()


def ringkasan_akun() -> dict:
    """Untuk dasbor operator. 'Aktif' = punya sesi login yang sah (belum keluar & belum kedaluwarsa);
    'memantau' = sedang membuka siaran langsung. Tidak memuat hash, garam, token, maupun alamat IP."""
    sekarang = time.time()
    with _kunci_sesi:
        sesi: dict[str, int] = defaultdict(int)
        for nama, kedaluwarsa in _sesi.values():
            if kedaluwarsa > sekarang:
                sesi[nama] += 1
    daftar = []
    for a in sorted(AKUN.values(), key=lambda a: (a.peran, a.nama)):
        daftar.append({"nama": a.nama, "peran": a.peran, "asal": a.asal, "dibuat": a.dibuat or None,
                       "sesi": sesi.get(a.nama, 0), "siaran": SIARAN.jumlah(a.nama)})
    hitung = {}
    for peran in PERAN_IZIN:
        milik = [d for d in daftar if d["peran"] == peran]
        hitung[peran] = {"terdaftar": len(milik), "aktif": sum(1 for d in milik if d["sesi"]),
                         "memantau": sum(1 for d in milik if d["siaran"])}
    return {"hitung": hitung, "akun": daftar,
            "pendaftaran": {"pengamat_terbuka": pendaftaran_pengamat_terbuka(),
                            "operator_dengan_kode": bool(os.getenv("NS_KODE_OPERATOR"))}}


def _uji_reset_akun() -> None:
    """Hanya untuk pengujian otomatis: hapus akun terdaftar & semua sesi."""
    with _kunci_akun:
        for nama in [n for n, a in AKUN.items() if a.asal != "bawaan"]:
            del AKUN[nama]
    with _kunci_sesi:
        _sesi.clear()


def butuh_izin(izin: str):
    """Pembuat 'gerbang' per izin. Contoh: Depends(butuh_izin('ubah'))."""
    def gerbang(akun: Akun = Depends(pengguna_saat_ini)) -> Akun:
        if izin not in PERAN_IZIN.get(akun.peran, set()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Peran Anda tidak diizinkan")
        return akun
    return gerbang


# --------------------------------------------------------------------------
# RATE LIMITING (antrean bernomor)
# --------------------------------------------------------------------------
# Disimpan di memori saja dan otomatis terlupa (minimisasi data): kita tidak
# menulis alamat IP pengunjung ke berkas mana pun.
class PembatasLaju:
    def __init__(self) -> None:
        self._catatan: dict[tuple[str, str], deque] = defaultdict(deque)
        self._kunci = threading.Lock()

    def izinkan(self, kunci: str, ember: str, batas: int, jendela_detik: int) -> bool:
        sekarang = time.monotonic()
        with self._kunci:
            antre = self._catatan[(kunci, ember)]
            while antre and antre[0] <= sekarang - jendela_detik:
                antre.popleft()
            if len(antre) >= batas:
                return False
            antre.append(sekarang)
            return True

    def reset(self) -> None:
        with self._kunci:
            self._catatan.clear()


PEMBATAS = PembatasLaju()

# (batas permintaan, jendela detik) per kelompok endpoint
ATURAN_LAJU = {
    "login": (5, 60),     # tebak sandi paling banyak 5x per menit
    "daftar": (5, 300),   # Fase 5: pembuatan akun mandiri paling banyak 5x per 5 menit per alamat
    "ubah": (30, 60),     # tindakan yang mengubah data
    "pdf": (5, 60),       # membuat PDF cukup berat
    "umum": (120, 60),    # baca biasa
}


def batasi(ember: str):
    batas, jendela = ATURAN_LAJU[ember]

    def gerbang(request: Request) -> None:
        ip = request.client.host if request.client else "tanpa-ip"
        if not PEMBATAS.izinkan(ip, ember, batas, jendela):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Terlalu banyak permintaan, coba lagi sebentar lagi",
                                headers={"Retry-After": str(jendela)})
    return gerbang


# --------------------------------------------------------------------------
# MIDDLEWARE ASGI MURNI (Fase 2, temuan F-08 & F-15)
# --------------------------------------------------------------------------
# Kenapa bukan BaseHTTPMiddleware lagi? BaseHTTPMiddleware membungkus SETIAP respons (termasuk
# aliran SSE yang hidup berjam-jam) dalam lapisan tugas & antrean tambahan, dan hanya bisa memeriksa
# header Content-Length. Middleware ASGI murni bekerja langsung pada pesan mentah server:
# lebih ringan untuk aliran panjang, dan bisa menghitung byte body yang SEBENARNYA datang.
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)

_HEADER_TETAP: list[tuple[bytes, bytes]] = [
    (b"content-security-policy", CSP.encode()),                 # hanya jalankan skrip milik sendiri
    (b"x-content-type-options", b"nosniff"),                    # jangan menebak-nebak jenis berkas
    (b"x-frame-options", b"DENY"),                              # tidak boleh ditanam di situs lain
    (b"referrer-policy", b"no-referrer"),                       # jangan bocorkan alamat asal
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
]
_HSTS = (b"strict-transport-security", b"max-age=63072000; includeSubDomains")


class HeaderKeamanan:
    """Menempelkan 'stiker' keamanan pada SETIAP respons, termasuk respons 413/400 dari lapisan
    lain (karena middleware ini dipasang paling luar). Tidak menyentuh isi body sama sekali."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        api = scope["path"].startswith("/api/")
        tambahan = _HEADER_TETAP + ([(b"cache-control", b"no-store")] if api else []) \
            + ([_HSTS] if KONFIG.pakai_https else [])
        diganti = {k for k, _ in tambahan} | {b"server"}           # jangan umumkan merek server

        async def kirim(pesan) -> None:
            if pesan["type"] == "http.response.start":
                lama = [(k, v) for k, v in pesan.get("headers", []) if k.lower() not in diganti]
                pesan = {**pesan, "headers": lama + tambahan}
            await send(pesan)

        await self.app(scope, receive, kirim)


_METODE_BERBODY = {"POST", "PUT", "PATCH", "DELETE"}


class BatasBody:
    """Penjaga pintu ukuran kiriman (F-08). Bekerja SEBELUM router/aplikasi melihat permintaan.

    1. Content-Length di atas batas (atau tidak berupa angka) → 413 seketika; 0 byte body dibaca.
       Klien yang mengirim 'Expect: 100-continue' bahkan tidak pernah diberi izin mengunggah.
    2. Tanpa Content-Length (chunked transfer encoding) → body DIPRA-BACA di sini, dihitung per
       potongan. Begitu melewati batas → 413 + 'Connection: close', sisa aliran tidak dibaca dan
       server menutup soketnya. Router tidak pernah dipanggil.
    3. Body yang lolos (≤ batas) diteruskan ke aplikasi dari memori, persis seperti aslinya.
    Memori yang dipakai per permintaan dibatasi ±batas byte, berapa pun besar kiriman penyerang."""

    def __init__(self, app, batas: int) -> None:
        self.app, self.batas = app, batas

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope["headers"])                       # nama header sudah huruf kecil (ASGI)
        panjang = header.get(b"content-length")
        if panjang is not None and (not panjang.isdigit() or int(panjang) > self.batas):
            return await self._tolak(send)
        berbody = (panjang not in (None, b"0") or b"transfer-encoding" in header
                   or scope["method"] in _METODE_BERBODY)
        if not berbody:                                       # GET biasa & aliran SSE: lewat tanpa disentuh
            return await self.app(scope, receive, send)

        potongan: list[bytes] = []
        total = 0
        while True:
            pesan = await receive()
            if pesan["type"] == "http.disconnect":
                return                                        # klien sudah pergi; tidak ada yang dijawab
            isi = pesan.get("body", b"")
            total += len(isi)
            if total > self.batas:
                return await self._tolak(send)                # router TIDAK PERNAH dipanggil
            potongan.append(isi)
            if not pesan.get("more_body", False):
                break

        diserahkan = False

        async def terima():
            nonlocal diserahkan
            if not diserahkan:                                # satu kali: seluruh body yang sudah divalidasi
                diserahkan = True
                return {"type": "http.request", "body": b"".join(potongan), "more_body": False}
            return await receive()                            # sesudahnya: sinyal putus dari klien, dsb.

        await self.app(scope, terima, send)

    @staticmethod
    async def _tolak(send) -> None:
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"connection", b"close")]})
        await send({"type": "http.response.body", "body": b'{"detail":"Kiriman terlalu besar"}'})
