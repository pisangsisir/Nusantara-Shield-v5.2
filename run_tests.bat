@echo off
rem ---------------------------------------------------------------------------
rem Menjalankan seluruh uji otomatis Nusantara Shield v5.1 dengan umpan balik PER UJI (Windows).
rem   run_tests.bat                 semua uji
rem   run_tests.bat -k akun         hanya uji yang namanya memuat "akun"
rem   run_tests.bat --lf            ulangi uji yang gagal terakhir kali
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
chcp 65001 >nul
if not defined VIRTUAL_ENV if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

python -m pytest --version >nul 2>&1
if errorlevel 1 (
  echo pytest belum terpasang di lingkungan ini.
  echo Jalankan dulu:  python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
  exit /b 1
)

echo Menjalankan uji otomatis Nusantara Shield v5.1 - setiap uji tampil satu baris beserta hasilnya
python -m pytest %*
exit /b %ERRORLEVEL%
