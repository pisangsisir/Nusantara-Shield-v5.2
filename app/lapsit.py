"""
lapsit.py — Membuat laporan situasi dalam format PDF (label resmi diambil dari kamus istilah).

Analogi: notulen rapat darurat yang dicetak otomatis. Isinya ringkasan
status semua layanan, insiden yang sedang berjalan, dan bukti bahwa buku
catatan audit masih utuh.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

WARNA_STATUS = {"hijau": colors.HexColor("#1f8a4c"),
                "kuning": colors.HexColor("#b7791f"),
                "merah": colors.HexColor("#c0392b")}


def buat_pdf(layanan: list[dict], hasil_audit: dict, pembuat: str) -> bytes:
    gaya = getSampleStyleSheet()
    buffer = BytesIO()
    dok = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="LAPSIT Nusantara Shield", author="Nusantara Shield")
    waktu = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    isi = [
        Paragraph("LAPSIT — Nusantara Shield", gaya["Title"]),
        Paragraph(f"Dibuat: {escape(waktu)} · oleh akun: {escape(pembuat)}", gaya["Normal"]),
        Paragraph("<i>Dokumen demo. Seluruh data sintetis, tidak memuat data pribadi.</i>",
                  gaya["Normal"]),
        Spacer(1, 8),
        Paragraph("1. Status layanan", gaya["Heading2"]),
    ]

    # Tabel status layanan (semua teks di-escape agar aman)
    baris = [["Layanan", "Status", "Backup terakhir", "Backup diuji"]]
    for l in layanan:
        baris.append([l["nama"], l["status"].upper(),
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
        for log in ins.get("log_peringatan", []):
            isi.append(Paragraph(f"&nbsp;&nbsp;<font color='#ad4f46'>[{escape(log['tingkat'].upper())}]</font> "
                                 f"{escape(log['waktu'])} — {escape(log['pesan'])}", gaya["Normal"]))
        for langkah, beres in zip(ins["langkah"], ins["langkah_selesai"]):
            tanda = "[x]" if beres else "[ ]"
            isi.append(Paragraph(f"&nbsp;&nbsp;{tanda} {escape(langkah)}", gaya["Normal"]))

    isi += [Spacer(1, 10), Paragraph("3. Integritas log audit", gaya["Heading2"]),
            Paragraph(escape(hasil_audit["pesan"]) + f" ({hasil_audit['jumlah']} entri)",
                      gaya["Normal"])]
    if hasil_audit.get("hash_terakhir"):
        isi.append(Paragraph(f"Sidik jari terakhir: <font face='Courier' size='7'>"
                             f"{escape(hasil_audit['hash_terakhir'])}</font>", gaya["Normal"]))
    dok.build(isi)
    return buffer.getvalue()
