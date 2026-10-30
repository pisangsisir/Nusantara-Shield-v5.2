#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
# ---------------------------------------------------------------------------
# Menjalankan seluruh uji otomatis Nusantara Shield (versi dari app/versi.py) dengan umpan balik PER UJI.
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

VERSI=$(sed -n 's/^VERSI = "\(.*\)"$/\1/p' app/versi.py)
echo "▶ Menjalankan uji otomatis Nusantara Shield v${VERSI} — setiap uji tampil satu baris beserta hasilnya"
"$PY" -m pytest "$@"
