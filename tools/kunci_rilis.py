# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
kunci_rilis.py — kunci tanda tangan rilis Ed25519 untuk paket pasang Ubuntu 24.04.

Dijalankan HANYA di komputer pembuat rilis (Mac). Analogi: cap dinas. Capnya (kunci privat) disimpan di laci
terkunci milik pembuat rilis dan tidak pernah ikut dikirim; yang dikirim ke posko hanya contoh cap (kunci publik)
dan sidik jarinya, supaya penerima bisa memeriksa keaslian dokumen tanpa bisa membuat cap palsu.

Aturan yang dijaga alat ini:
  - kunci privat disimpan terenkripsi (PKCS#8 + kata sandi minimal 16 karakter), izin berkas 600, di LUAR repo;
  - kunci privat tidak pernah ditimpa, dicetak, atau diterima sebagai argumen baris perintah;
  - kata sandi diketik (tidak tampil di layar dan tidak tersimpan di riwayat shell);
  - setiap tanda tangan langsung diverifikasi ulang; bila gagal, berkas .sig dihapus.

Pemakaian (dari akar repo, di Mac):
    python3 tools/kunci_rilis.py buat                     → kunci privat ~/.nusantara-shield/kunci-rilis.pem,
                                                            kunci publik kunci/kunci-publik-rilis.pem
    python3 tools/kunci_rilis.py tandatangani dist/<paket>/SHA256SUMS   → SHA256SUMS.sig (64 bita)
    python3 tools/kunci_rilis.py sidik-jari kunci/kunci-publik-rilis.pem
Butuh pustaka `cryptography` (ada di requirements.txt bagian pengujian dan rilis).

Sidik jari kunci = SHA-256 atas kunci publik dalam bentuk DER (SubjectPublicKeyInfo); sama dengan
    openssl pkey -pubin -in kunci-publik-rilis.pem -outform DER | sha256sum
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
KUNCI_PRIVAT_BAWAAN = Path.home() / ".nusantara-shield" / "kunci-rilis.pem"
KUNCI_PUBLIK_BAWAAN = AKAR / "kunci" / "kunci-publik-rilis.pem"
SANDI_MINIMAL = 16


class GagalKunci(Exception):
    """Kesalahan yang dilaporkan ke pengguna dengan kode keluar tertentu."""

    def __init__(self, pesan: str, kode: int = 1):
        super().__init__(pesan)
        self.kode = kode


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as e:          # pragma: no cover - lingkungan tanpa cryptography
        raise GagalKunci("pustaka 'cryptography' belum terpasang: pip install cryptography", 2) from e
    return serialization, ed25519


def sidik_jari_kunci(pem: bytes) -> str:
    """SHA-256 atas DER SubjectPublicKeyInfo dari kunci publik PEM (sama dengan perintah openssl di atas)."""
    serialization, ed25519 = _crypto()
    kunci = serialization.load_pem_public_key(pem)
    if not isinstance(kunci, ed25519.Ed25519PublicKey):
        raise GagalKunci("kunci publik bukan Ed25519")
    der = kunci.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def baca_sandi(sandi_berkas: str | None, konfirmasi: bool) -> bytes:
    """Kata sandi dari berkas (otomasi/uji) atau diketik dua kali. Tidak pernah dari argumen."""
    if sandi_berkas:
        baris = Path(sandi_berkas).read_text(encoding="utf-8").splitlines()
        sandi = baris[0] if baris else ""
    else:
        sandi = getpass.getpass("Kata sandi kunci rilis: ")
        if konfirmasi and getpass.getpass("Ulangi kata sandi    : ") != sandi:
            raise GagalKunci("kedua kata sandi tidak sama", 2)
    if konfirmasi and len(sandi) < SANDI_MINIMAL:
        raise GagalKunci(f"kata sandi minimal {SANDI_MINIMAL} karakter", 2)
    if not sandi:
        raise GagalKunci("kata sandi kosong", 2)
    return sandi.encode()


def _di_dalam_repo(jalur: Path) -> bool:
    try:
        jalur.resolve().relative_to(AKAR.resolve())
        return True
    except ValueError:
        return False


def buat(kunci_privat: Path, kunci_publik: Path, sandi: bytes) -> str:
    """Membuat pasangan kunci baru. Mengembalikan sidik jari kunci publik."""
    serialization, ed25519 = _crypto()
    if _di_dalam_repo(kunci_privat):
        raise GagalKunci(f"kunci privat tidak boleh disimpan di dalam repo ({kunci_privat})", 2)
    if kunci_privat.exists():
        raise GagalKunci(f"{kunci_privat} sudah ada; kunci lama tidak akan ditimpa", 2)
    if kunci_publik.exists():
        raise GagalKunci(f"{kunci_publik} sudah ada; pindahkan dulu bila memang ingin mengganti kunci", 2)
    privat = ed25519.Ed25519PrivateKey.generate()
    pem_privat = privat.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.BestAvailableEncryption(sandi))
    pem_publik = privat.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo)
    kunci_privat.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(kunci_privat, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem_privat)
    os.chmod(kunci_privat, 0o600)
    kunci_publik.parent.mkdir(parents=True, exist_ok=True)
    kunci_publik.write_bytes(pem_publik)
    return sidik_jari_kunci(pem_publik)


def _muat_privat(kunci_privat: Path, sandi: bytes):
    serialization, ed25519 = _crypto()
    if not kunci_privat.is_file():
        raise GagalKunci(f"kunci privat tidak ditemukan: {kunci_privat}", 2)
    if os.name == "posix" and kunci_privat.stat().st_mode & 0o077:
        raise GagalKunci(f"izin {kunci_privat} terlalu longgar; jalankan: chmod 600 '{kunci_privat}'", 2)
    try:
        privat = serialization.load_pem_private_key(kunci_privat.read_bytes(), password=sandi)
    except (ValueError, TypeError) as e:
        raise GagalKunci("kata sandi salah atau berkas kunci rusak") from e
    if not isinstance(privat, ed25519.Ed25519PrivateKey):
        raise GagalKunci("kunci privat bukan Ed25519")
    return privat


def _openssl3() -> str | None:
    """Jalur openssl bila versinya OpenSSL 3 (LibreSSL bawaan macOS tidak bisa memverifikasi Ed25519 -rawin)."""
    for calon in (shutil.which("openssl"), "/opt/homebrew/opt/openssl@3/bin/openssl", "/usr/local/opt/openssl@3/bin/openssl"):
        if calon and Path(calon).exists():
            try:
                versi = subprocess.run([calon, "version"], capture_output=True, text=True, timeout=10).stdout
            except (OSError, subprocess.SubprocessError):
                continue
            if versi.startswith("OpenSSL 3"):
                return calon
    return None


def verifikasi_openssl(openssl: str, kunci_publik: Path, berkas: Path, sig: Path) -> bool:
    """Perintah yang sama persis dengan yang dijalankan pasang.sh di Ubuntu."""
    r = subprocess.run([openssl, "pkeyutl", "-verify", "-pubin", "-inkey", str(kunci_publik), "-rawin",
                        "-in", str(berkas), "-sigfile", str(sig)], capture_output=True, text=True)
    return r.returncode == 0


def tandatangani(berkas: Path, kunci_privat: Path, kunci_publik: Path, sandi: bytes) -> tuple[Path, str, bool]:
    """Menandatangani berkas → <berkas>.sig (64 bita mentah). Mengembalikan (jalur sig, sidik jari, diperiksa openssl?)."""
    serialization, _ = _crypto()
    if not berkas.is_file():
        raise GagalKunci(f"berkas tidak ditemukan: {berkas}", 2)
    if not kunci_publik.is_file():
        raise GagalKunci(f"kunci publik tidak ditemukan: {kunci_publik}", 2)
    privat = _muat_privat(kunci_privat, sandi)
    pem_dari_privat = privat.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo)
    sidik = sidik_jari_kunci(kunci_publik.read_bytes())
    if sidik_jari_kunci(pem_dari_privat) != sidik:
        raise GagalKunci("kunci privat ini BUKAN pasangan kunci publik yang diterbitkan "
                         f"({kunci_publik}); tanda tangan tidak dibuat")
    sig = berkas.with_name(berkas.name + ".sig")
    data = berkas.read_bytes()
    sig.write_bytes(privat.sign(data))
    # Verifikasi ulang dengan kunci publik yang DITERBITKAN (bukan kunci di memori), lalu dengan openssl bila ada.
    publik = serialization.load_pem_public_key(kunci_publik.read_bytes())
    try:
        publik.verify(sig.read_bytes(), data)
        openssl = _openssl3()
        diperiksa_openssl = bool(openssl)
        if openssl and not verifikasi_openssl(openssl, kunci_publik, berkas, sig):
            raise GagalKunci("openssl menolak tanda tangan yang baru dibuat")
    except Exception:
        sig.unlink(missing_ok=True)
        raise
    return sig, sidik, diperiksa_openssl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kunci_rilis.py", description="Kunci tanda tangan rilis Ed25519 (sisi pembuat rilis).")
    sub = ap.add_subparsers(dest="perintah", required=True)
    b = sub.add_parser("buat", help="membuat pasangan kunci baru (sekali saja)")
    b.add_argument("--kunci-privat", default=str(KUNCI_PRIVAT_BAWAAN))
    b.add_argument("--kunci-publik", default=str(KUNCI_PUBLIK_BAWAAN))
    b.add_argument("--sandi-berkas", help="baca kata sandi dari baris pertama berkas ini (otomasi/uji)")
    t = sub.add_parser("tandatangani", help="menandatangani berkas (SHA256SUMS) → berkas.sig")
    t.add_argument("berkas")
    t.add_argument("--kunci-privat", default=str(KUNCI_PRIVAT_BAWAAN))
    t.add_argument("--kunci-publik", default=str(KUNCI_PUBLIK_BAWAAN))
    t.add_argument("--sandi-berkas", help="baca kata sandi dari baris pertama berkas ini (otomasi/uji)")
    s = sub.add_parser("sidik-jari", help="mencetak sidik jari kunci publik")
    s.add_argument("pem")
    a = ap.parse_args(argv)
    try:
        if a.perintah == "buat":
            sidik = buat(Path(a.kunci_privat).expanduser(), Path(a.kunci_publik).expanduser(),
                         baca_sandi(a.sandi_berkas, konfirmasi=True))
            print(f"✓ Kunci privat (terenkripsi, izin 600): {Path(a.kunci_privat).expanduser()}")
            print(f"✓ Kunci publik                        : {a.kunci_publik}")
            print(f"  Sidik jari kunci publik: {sidik}")
            print("  Catat sidik jari ini di berita acara. Cadangkan kunci privat ke media luring yang disimpan terpisah;")
            print("  bila kunci privat atau kata sandinya hilang, rilis berikutnya harus memakai kunci baru.")
        elif a.perintah == "tandatangani":
            # Periksa berkas DULU, baru tanya kata sandi: jangan sampai sandi diketik untuk berkas yang tidak ada.
            for jalur, nama in ((Path(a.berkas), "berkas yang ditandatangani"),
                                (Path(a.kunci_publik).expanduser(), "kunci publik"),
                                (Path(a.kunci_privat).expanduser(), "kunci privat")):
                if not jalur.is_file():
                    raise GagalKunci(f"{nama} tidak ditemukan: {jalur} (kata sandi belum ditanyakan)", 2)
            sig, sidik, openssl = tandatangani(Path(a.berkas), Path(a.kunci_privat).expanduser(),
                                               Path(a.kunci_publik).expanduser(), baca_sandi(a.sandi_berkas, False))
            print(f"✓ {sig} ({sig.stat().st_size} bita) · kunci {sidik}")
            print("  Diverifikasi ulang dengan kunci publik yang diterbitkan" +
                  (" dan dengan OpenSSL 3 (perintah yang sama dengan pasang.sh)." if openssl else
                   "; OpenSSL 3 tidak ditemukan di komputer ini, jadi pemeriksaan openssl dilewati."))
        else:
            print(sidik_jari_kunci(Path(a.pem).read_bytes()))
    except GagalKunci as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return e.kode
    except (OSError, ValueError) as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
