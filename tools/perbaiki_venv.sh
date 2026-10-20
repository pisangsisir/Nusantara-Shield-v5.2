#!/usr/bin/env bash
# Membuat ulang .venv bila rusak, misalnya setelah folder proyek dipindah
# (gejala: "cannot execute: No such file or directory", lalu "No module named 'numpy'").
# Penyebab: venv Python mencatat jalur folder secara mutlak, jadi tidak bisa dipindah.
# Pakai: bash tools/perbaiki_venv.sh   (dari folder mana pun)
set -euo pipefail
cd "$(dirname "$0")/.."
deactivate 2>/dev/null || true
if [ -d .venv ]; then rm -rf ./.venv; fi
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.12 python3.11 python3.10 python3; do command -v "$c" >/dev/null && { PY="$c"; break; }; done
fi
[ -n "$PY" ] || { echo "Python 3.10+ tidak ditemukan"; exit 1; }
"$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c "import numpy, sklearn, fastapi; print('OK numpy', numpy.__version__, '| scikit-learn', sklearn.__version__)"
echo "Selesai. Aktifkan dengan: source .venv/bin/activate   lalu: ./run_tests.sh"
