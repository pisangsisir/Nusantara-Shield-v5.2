#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Menjalankan seluruh uji otomatis Nusantara Shield v5.1 dengan umpan balik PER UJI.
#   ./run_tests.sh                 semua uji
#   ./run_tests.sh -k akun         hanya uji yang namanya memuat "akun"
#   ./run_tests.sh tests/test_rantai_bukti.py
#   ./run_tests.sh --lf            ulangi uji yang gagal terakhir kali
# Pengaturan tampilan (-v, ringkasan, uji paling lambat) ada di pytest.ini.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

# Pakai .venv proyek bila ada dan belum aktif
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
if ! "$PY" -m pytest --version >/dev/null 2>&1; then
  echo "✖ pytest belum terpasang di lingkungan ini."
  echo "  Jalankan dulu:  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

echo "▶ Menjalankan uji otomatis Nusantara Shield v5.1 — setiap uji tampil satu baris beserta hasilnya"
"$PY" -m pytest "$@"
