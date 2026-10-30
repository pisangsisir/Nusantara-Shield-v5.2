# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
impor_log.py — Membaca berkas log ASLI yang dibawa Operator (luring), lalu mengubahnya menjadi peristiwa mentah
untuk mesin deteksi aturan (app/deteksi.py). Tidak ada aturan baru di sini: aturan yang sama menilai log latihan
maupun log asli.

Analogi: petugas jaga menyerahkan buku tamu pos lain. Kita tidak menulis ulang bukunya; kita hanya menyalin baris
yang relevan (siapa, dari mana, ke mana, kapan) ke format buku tamu kita, lalu aturan yang sama membacanya.

Format yang dikenali (dipilih otomatis per baris):
1. Log autentikasi OpenSSH (auth.log / secure / journal): "Failed password ... from IP" dan "Accepted ... from IP".
2. Log firewall UFW/iptables (kern.log / ufw.log): baris berisi SRC=, DST=, dan DPT=.
3. CSV berkepala: waktu, jenis (login | koneksi | koneksi_ot | modbus), sumber, lalu kolom sesuai jenis.

Prinsip keamanan dan privasi:
- Sepenuhnya defensif dan luring: modul ini hanya membaca teks yang diserahkan; ia tidak memindai atau menghubungi apa pun.
- Validasi ketat di batas kepercayaan: alamat IP harus sah, port 1–65535, jam 0–23; baris yang tidak dikenali dilewati
  dan dihitung, bukan ditebak.
- Nama akun dalam log TIDAK disimpan (tidak dibutuhkan aturan mana pun). Isi mentah log tidak masuk log audit.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import re
from datetime import datetime, timezone

MAKS_BARIS = 50_000
MAKS_PERISTIWA = 20_000

_BULAN = {b: i for i, b in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_SYSLOG = re.compile(r"^(?P<bln>[A-Z][a-z]{2})\s+(?P<hari>\d{1,2}) (?P<j>\d\d):(?P<m>\d\d):(?P<d>\d\d) \S+ (?P<isi>.*)$")
_ISO = re.compile(r"^(?P<iso>\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?) \S+ (?P<isi>.*)$")
_SSH_GAGAL = re.compile(r"sshd(?:\[\d+\])?: Failed (?:password|publickey|none|keyboard-interactive/pam) for "
                        r"(?:invalid user )?\S+ from (?P<ip>[0-9A-Fa-f:.]+) port \d+")
_SSH_MASUK = re.compile(r"sshd(?:\[\d+\])?: Accepted \S+ for \S+ from (?P<ip>[0-9A-Fa-f:.]+) port \d+")
_FW = re.compile(r"\bSRC=(?P<src>[0-9A-Fa-f:.]+)\b.*\bDST=(?P<dst>[0-9A-Fa-f:.]+)\b.*\bDPT=(?P<dpt>\d+)\b")
JENIS_CSV = ("login", "koneksi", "koneksi_ot", "modbus")


class GalatImpor(ValueError):
    """Berkas tidak bisa dipakai sama sekali (format tidak dikenali, terlalu besar, kosong)."""


def _ip(teks: str) -> str | None:
    try:
        return str(ipaddress.ip_address(teks.strip()))
    except ValueError:
        return None


def _waktu_syslog(m: re.Match, tahun: int) -> float | None:
    try:
        return datetime(tahun, _BULAN[m["bln"]], int(m["hari"]), int(m["j"]), int(m["m"]), int(m["d"])).timestamp()
    except (KeyError, ValueError):
        return None


def _waktu_iso(teks: str) -> float | None:
    teks = teks.strip()
    if re.fullmatch(r"\d{9,11}(?:\.\d+)?", teks):                 # detik epoch
        return float(teks)
    try:
        return datetime.fromisoformat(teks.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _jam_lokal(t: float) -> int:
    return datetime.fromtimestamp(t).hour


def _aset(teks: str | None, aset_by_ip: dict[str, str], aset_dikenal: set[str]) -> str | None:
    if not teks:
        return None
    teks = teks.strip()
    if teks in aset_dikenal:
        return teks
    ip = _ip(teks)
    return aset_by_ip.get(ip) if ip else None


def _baris_teks(baris: str, tahun: int, aset_ssh: str, port_aset: dict[tuple[str, int], str]) -> tuple[float, dict] | None:
    m = _SYSLOG.match(baris)
    t = _waktu_syslog(m, tahun) if m else None
    if not m:
        m = _ISO.match(baris)
        t = _waktu_iso(m["iso"]) if m else None
    if not m or t is None:
        return None
    isi = m["isi"]
    for pola, berhasil in ((_SSH_GAGAL, False), (_SSH_MASUK, True)):
        k = pola.search(isi)
        if k and (ip := _ip(k["ip"])):
            return t, {"jenis": "login", "sumber": ip, "aset": aset_ssh, "berhasil": berhasil}
    k = _FW.search(isi)
    if k and (src := _ip(k["src"])) and (dst := _ip(k["dst"])) and 0 < int(k["dpt"]) < 65536:
        port = int(k["dpt"])
        return t, {"jenis": "koneksi", "sumber": src, "ip": dst, "port": port, "aset": port_aset.get((dst, port))}
    return None


def _baris_csv(r: dict, aset_by_ip: dict[str, str], aset_dikenal: set[str],
               port_aset: dict[tuple[str, int], str]) -> tuple[float, dict] | None:
    jenis, sumber = (r.get("jenis") or "").strip().lower(), _ip(r.get("sumber") or "")
    t = _waktu_iso(r.get("waktu") or "")
    if jenis not in JENIS_CSV or not sumber or t is None:
        return None
    try:
        if jenis == "login":
            aset = _aset(r.get("aset"), aset_by_ip, aset_dikenal)
            berhasil = (r.get("berhasil") or "").strip().lower()
            if not aset or berhasil not in ("ya", "tidak", "true", "false", "1", "0"):
                return None
            return t, {"jenis": "login", "sumber": sumber, "aset": aset, "berhasil": berhasil in ("ya", "true", "1")}
        if jenis == "koneksi":
            ip, port = _ip(r.get("ip") or ""), int(r.get("port") or 0)
            if not ip or not 0 < port < 65536:
                return None
            return t, {"jenis": "koneksi", "sumber": sumber, "ip": ip, "port": port, "aset": port_aset.get((ip, port))}
        aset = _aset(r.get("aset"), aset_by_ip, aset_dikenal)
        if not aset:
            return None
        if jenis == "koneksi_ot":
            return t, {"jenis": "koneksi_ot", "sumber": sumber, "aset": aset}
        fungsi = int(r.get("fungsi") or 0)
        jam = int(r["jam"]) if (r.get("jam") or "").strip() else _jam_lokal(t)
        if not 0 < fungsi < 128 or not 0 <= jam <= 23:
            return None
        return t, {"jenis": "modbus", "sumber": sumber, "aset": aset, "fungsi": fungsi, "jam": jam}
    except (TypeError, ValueError):
        return None


def baca(isi: str, simpul: list[dict], aset_ssh: str = "ssh", tahun: int | None = None) -> tuple[list[tuple[float, dict]], dict]:
    """Teks berkas → ([(waktu epoch, peristiwa mentah)] berurutan waktu, ringkasan). GalatImpor bila tak ada yang dikenali."""
    baris = isi.splitlines()
    if len(baris) > MAKS_BARIS:
        raise GalatImpor(f"Berkas terlalu panjang (lebih dari {MAKS_BARIS:,} baris)".replace(",", "."))
    tahun = tahun or datetime.now(timezone.utc).year
    aset_by_ip = {s["ip"]: s["id"] for s in simpul if s.get("port")}
    aset_dikenal = set(aset_by_ip.values())
    port_aset = {(s["ip"], s["port"]): s["id"] for s in simpul if s.get("port")}
    kepala = baris[0].strip().lower().replace(" ", "") if baris else ""
    hasil: list[tuple[float, dict]] = []
    if kepala.startswith("waktu,") or ",jenis," in kepala:
        format_ = "csv"
        pembaca = csv.DictReader(io.StringIO(isi))
        pembaca.fieldnames = [f.strip().lower() for f in (pembaca.fieldnames or [])]
        jumlah = 0
        for r in pembaca:
            jumlah += 1
            if (x := _baris_csv(r, aset_by_ip, aset_dikenal, port_aset)) is not None:
                hasil.append(x)
    else:
        format_, jumlah = "teks", 0
        for b in baris:
            if not b.strip():
                continue
            jumlah += 1
            if (x := _baris_teks(b, tahun, aset_ssh, port_aset)) is not None:
                hasil.append(x)
        if hasil:
            jenis = {ev["jenis"] for _, ev in hasil}
            format_ = "auth.log (OpenSSH)" if jenis == {"login"} else "firewall (UFW/iptables)" if jenis == {"koneksi"} \
                else "auth.log + firewall"
    if not hasil:
        raise GalatImpor("Tidak ada baris yang dikenali. Format yang didukung: auth.log OpenSSH, log firewall "
                         "UFW/iptables (SRC=, DST=, DPT=), atau CSV berkepala waktu,jenis,sumber,…")
    if len(hasil) > MAKS_PERISTIWA:
        raise GalatImpor(f"Terlalu banyak peristiwa (lebih dari {MAKS_PERISTIWA:,}); pecah berkasnya".replace(",", "."))
    hasil.sort(key=lambda x: x[0])
    return hasil, {"format": format_, "baris": jumlah, "dikenali": len(hasil), "diabaikan": jumlah - len(hasil),
                   "rentang_detik": round(hasil[-1][0] - hasil[0][0])}
