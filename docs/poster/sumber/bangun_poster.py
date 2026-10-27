"""Bangun poster A4 Nusantara Shield: templat + ikon Lucide (ISC) disematkan sebagai sprite SVG sebaris,
ditambah logo dari docs/logo/simbol.svg.
Pemakaian: python3 bangun_poster.py <folder lucide-static/icons> <keluaran.html>"""
import random
import re
import sys
from pathlib import Path

IKON_DIR, KELUAR = Path(sys.argv[1]), Path(sys.argv[2])
TEMPLAT = Path(__file__).with_name("poster_templat.html").read_text(encoding="utf-8")

# ---------------------------------------------------------------- sprite ikon
dipakai = sorted(set(re.findall(r"\{\{i:([a-z0-9-]+)\}\}", TEMPLAT)))
simbol = []
for nama in dipakai:
    svg = (IKON_DIR / f"{nama}.svg").read_text(encoding="utf-8")
    isi = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    isi = re.sub(r"\s+", " ", isi).strip()
    simbol.append(f'<symbol id="i-{nama}" viewBox="0 0 24 24">{isi}</symbol>')
sprite = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true">'
          '<!-- Ikon: Lucide v0.460.0 (lisensi ISC), disematkan agar luring -->' + "".join(simbol) + "</svg>")
html = re.sub(r"\{\{i:([a-z0-9-]+)\}\}", r'<svg class="ik" aria-hidden="true"><use href="#i-\1"/></svg>', TEMPLAT)


# ---------------------------------------------------------------- ilustrasi jaringan abstrak (deterministik)
def jaringan(lebar, tinggi, n, benih, hub=None):
    acak = random.Random(benih)
    titik = [(acak.uniform(8, lebar - 8), acak.uniform(8, tinggi - 8)) for _ in range(n)]
    if hub:
        titik[0] = hub
    garis = []
    for i, (x1, y1) in enumerate(titik):
        dekat = sorted(range(len(titik)), key=lambda j: (titik[j][0] - x1) ** 2 + (titik[j][1] - y1) ** 2)[1:3]
        for j in dekat:
            if i < j or i not in sorted(range(len(titik)), key=lambda k: (titik[k][0] - titik[j][0]) ** 2 + (titik[k][1] - titik[j][1]) ** 2)[1:3]:
                garis.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{titik[j][0]:.0f}" y2="{titik[j][1]:.0f}"/>')
    if hub:
        for k in range(1, min(7, n)):
            garis.append(f'<line class="tebal" x1="{hub[0]:.0f}" y1="{hub[1]:.0f}" x2="{titik[k][0]:.0f}" y2="{titik[k][1]:.0f}"/>')
    bulat = []
    for k, (x, y) in enumerate(titik):
        kelas = "hub" if hub and k == 0 else ("kuning" if k % 9 == 4 else ("merah" if k % 13 == 7 else ""))
        r = 4.2 if kelas == "hub" else (2.4 if kelas else 1.7)
        bulat.append(f'<circle class="{kelas}" cx="{x:.0f}" cy="{y:.0f}" r="{r}"/>')
    return "".join(dict.fromkeys(garis)) + "".join(bulat)


html = html.replace("{{jaringan_atas}}", jaringan(430, 250, 34, 7, hub=(300, 110)))
html = html.replace("{{jaringan_bawah}}", jaringan(780, 70, 40, 11))
html = html.replace("{{sprite}}", sprite)
# Logo v2 dari docs/logo/simbol.svg (satu sumber untuk aplikasi, dek, dan poster)
logo = (Path(__file__).resolve().parents[2] / "logo" / "simbol.svg").read_text(encoding="utf-8")
logo = re.sub(r"<!--.*?-->|<title>.*?</title>", "", logo, flags=re.S)
logo = re.sub(r"<svg[^>]*>", '<svg class="logo" viewBox="0 0 512 512" aria-hidden="true">', logo, count=1)
html = html.replace("{{logo}}", re.sub(r"\s+", " ", logo).strip())
assert "{{" not in html, re.findall(r"\{\{[^}]*\}\}", html)
KELUAR.write_text(html, encoding="utf-8")
print("ikon:", len(dipakai), "·", KELUAR)
