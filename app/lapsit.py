# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Nusantara Shield Team. Dikembangkan untuk Kartika Cyber Hackathon 2026.
# Dilisensikan di bawah GNU General Public License v3.0; lihat berkas LICENSE.
"""
lapsit.py — Membuat laporan situasi dalam format PDF (label resmi diambil dari kamus istilah).

Analogi: notulen rapat darurat yang dicetak otomatis. Isinya ringkasan
status semua layanan, insiden yang sedang berjalan, dan bukti bahwa buku
catatan audit masih utuh.

Kop laporan: logo Nusantara Shield digambar sebagai VEKTOR langsung dari static/logo.svg (satu sumber dengan dasbor),
tanpa pustaka tambahan dan tanpa internet. Kop memakai identitas proyek sendiri; sengaja tidak meniru kop surat,
lambang, atau stempel instansi mana pun. Setiap halaman memuat nomor laporan dan "Halaman x dari y".
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .istilah import ISTILAH, nama_manajemen
from .mitre import ringkas as ringkas_mitre

WARNA_STATUS = {"hijau": colors.HexColor("#1f8a4c"),
                "kuning": colors.HexColor("#b7791f"),
                "merah": colors.HexColor("#c0392b")}


LOGO_SVG = Path(__file__).resolve().parent.parent / "static" / "logo.svg"
NAVY = colors.HexColor("#0A1120")
HIJAU = colors.HexColor("#1F8A4C")       # hijau merek versi cetak (neon #3EF0A1 terlalu pucat di kertas putih)
ABU = colors.HexColor("#5A6678")
_TOKEN = re.compile(r"[MLCQVHZ]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _jalur(c, d: str):
    """Data jalur SVG (perintah absolut M L C Q V H Z, cukup untuk logo kita) → objek jalur ReportLab."""
    tok = _TOKEN.findall(d)
    p, i, x, y, perintah = c.beginPath(), 0, 0.0, 0.0, None
    angka = lambda: float(tok[i])
    while i < len(tok):
        if tok[i].isalpha():
            perintah, i = tok[i], i + 1
            if perintah == "Z":
                p.close()
            continue
        if perintah in ("M", "L"):
            x, y = angka(), float(tok[i + 1]); i += 2
            (p.moveTo if perintah == "M" else p.lineTo)(x, y)
            perintah = "L" if perintah == "M" else perintah
        elif perintah == "V":
            y = angka(); i += 1; p.lineTo(x, y)
        elif perintah == "H":
            x = angka(); i += 1; p.lineTo(x, y)
        elif perintah == "C":
            v = [float(s) for s in tok[i:i + 6]]; i += 6
            p.curveTo(*v); x, y = v[4], v[5]
        elif perintah == "Q":                    # kuadrat → kubik
            qx, qy, ex, ey = (float(s) for s in tok[i:i + 4]); i += 4
            p.curveTo(x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey), ex, ey)
            x, y = ex, ey
        else:
            raise ValueError(f"perintah jalur tidak didukung: {perintah}")
    return p


def gambar_logo(c, x: float, y: float, ukuran: float) -> bool:
    """Gambar logo di kotak persegi (x, y = sudut kiri bawah). False bila berkas logo tidak terbaca (kop tetap jadi)."""
    try:
        akar = ET.parse(LOGO_SVG).getroot()
    except (OSError, ET.ParseError):
        return False
    ns = "{http://www.w3.org/2000/svg}"
    lebar = float(akar.get("viewBox", "0 0 512 512").split()[2])
    c.saveState()
    c.translate(x, y + ukuran)
    c.scale(ukuran / lebar, -ukuran / lebar)                     # sumbu y SVG ke bawah, PDF ke atas

    def lukis(el, warisan: dict):
        a = {**warisan, **{k: v for k, v in el.attrib.items() if k in (
            "fill", "stroke", "stroke-width", "stroke-opacity", "fill-opacity", "stroke-linecap")}}
        tag = el.tag.replace(ns, "")
        if tag in ("svg", "g"):
            for anak in el:
                lukis(anak, a)
            return
        if tag not in ("path", "rect", "circle"):
            return
        isi = a.get("fill", "#000000") not in ("none",)
        garis = a.get("stroke", "none") != "none" and float(a.get("stroke-width", "1")) > 0
        if isi:
            c.setFillColor(colors.HexColor(a.get("fill", "#000000")))
            c.setFillAlpha(float(a.get("fill-opacity", "1")))
        if garis:
            c.setStrokeColor(colors.HexColor(a["stroke"]))
            c.setStrokeAlpha(float(a.get("stroke-opacity", "1")))
            c.setLineWidth(float(a.get("stroke-width", "1")))
            c.setLineJoin(1)
            c.setLineCap(1 if a.get("stroke-linecap") == "round" else 0)
        if tag == "path":
            c.drawPath(_jalur(c, el.get("d", "")), stroke=int(garis), fill=int(isi))
        elif tag == "rect":
            c.rect(float(el.get("x")), float(el.get("y")), float(el.get("width")), float(el.get("height")),
                   stroke=int(garis), fill=int(isi))
        else:
            c.circle(float(el.get("cx")), float(el.get("cy")), float(el.get("r")), stroke=int(garis), fill=int(isi))

    try:
        lukis(akar, {})
    except (ValueError, TypeError, IndexError):
        c.restoreState()
        return False
    c.restoreState()
    return True


class _KanvasBernomor(rl_canvas.Canvas):
    """Kanvas yang menunda penulisan halaman agar kaki halaman bisa memuat "Halaman x dari y"."""

    def __init__(self, *a, kop=None, **kw):
        super().__init__(*a, **kw)
        self._halaman, self._kop = [], kop

    def showPage(self):
        self._halaman.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._halaman)
        for keadaan in self._halaman:
            self.__dict__.update(keadaan)
            self._kop(self, self._pageNumber, total)
            super().showPage()
        super().save()


def _penggambar_kop(nomor: str, waktu: str, jenis: str):
    """Kop dan kaki di setiap halaman: logo + identitas proyek di kiri, jenis/nomor/waktu laporan di kanan."""
    lebar, tinggi = A4
    kiri, kanan = 18 * mm, lebar - 18 * mm

    def gambar(c, halaman: int, total: int):
        c.saveState()
        atas = tinggi - 12 * mm
        gambar_logo(c, kiri, atas - 19 * mm, 19 * mm)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(kiri + 23 * mm, atas - 7 * mm, "NUSANTARA SHIELD")
        c.setFont("Helvetica", 8.5)
        c.setFillColor(ABU)
        c.drawString(kiri + 23 * mm, atas - 11.5 * mm, "Posko Pertahanan Siber Luring \u00b7 v5.1")
        c.drawString(kiri + 23 * mm, atas - 15.5 * mm, "Bukti dulu, baru putus.")
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(kanan, atas - 6 * mm, ISTILAH["laporan"].upper())
        c.setFont("Helvetica", 8.5)
        c.drawRightString(kanan, atas - 10.5 * mm, f"Nomor: {nomor}")
        c.drawRightString(kanan, atas - 14.5 * mm, f"Dicetak: {waktu}")
        c.drawRightString(kanan, atas - 18.5 * mm, jenis)
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.6)
        c.line(kiri, atas - 22 * mm, kanan, atas - 22 * mm)
        c.setStrokeColor(HIJAU)
        c.setLineWidth(0.8)
        c.line(kiri, atas - 23.2 * mm, kanan, atas - 23.2 * mm)
        # kaki halaman
        c.setStrokeColor(colors.HexColor("#B8C0CC"))
        c.setLineWidth(0.4)
        c.line(kiri, 13 * mm, kanan, 13 * mm)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(ABU)
        c.drawString(kiri, 9 * mm, f"Nusantara Shield \u00b7 {nomor} \u00b7 dibuat otomatis oleh sistem \u00b7 "
                                    "dokumen latihan, seluruh data sintetis")
        c.drawRightString(kanan, 9 * mm, f"Halaman {halaman} dari {total}")
        c.restoreState()

    return gambar


def _blok_pengesahan(gaya) -> Table:
    """Dua kolom tanda tangan: Operator jaga yang membuat laporan, dan pejabat yang mengetahui."""
    mengetahui = " / ".join(reversed(nama_manajemen()))          # urutan dibalik: kepala seksi dulu, lalu komandan
    sel = lambda judul: [Paragraph(escape(judul), gaya["Normal"]), Spacer(1, 18 * mm),
                         Paragraph("( ........................................ )", gaya["Normal"]),
                         Paragraph("Nama, pangkat/NRP, tanggal", gaya["Normal"])]
    t = Table([[sel(ISTILAH["ttd_pembuat"]), sel(f"{ISTILAH['ttd_mengetahui']}, {mengetahui}")]],
              colWidths=[82 * mm, 82 * mm])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    return t


def buat_pdf(layanan: list[dict], hasil_audit: dict, pembuat: str, peringatan: list[dict] | None = None) -> bytes:
    gaya = getSampleStyleSheet()
    buffer = BytesIO()
    sekarang = datetime.now(timezone.utc)
    waktu = sekarang.strftime("%Y-%m-%d %H:%M UTC")
    nomor = f"LAPSIT/NS/{sekarang:%Y%m%d-%H%M%S}"
    jumlah_insiden = sum(1 for l in layanan if l.get("insiden"))
    jenis = f"Laporan insiden ({jumlah_insiden} aktif)" if jumlah_insiden else "Laporan rutin"
    dok = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=42 * mm, bottomMargin=20 * mm,
                            title=f"LAPSIT Nusantara Shield {nomor}", author="Nusantara Shield")
    isi = [
        Paragraph(f"Dibuat oleh akun: <b>{escape(pembuat)}</b>", gaya["Normal"]),
        Paragraph("<i>Dokumen latihan. Seluruh data sintetis, tidak memuat data pribadi; perintah ke perangkat "
                  "jaringan masih simulasi.</i>", gaya["Normal"]),
        Spacer(1, 8),
        Paragraph("1. Status layanan", gaya["Heading2"]),
    ]

    # Tabel status layanan (semua teks di-escape agar aman)
    baris = [["Layanan", "Status", "Backup terakhir", "Backup diuji"]]
    for l in layanan:
        baris.append([Paragraph(escape(l["nama"]), gaya["Normal"].clone("sel", fontSize=9, leading=11)),
                      l["status"].upper(),
                      f"{l['jam_sejak_backup']} jam lalu",
                      "Ya" if l["backup_teruji"] else "Belum"])
    tabel = Table(baris, colWidths=[78 * mm, 22 * mm, 36 * mm, 27 * mm])
    gaya_tabel = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2a3a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, l in enumerate(layanan, start=1):
        gaya_tabel.append(("TEXTCOLOR", (1, i), (1, i), WARNA_STATUS[l["status"]]))
    tabel.setStyle(TableStyle(gaya_tabel))
    isi += [tabel, Spacer(1, 10), Paragraph("2. Insiden aktif", gaya["Heading2"])]

    insiden = [l for l in layanan if l.get("insiden")]
    if not insiden:
        isi.append(Paragraph("Tidak ada insiden aktif.", gaya["Normal"]))
    for l in insiden:
        ins = l["insiden"]
        selesai = sum(ins["langkah_selesai"])
        isi.append(Paragraph(
            f"<b>{escape(l['nama'])}</b> — {escape(ins['judul'])} "
            f"(sejak {escape(ins['mulai'])}; playbook {selesai}/{len(ins['langkah'])} langkah)",
            gaya["Normal"]))
        attck = ringkas_mitre(ins.get("skenario"))
        if attck:
            isi.append(Paragraph(f"&nbsp;&nbsp;Teknik MITRE ATT&amp;CK: {escape(attck)}", gaya["Normal"]))
        for log in ins.get("log_peringatan", []):
            isi.append(Paragraph(f"&nbsp;&nbsp;<font color='#ad4f46'>[{escape(log['tingkat'].upper())}]</font> "
                                 f"{escape(log['waktu'])} — {escape(log['pesan'])}", gaya["Normal"]))
        for langkah, beres in zip(ins["langkah"], ins["langkah_selesai"]):
            tanda = "[x]" if beres else "[ ]"
            isi.append(Paragraph(f"&nbsp;&nbsp;{tanda} {escape(langkah)}", gaya["Normal"]))

    isi += [Spacer(1, 10), Paragraph("3. Peringatan terbaru", gaya["Heading2"])]
    if not peringatan:
        isi.append(Paragraph("Tidak ada peringatan.", gaya["Normal"]))
    else:
        kecil = gaya["Normal"].clone("kecil", fontSize=8, leading=10)
        baris = [["Keparahan", "Peringatan", "Teknik ATT&CK", "Status"]]
        for p in peringatan:
            teks = escape(p["judul"]) + (f"<br/><i>{escape(p['sumber_data'])}</i>" if p.get("sumber_data") else "")
            baris.append([p["keparahan"].upper(), Paragraph(teks, kecil),
                          Paragraph(escape(", ".join(m["id"] for m in p.get("mitre", [])) or "—"), kecil),
                          Paragraph(escape(p["status"]), kecil)])
        t = Table(baris, colWidths=[20 * mm, 78 * mm, 26 * mm, 40 * mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2a3a")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        isi += [t, Paragraph("<i>Teknik MITRE ATT&amp;CK® dipetakan tim sendiri sebagai rujukan, bukan sertifikasi. "
                             "MITRE ATT&amp;CK® adalah merek dagang The MITRE Corporation.</i>", kecil)]

    isi += [Spacer(1, 10), Paragraph("4. Integritas log audit", gaya["Heading2"]),
            Paragraph(escape(hasil_audit["pesan"]) + f" ({hasil_audit['jumlah']} entri)",
                      gaya["Normal"])]
    if hasil_audit.get("hash_terakhir"):
        isi.append(Paragraph(f"Sidik jari terakhir: <font face='Courier' size='7'>"
                             f"{escape(hasil_audit['hash_terakhir'])}</font>", gaya["Normal"]))
    isi += [Spacer(1, 12), KeepTogether([Paragraph(f"5. {escape(ISTILAH['ttd_judul'])}", gaya["Heading2"]),
                                         _blok_pengesahan(gaya)])]   # judul dan kotak tanda tangan tidak terpisah halaman
    kop = _penggambar_kop(nomor, waktu, jenis)
    dok.build(isi, canvasmaker=lambda *a, **kw: _KanvasBernomor(*a, kop=kop, **kw))
    return buffer.getvalue()
