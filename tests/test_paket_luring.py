"""
Uji paket pasang luring (tools/kemas_luring.py dan tools/pasang_luring.py).

Prinsip yang dikunci:
- Daftar sidik jari SHA256SUMS mencakup setiap berkas paket; satu bait saja berubah, pemeriksaan gagal.
- Berkas yang hilang, berkas selundupan, dan jalur yang keluar dari folder paket semuanya ketahuan.
- Pemasangan dependensi memakai --no-index: pip dilarang menghubungi internet.
- Paket tidak pernah membawa .env, .venv, atau data runtime.
Uji ini berjalan tanpa internet; unduhan wheels diganti berkas tiruan.
"""

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import kemas_luring  # noqa: E402
import pasang_luring  # noqa: E402
from pasang_luring import DAFTAR, buat_daftar, periksa  # noqa: E402


@pytest.fixture
def paket(tmp_path):
    akar = tmp_path / "paket"
    (akar / "app").mkdir(parents=True)
    (akar / "wheels").mkdir()
    (akar / "app" / "main.py").write_text("print('halo')\n", encoding="utf-8")
    (akar / "wheels" / "contoh-1.0-py3-none-any.whl").write_bytes(b"isi wheel tiruan")
    (akar / DAFTAR).write_text(buat_daftar(akar), encoding="utf-8")
    return akar


def test_paket_utuh_lolos_pemeriksaan(paket):
    assert periksa(paket) == []
    baris = (paket / DAFTAR).read_text(encoding="utf-8").splitlines()
    assert [b.split("  ", 1)[1] for b in baris] == ["app/main.py", "wheels/contoh-1.0-py3-none-any.whl"]


def test_satu_bait_berubah_langsung_ditolak(paket):
    p = paket / "wheels" / "contoh-1.0-py3-none-any.whl"
    p.write_bytes(p.read_bytes()[:-1] + b"X")
    assert periksa(paket) == ["berubah: wheels/contoh-1.0-py3-none-any.whl"]
    assert pasang_luring.main(["--periksa-saja"], akar=paket) == 1     # pemasang berhenti


def test_pemasang_menerima_paket_utuh(paket):
    assert pasang_luring.main(["--periksa-saja"], akar=paket) == 0


def test_berkas_hilang_selundupan_dan_jalur_keluar_ketahuan(paket):
    (paket / "app" / "main.py").unlink()
    (paket / "app" / "pintu_belakang.py").write_text("x = 1\n", encoding="utf-8")
    with open(paket / DAFTAR, "a", encoding="utf-8") as f:
        f.write("0" * 64 + "  ../di-luar.txt\n")
    assert periksa(paket) == ["hilang: app/main.py", "jalur di luar paket: ../di-luar.txt",
                              "tidak tercatat: app/pintu_belakang.py"]


def test_folder_hasil_pemasangan_tidak_dianggap_selundupan(paket):
    (paket / ".venv" / "bin").mkdir(parents=True)
    (paket / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (paket / "data").mkdir()
    (paket / "data" / "audit_log.jsonl").write_text("{}\n", encoding="utf-8")
    assert periksa(paket) == []


def test_pemasangan_dependensi_dilarang_menghubungi_internet():
    cmd = pasang_luring.perintah_pasang(Path("py"))
    assert "--no-index" in cmd and cmd[cmd.index("--find-links") + 1] == "wheels"
    unduh = kemas_luring.perintah_unduh(Path("w"), "win_amd64", "3.12")
    assert "--only-binary=:all:" in unduh and unduh[unduh.index("--platform") + 1] == "win_amd64"


def test_paket_lengkap_tanpa_rahasia_dan_lolos_pemeriksaan(tmp_path):
    def unduh_tiruan(tujuan, platform, python):
        (tujuan / "numpy-0-cp312-none-any.whl").write_bytes(b"tiruan")

    zip_jalur = kemas_luring.kemas(tmp_path / "dist", "manylinux2014_x86_64", "3.12", unduh=unduh_tiruan)
    with zipfile.ZipFile(zip_jalur) as z:
        nama = z.namelist()
        z.extractall(tmp_path / "ekstrak")
    akar = tmp_path / "ekstrak" / zip_jalur.stem
    relatif = {n.split("/", 1)[1] for n in nama}
    assert {"pasang_luring.py", DAFTAR, "app/main.py", "requirements.txt",
            "wheels/numpy-0-cp312-none-any.whl"} <= relatif
    assert not any(r == ".env" or r.startswith((".venv/", "data/", "dist/")) or "__pycache__" in r for r in relatif)
    assert periksa(akar) == []


def test_kebutuhan_lintas_sistem_operasi_disesuaikan_target():
    assert "uvicorn[standard]" in kemas_luring.kebutuhan_untuk(None)
    win = kemas_luring.kebutuhan_untuk("win_amd64")
    assert "uvicorn[standard]" not in win and "uvicorn" in win and "colorama" in win
    mac = kemas_luring.kebutuhan_untuk("macosx_11_0_arm64")
    assert "uvicorn[standard]" not in mac and "colorama" not in mac and "scikit-learn" in mac

