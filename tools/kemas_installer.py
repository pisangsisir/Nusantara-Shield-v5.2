# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
kemas_installer.py — pembuat paket pasang LURING BERTANDA TANGAN untuk Ubuntu 24.04 LTS x86_64.

Dijalankan di komputer pembuat rilis (Mac, terhubung internet) dalam tiga langkah:

    1. python3 tools/kemas_installer.py susun
         → dist/nusantara-shield-<versi>-ubuntu24.04-amd64/ berisi payload.tar.gz (kode + semua wheel Linux),
           manifest.json (SHA-256 setiap berkas di payload), pasang.sh, kunci publik, dan SHA256SUMS.
    2. python3 tools/kunci_rilis.py tandatangani dist/nusantara-shield-<versi>-ubuntu24.04-amd64/SHA256SUMS
         → SHA256SUMS.sig (Ed25519, kunci privat terenkripsi yang hanya ada di Mac pembuat rilis).
    3. python3 tools/kemas_installer.py bungkus dist/nusantara-shield-<versi>-ubuntu24.04-amd64
         → memeriksa tanda tangan, lalu membuat <nama>.tar dan SIDIK-JARI-PAKET-<tanggal>-v<versi>.txt.

Rantai kepercayaan: sidik jari kunci publik (dicatat di berita acara) → SHA256SUMS.sig → SHA256SUMS → manifest.json
dan payload.tar.gz → SHA-256 setiap berkas di dalam payload. pasang.sh di Ubuntu memeriksa seluruh rantai ini
SEBELUM satu berkas pun dari payload diekstrak atau dijalankan.

Target tetap: Ubuntu 24.04 LTS, x86_64, Python 3.12 bawaan Ubuntu (/usr/bin/python3.12). Paket tidak membawa
Python sendiri. Wheel diunduh dengan pip `--only-binary=:all:` untuk platform manylinux x86_64 dan CPython 3.12,
lalu dikunci per versi dan per SHA-256 di persyaratan-terkunci.txt (pip --require-hashes di target).
Payload dibuat deterministik (urutan, cap waktu = waktu commit, pemilik root, mode dinormalkan), jadi dua
pembuatan dari commit dan wheel yang sama menghasilkan sidik jari payload yang sama.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kemas_luring import kebutuhan_untuk  # noqa: E402
from kemas_rilis import AKAR, VERSI, ikut  # noqa: E402

VERSI_BAWAAN = VERSI                 # dari app/versi.py
TARGET = "ubuntu24.04-amd64"
SKEMA = "nusantara-shield/manifest/1"
PYTHON_TARGET = "3.12"
PLATFORM_LINUX = [f"manylinux_2_{n}_x86_64" for n in range(39, 16, -1)] + \
    ["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]
BERKAS_PAKET = ("pasang.sh", "kunci-publik-rilis.pem", "manifest.json", "payload.tar.gz", "BACA-SAYA.txt")
POLA_WHEEL = re.compile(r"^(?P<nama>[A-Za-z0-9_.]+)-(?P<versi>[A-Za-z0-9_.!+]+)(-\d[^-]*)?-[^-]+-[^-]+-[^-]+\.whl$")
POLA_VERSI = re.compile(r"^\d+\.\d+\.\d+$")


class GagalKemas(Exception):
    pass


def sha256(jalur: Path) -> str:
    h = hashlib.sha256()
    with open(jalur, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def nama_paket(versi: str) -> str:
    return f"nusantara-shield-{versi}-{TARGET}"


# ---------------------------------------------------------------- git
def info_git(periksa_bersih: bool) -> dict:
    """Commit sumber paket. Pohon kerja harus bersih, supaya paket = persis isi commit yang tercatat."""
    try:
        status = subprocess.run(["git", "-C", str(AKAR), "status", "--porcelain"], capture_output=True, text=True,
                                check=True).stdout
        commit = subprocess.run(["git", "-C", str(AKAR), "rev-parse", "HEAD"], capture_output=True, text=True,
                                check=True).stdout.strip()
        waktu = int(subprocess.run(["git", "-C", str(AKAR), "log", "-1", "--format=%ct"], capture_output=True,
                                   text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError, ValueError) as e:
        raise GagalKemas("tidak bisa membaca git (paket rilis harus dibuat dari repo git)") from e
    bersih = not status.strip()
    if periksa_bersih and not bersih:
        raise GagalKemas("pohon kerja git tidak bersih: commit atau simpan dulu perubahan, lalu ulangi "
                         "(paket harus sama persis dengan commit yang tercatat)")
    return {"commit": commit, "waktu_commit": waktu, "pohon_kerja_bersih": bersih}


# ---------------------------------------------------------------- wheel
def perintah_unduh(tujuan: Path, kebutuhan: Path) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "download", "-r", str(kebutuhan), "pip", "-d", str(tujuan),
           "--only-binary=:all:", "--implementation", "cp", "--python-version", PYTHON_TARGET,
           "--disable-pip-version-check", "--no-input"]
    for p in PLATFORM_LINUX:
        cmd += ["--platform", p]
    return cmd


def unduh_pip(tujuan: Path, kebutuhan: Path) -> None:
    subprocess.run(perintah_unduh(tujuan, kebutuhan), check=True)


def kunci_persyaratan(folder_wheel: Path) -> str:
    """persyaratan-terkunci.txt: setiap wheel dipaku versi dan SHA-256-nya (pip --require-hashes)."""
    baris, terlihat = [], set()
    for whl in sorted(folder_wheel.glob("*.whl")):
        m = POLA_WHEEL.match(whl.name)
        if not m:
            raise GagalKemas(f"nama wheel tidak dikenali: {whl.name}")
        nama = re.sub(r"[-_.]+", "-", m["nama"]).lower()
        if nama in terlihat:
            raise GagalKemas(f"dua wheel untuk pustaka yang sama: {nama}")
        terlihat.add(nama)
        baris.append(f"{nama}=={m['versi']} --hash=sha256:{sha256(whl)}")
    if "pip" not in terlihat:
        raise GagalKemas("wheel pip tidak ada (dibutuhkan untuk memasang tanpa internet)")
    return "\n".join(baris) + "\n"


# ---------------------------------------------------------------- payload
def tulis_payload(sumber: Path, tujuan: Path, waktu: int) -> dict:
    """tar.gz deterministik: hanya berkas biasa, urut, pemilik root, mtime tetap, mode 644/755, gzip tanpa cap waktu.
    Mengembalikan isi manifest per berkas."""
    isi: dict[str, dict] = {}
    berkas = sorted((p for p in sumber.rglob("*") if p.is_file()), key=lambda p: p.relative_to(sumber).as_posix())
    with open(tujuan, "wb") as mentah, \
            gzip.GzipFile(filename="", mode="wb", fileobj=mentah, mtime=0, compresslevel=9) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in berkas:
            if p.is_symlink():
                raise GagalKemas(f"tautan simbolik tidak boleh masuk paket: {p}")
            relatif = p.relative_to(sumber).as_posix()
            data = p.read_bytes()
            mode = 0o755 if p.stat().st_mode & 0o111 else 0o644
            info = tarfile.TarInfo(relatif)
            info.size, info.mtime, info.mode = len(data), waktu, mode
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(data))
            isi[relatif] = {"sha256": hashlib.sha256(data).hexdigest(), "ukuran": len(data), "mode": f"{mode:04o}"}
    return isi


def tulis_sha256sums(folder: Path) -> str:
    """SHA256SUMS format coreutils (dua spasi) atas semua berkas paket kecuali SHA256SUMS* sendiri."""
    baris = [f"{sha256(p)}  {p.name}" for p in sorted(folder.iterdir())
             if p.is_file() and not p.name.startswith("SHA256SUMS")]
    teks = "\n".join(baris) + "\n"
    (folder / "SHA256SUMS").write_text(teks, encoding="utf-8")
    return teks


def susun(keluar: Path, kunci_publik: Path, versi: str = VERSI_BAWAAN,
          unduh: Callable[[Path, Path], None] = unduh_pip, periksa_git: bool = True,
          git: dict | None = None) -> Path:
    """Langkah 1: menyusun folder paket (belum bertanda tangan). Mengembalikan jalurnya."""
    from kunci_rilis import sidik_jari_kunci          # butuh cryptography hanya di komputer pembuat rilis
    if not POLA_VERSI.match(versi):
        raise GagalKemas(f"versi harus berbentuk X.Y.Z, bukan {versi!r}")
    if not kunci_publik.is_file():
        raise GagalKemas(f"kunci publik tidak ditemukan: {kunci_publik} (buat dulu: python3 tools/kunci_rilis.py buat)")
    pem = kunci_publik.read_bytes()
    if b"PRIVATE" in pem:
        raise GagalKemas("berkas yang diberikan berisi kunci PRIVAT; paket hanya boleh membawa kunci publik")
    sidik_kunci = sidik_jari_kunci(pem)
    git = git or info_git(periksa_git)
    nama = nama_paket(versi)
    folder = keluar / nama
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as sementara:
        isi = Path(sementara) / "payload"
        for p in sorted(x for x in AKAR.rglob("*") if x.is_file() and ikut(x)):
            relatif = p.relative_to(AKAR)
            if relatif.parts[0] in ("wheels",) or relatif.as_posix() in ("SHA256SUMS", "pasang_luring.py"):
                continue                                   # sisa paket luring lama tidak ikut
            tujuan = isi / relatif
            tujuan.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, tujuan)
        if (isi / ".env").exists() or (isi / "data").exists():
            raise GagalKemas(".env atau data/ terdeteksi di payload — dibatalkan")
        (isi / "wheels").mkdir()
        kebutuhan = Path(sementara) / "kebutuhan-linux.txt"
        kebutuhan.write_text(kebutuhan_untuk("manylinux_x86_64"), encoding="utf-8")
        unduh(isi / "wheels", kebutuhan)
        (isi / "persyaratan-terkunci.txt").write_text(kunci_persyaratan(isi / "wheels"), encoding="utf-8")
        (isi / "VERSI").write_text(versi + "\n", encoding="utf-8")
        isi_manifest = tulis_payload(isi, folder / "payload.tar.gz", git["waktu_commit"])
    manifest = {
        "skema": SKEMA, "nama": "nusantara-shield", "versi": versi, "target": TARGET,
        "python": f"/usr/bin/python{PYTHON_TARGET}", "commit": git["commit"],
        "waktu_commit": git["waktu_commit"], "pohon_kerja_bersih": git["pohon_kerja_bersih"],
        "kunci_publik_sha256": sidik_kunci,
        "payload": {"berkas": "payload.tar.gz", "sha256": sha256(folder / "payload.tar.gz"),
                    "ukuran": (folder / "payload.tar.gz").stat().st_size, "jumlah_berkas": len(isi_manifest)},
        "isi": isi_manifest,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    skrip = (AKAR / "installer" / "pasang.sh").read_text(encoding="utf-8")
    if "@@VERSI@@" not in skrip or "@@SIDIK_JARI_KUNCI@@" not in skrip:
        raise GagalKemas("installer/pasang.sh tidak berisi penanda @@VERSI@@/@@SIDIK_JARI_KUNCI@@")
    skrip = skrip.replace("@@VERSI@@", versi).replace("@@SIDIK_JARI_KUNCI@@", sidik_kunci)
    (folder / "pasang.sh").write_text(skrip, encoding="utf-8")
    (folder / "pasang.sh").chmod(0o755)
    (folder / "kunci-publik-rilis.pem").write_bytes(pem)
    baca = (AKAR / "installer" / "BACA-SAYA.txt").read_text(encoding="utf-8")
    (folder / "BACA-SAYA.txt").write_text(baca.replace("@@VERSI@@", versi).replace("@@NAMA@@", nama)
                                          .replace("@@SIDIK_JARI_KUNCI@@", sidik_kunci), encoding="utf-8")
    tulis_sha256sums(folder)
    return folder


# ---------------------------------------------------------------- bungkus
def periksa_tanda_tangan(folder: Path) -> dict:
    """Pemeriksaan yang sama dengan pasang.sh (dengan pustaka cryptography): kunci, tanda tangan, SHA256SUMS, manifest."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from kunci_rilis import sidik_jari_kunci
    hilang = [n for n in (*BERKAS_PAKET, "SHA256SUMS") if not (folder / n).is_file()]
    if hilang:
        raise GagalKemas(f"folder paket {folder} belum lengkap ({', '.join(hilang)} tidak ada): "
                         "jalankan dulu 'python3 tools/kemas_installer.py susun' sampai berhasil")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    pem = (folder / "kunci-publik-rilis.pem").read_bytes()
    if sidik_jari_kunci(pem) != manifest["kunci_publik_sha256"]:
        raise GagalKemas("kunci publik di paket tidak sama dengan yang tercatat di manifest")
    sig = folder / "SHA256SUMS.sig"
    if not sig.is_file():
        raise GagalKemas("SHA256SUMS.sig belum ada: jalankan dulu python3 tools/kunci_rilis.py tandatangani "
                         f"{folder / 'SHA256SUMS'}")
    try:
        serialization.load_pem_public_key(pem).verify(sig.read_bytes(), (folder / "SHA256SUMS").read_bytes())
    except InvalidSignature as e:
        raise GagalKemas("tanda tangan SHA256SUMS TIDAK SAH untuk kunci publik paket") from e
    tercatat = {}
    for baris in (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        nilai, _, nama = baris.partition("  ")
        tercatat[nama] = nilai
    if set(tercatat) != set(BERKAS_PAKET):
        raise GagalKemas(f"SHA256SUMS tidak mencakup tepat berkas paket: {sorted(tercatat)}")
    for nama, nilai in tercatat.items():
        if sha256(folder / nama) != nilai:
            raise GagalKemas(f"{nama} berubah setelah SHA256SUMS dibuat")
    if sha256(folder / "payload.tar.gz") != manifest["payload"]["sha256"]:
        raise GagalKemas("payload.tar.gz tidak sama dengan manifest")
    return manifest


def bungkus(folder: Path) -> tuple[Path, Path]:
    """Langkah 3: memeriksa tanda tangan, lalu membuat .tar luar (tanpa kompresi) dan berkas sidik jari berita acara."""
    folder = folder.resolve()
    manifest = periksa_tanda_tangan(folder)
    tar_luar = folder.parent / f"{folder.name}.tar"
    isi = list(BERKAS_PAKET) + ["SHA256SUMS", "SHA256SUMS.sig"]
    with tarfile.open(tar_luar, "w", format=tarfile.PAX_FORMAT) as tar:
        akar = tarfile.TarInfo(folder.name)
        akar.type, akar.mode, akar.mtime = tarfile.DIRTYPE, 0o755, manifest["waktu_commit"]
        akar.uid = akar.gid = 0
        akar.uname = akar.gname = "root"
        tar.addfile(akar)
        for nama in sorted(isi):
            data = (folder / nama).read_bytes()
            info = tarfile.TarInfo(f"{folder.name}/{nama}")
            info.size, info.mtime = len(data), manifest["waktu_commit"]
            info.mode = 0o755 if nama == "pasang.sh" else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(data))
    tanggal = dt.datetime.now().strftime("%d-%b-%Y").replace("May", "Mei").replace("Aug", "Agu") \
        .replace("Oct", "Okt").replace("Dec", "Des")
    sidik_tar, sidik_sums = sha256(tar_luar), sha256(folder / "SHA256SUMS")
    catatan = folder.parent / f"SIDIK-JARI-PAKET-{tanggal}-v{manifest['versi']}.txt"
    catatan.write_text(f"""SIDIK JARI PAKET NUSANTARA SHIELD v{manifest['versi']} (Ubuntu 24.04 LTS x86_64) — untuk berita acara serah terima
Dibuat dari commit {manifest['commit']}{'' if manifest['pohon_kerja_bersih'] else ' (POHON KERJA TIDAK BERSIH)'}

Berkas paket          : {tar_luar.name} ({tar_luar.stat().st_size / 1_048_576:.1f} MB)
SHA-256 berkas paket  : {sidik_tar}
SHA-256 SHA256SUMS    : {sidik_sums}
Sidik jari kunci rilis: {manifest['kunci_publik_sha256']}
Isi payload           : {manifest['payload']['jumlah_berkas']} berkas, SHA-256 {manifest['payload']['sha256']}

Langkah di komputer Ubuntu 24.04 (tanpa internet), sebagai pengguna dengan hak sudo:
  1. sha256sum {tar_luar.name}
       → harus sama dengan "SHA-256 berkas paket" di atas. Bila beda, JANGAN diekstrak.
  2. tar -xf {tar_luar.name} && cd {folder.name}
  3. openssl pkey -pubin -in kunci-publik-rilis.pem -outform DER | sha256sum
       → harus sama dengan "Sidik jari kunci rilis" di atas.
  4. openssl pkeyutl -verify -pubin -inkey kunci-publik-rilis.pem -rawin -in SHA256SUMS -sigfile SHA256SUMS.sig
       → harus mencetak "Signature Verified Successfully".
  5. sha256sum -c SHA256SUMS            → semua baris "OK".
  6. sudo sh pasang.sh                  → mengulang langkah 3–5 secara otomatis, lalu memeriksa setiap berkas
                                           payload sebelum memasang.
Langkah 3–5 dijalankan manual karena pasang.sh tidak bisa membuktikan keaslian dirinya sendiri: bila paket
dipalsukan, pasang.sh pun bisa ikut dipalsukan. Sidik jari di berita acara inilah jangkar kepercayaannya.
""", encoding="utf-8")
    return tar_luar, catatan


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kemas_installer.py",
                                 description="Paket pasang luring bertanda tangan untuk Ubuntu 24.04 LTS x86_64.")
    sub = ap.add_subparsers(dest="perintah", required=True)
    s = sub.add_parser("susun", help="langkah 1: menyusun folder paket (belum bertanda tangan)")
    s.add_argument("--kunci-publik", default=str(AKAR / "kunci" / "kunci-publik-rilis.pem"))
    s.add_argument("--keluar", default=str(AKAR / "dist"))
    s.add_argument("--versi", default=VERSI_BAWAAN)
    s.add_argument("--izinkan-kotor", action="store_true",
                   help="izinkan pohon kerja git tidak bersih (hanya untuk mencoba; tercatat di manifest)")
    b = sub.add_parser("bungkus", help="langkah 3: memeriksa tanda tangan lalu membuat .tar dan sidik jari berita acara")
    b.add_argument("folder")
    a = ap.parse_args(argv)
    try:
        if a.perintah == "susun":
            folder = susun(Path(a.keluar), Path(a.kunci_publik), a.versi, periksa_git=not a.izinkan_kotor)
            m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            print(f"✓ {folder}")
            print(f"  {m['payload']['jumlah_berkas']} berkas di payload · "
                  f"{m['payload']['ukuran'] / 1_048_576:.1f} MB · commit {m['commit'][:12]}")
            print(f"  Kunci rilis: {m['kunci_publik_sha256']}")
            print("  Berikutnya (kata sandi kunci akan ditanyakan):")
            print(f"    python3 tools/kunci_rilis.py tandatangani '{folder / 'SHA256SUMS'}'")
            print(f"    python3 tools/kemas_installer.py bungkus '{folder}'")
        else:
            tar_luar, catatan = bungkus(Path(a.folder))
            print(f"✓ Tanda tangan sah. {tar_luar} · SHA-256 {sha256(tar_luar)}")
            print(f"✓ {catatan}")
    except GagalKemas as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"GAGAL: perintah {e.cmd[:4]} … berhenti dengan kode {e.returncode}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
