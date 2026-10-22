"""
pasang_luring.py — memasang Nusantara Shield TANPA internet dari paket luring (jaringan air-gapped).

Berkas ini ikut di akar paket `nusantara-shield-v5.1-luring-*.zip` (dibuat oleh tools/kemas_luring.py).
Hanya memakai pustaka bawaan Python, jadi bisa dijalankan sebelum apa pun terpasang.

Langkah di posko (Mac/Linux/Windows):
    1. Ekstrak zip, masuk ke foldernya.
    2. Cocokkan sidik jari daftar dengan berita acara serah terima paket:
           python pasang_luring.py --periksa-saja
    3. Pasang:
           python pasang_luring.py
Analogi: sebelum peti logistik dibuka, segel dan daftar isinya dicocokkan dulu dengan berita acara.
Satu berkas saja berbeda, pemasangan dihentikan.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import venv
from pathlib import Path

DAFTAR = "SHA256SUMS"
# Folder yang muncul SETELAH pemasangan atau saat aplikasi berjalan; tidak ikut dicocokkan.
DIABAIKAN = (".venv/", "data/", ".pytest_cache/")


def sidik(jalur: Path) -> str:
    """Sidik jari SHA-256 sebuah berkas."""
    h = hashlib.sha256()
    with open(jalur, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _diabaikan(relatif: str) -> bool:
    return relatif.startswith(DIABAIKAN) or "__pycache__/" in relatif or relatif == DAFTAR


def buat_daftar(akar: Path) -> str:
    """Isi SHA256SUMS: satu baris "<sha256>  <jalur>" per berkas, urut abjad (format sha256sum)."""
    baris = []
    for p in sorted(akar.rglob("*")):
        if p.is_file():
            relatif = p.relative_to(akar).as_posix()
            if not _diabaikan(relatif):
                baris.append(f"{sidik(p)}  {relatif}")
    return "\n".join(baris) + "\n"


def periksa(akar: Path) -> list[str]:
    """Cocokkan isi folder dengan SHA256SUMS. Daftar kosong = semua cocok."""
    berkas_daftar = akar / DAFTAR
    if not berkas_daftar.is_file():
        return [f"{DAFTAR} tidak ditemukan"]
    akar_asli = akar.resolve()
    masalah, tercatat = [], set()
    for no, baris in enumerate(berkas_daftar.read_text(encoding="utf-8").splitlines(), 1):
        if not baris.strip():
            continue
        nilai, _, nama = baris.partition("  ")
        if len(nilai) != 64 or not nama:
            masalah.append(f"baris {no} rusak")
            continue
        jalur = (akar / nama).resolve()
        if akar_asli not in jalur.parents:
            masalah.append(f"jalur di luar paket: {nama}")
            continue
        tercatat.add(nama)
        if not jalur.is_file():
            masalah.append(f"hilang: {nama}")
        elif sidik(jalur) != nilai:
            masalah.append(f"berubah: {nama}")
    for p in akar.rglob("*"):
        if p.is_file():
            relatif = p.relative_to(akar).as_posix()
            if not _diabaikan(relatif) and relatif not in tercatat:
                masalah.append(f"tidak tercatat: {relatif}")
    return sorted(masalah)


def python_venv(akar: Path) -> Path:
    folder = "Scripts" if sys.platform == "win32" else "bin"
    nama = "python.exe" if sys.platform == "win32" else "python"
    return akar / ".venv" / folder / nama


def perintah_pasang(python: Path) -> list[str]:
    """Pemasangan dependensi HANYA dari folder wheels/ (--no-index: pip dilarang menghubungi internet)."""
    return [str(python), "-m", "pip", "install", "--no-index", "--find-links", "wheels", "-r", "requirements.txt"]


def main(argv: list[str] | None = None, akar: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pasang Nusantara Shield tanpa internet.")
    ap.add_argument("--periksa-saja", action="store_true", help="hanya mencocokkan sidik jari, tanpa memasang")
    ap.add_argument("--tanpa-uji", action="store_true", help="lewati uji otomatis setelah pemasangan")
    arg = ap.parse_args(argv)
    akar = akar or Path(__file__).resolve().parent

    print(f"▶ Sidik jari {DAFTAR}: {sidik(akar / DAFTAR) if (akar / DAFTAR).is_file() else '-'}")
    print("  Cocokkan angka ini dengan berita acara serah terima paket sebelum melanjutkan.")
    masalah = periksa(akar)
    if masalah:
        print(f"✖ Paket TIDAK utuh ({len(masalah)} temuan). Pemasangan dihentikan:")
        for m in masalah:
            print("   -", m)
        return 1
    print("✓ Semua berkas cocok dengan daftar sidik jari.")
    if arg.periksa_saja:
        return 0

    print("▶ Membuat .venv …")
    venv.create(akar / ".venv", with_pip=True, clear=True)
    py = python_venv(akar)
    print("▶ Memasang dependensi dari wheels/ (tanpa internet) …")
    if subprocess.call(perintah_pasang(py), cwd=akar) != 0:
        print("✖ Pemasangan dependensi gagal. Pastikan paket dibuat untuk sistem operasi dan versi Python ini.")
        return 1
    if not arg.tanpa_uji:
        print("▶ Menjalankan uji otomatis sebagai bukti pemasangan …")
        if subprocess.call([str(py), "-m", "pytest", "-p", "no:cacheprovider"], cwd=akar) != 0:
            print("✖ Ada uji yang gagal.")
            return 1
    print(f"✓ Selesai. Jalankan server: {python_venv(akar)} -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
