/* ==========================================================================
   radar.js — Pemindai Port/Anomali berbasis HTML5 Canvas murni.
   Analogi: penjaga malam bersenter.
   - SERVER memberi tahu: di mana setiap benda (sudut & jarak), warnanya, dan
     seberapa cepat penjaga harus berputar (putaran_ms).
   - BROWSER hanya memutar senter dan menyalakan benda yang tersorot.
   Dipakai oleh app.js lewat: Radar.init(), Radar.aturTitik(), Radar.aturPutaran().
   Fase 3 (R3): tidak lagi punya loop requestAnimationFrame sendiri. Bingkai digerakkan Penjadwal
   (penjadwal.js) yang hanya berjalan saat kanvas terlihat di layar DAN tab sedang aktif.
   Sapuan senter dirender sekali ke sprite lalu cukup diputar; tooltip hanya menyentuh DOM bila
   titik yang ditunjuk berganti.
   ========================================================================== */
"use strict";

const Radar = (() => {
  const TAU = Math.PI * 2;
  const WARNA = { normal: "62,240,161", waspada: "242,193,78", kritis: "255,92,116", isolasi: "122,162,214" };
  // Fase 5 (audit #4): arti setiap dimensi titik, dipakai tooltip & legenda
  const ZONA = {
    internal: { nama: "Internal", cincin: "cincin dalam", arti: "di dalam markas, tidak terlihat dari internet" },
    dmz:      { nama: "DMZ", cincin: "cincin tengah", arti: "server yang sengaja menghadap internet (portal, API)" },
    luar:     { nama: "Luar gerbang", cincin: "cincin luar", arti: "internet / pihak luar, termasuk sumber serangan" },
  };
  const STATUS = { normal: "Normal", waspada: "Berisiko", kritis: "Ancaman", isolasi: "Diblokir / diisolasi" };
  const zonaDariR = (r) => (r <= 0.5 ? "internal" : r <= 0.75 ? "dmz" : "luar");   // batas = cincin 50% & 75%
  const FONT = "10px ui-monospace, Menlo, Consolas, monospace";
  const EKOR = 1.05;                          // panjang ekor cahaya senter (radian)
  const lambat = matchMedia("(prefers-reduced-motion: reduce)").matches;

  let canvas, ctx, tip, latar, lctx;          // latar = kanvas cadangan untuk bagian diam
  let sapuan = null;                          // Fase 3: sprite sapuan senter (dibuat ulang hanya saat ukuran berubah)
  let tipTerakhir = null;                     // Fase 3: titik yang sedang ditampilkan tooltip-nya
  let W = 0, H = 0, R = 0, cx = 0, cy = 0, dpr = 1;
  let putaranMs = 4000, kecepatan = TAU / putaranMs, pudarMs = putaranMs * 0.85;
  let sudut = -Math.PI / 2;                   // mulai dari arah jam 12
  let berjalan = true, mouse = null;
  let titik = [];                             // daftar benda dari server

  // 1) Ukur ulang saat kotak berubah ukuran; tajam di layar retina
  function ukur() {
    const kotak = canvas.getBoundingClientRect();
    if (!kotak.width) { W = 0; return; }        // kotak tersembunyi (mis. layar login): Penjadwal tidak memanggil kita
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = kotak.width; H = kotak.height;
    for (const c of [canvas, latar]) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    lctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = W / 2; cy = H / 2; R = Math.min(W, H) / 2 - 16;
    gambarLatar();
    sapuan = buatSpriteSapuan();
  }

  // 2b) Sprite sapuan: kipas bergradasi untuk sudut 0, digambar SEKALI per ukuran (bukan tiap bingkai)
  function buatSpriteSapuan() {
    const sisi = Math.ceil((R + 2) * 2 * dpr), c = document.createElement("canvas");
    c.width = c.height = sisi;
    const g = c.getContext("2d"), p = sisi / 2;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const o = p / dpr;                         // pusat dalam satuan CSS px
    if (g.createConicGradient) {
      const gr = g.createConicGradient(-EKOR, o, o);
      gr.addColorStop(0, "rgba(62,240,161,0)");
      gr.addColorStop(EKOR / TAU, "rgba(62,240,161,.30)");
      gr.addColorStop(Math.min(1, EKOR / TAU + 0.001), "rgba(62,240,161,0)");
      g.fillStyle = gr;
      g.beginPath(); g.moveTo(o, o); g.arc(o, o, R, -EKOR, 0); g.closePath(); g.fill();
    } else {                                   // cadangan browser lama: 14 irisan
      const N = 14;
      for (let i = 0; i < N; i++) {
        g.fillStyle = `rgba(62,240,161,${((0.3 * (i + 1)) / N).toFixed(3)})`;
        g.beginPath(); g.moveTo(o, o);
        g.arc(o, o, R, -EKOR + (EKOR * i) / N, -EKOR + (EKOR * (i + 1)) / N + 0.01);
        g.closePath(); g.fill();
      }
    }
    return c;
  }

  // 2) Bagian yang TIDAK bergerak digambar SEKALI (lingkaran, sumbu, label zona)
  function gambarLatar() {
    lctx.clearRect(0, 0, W, H);
    const g = lctx.createRadialGradient(cx, cy, 0, cx, cy, R);
    g.addColorStop(0, "rgba(62,240,161,.08)"); g.addColorStop(1, "rgba(62,240,161,.015)");
    lctx.fillStyle = g; lctx.beginPath(); lctx.arc(cx, cy, R, 0, TAU); lctx.fill();
    // Fase 5: tiga pita zona diberi rona berbeda agar "jarak = zona" langsung terbaca
    [[0.75, 1, "255,92,116,.05"], [0.5, 0.75, "242,193,78,.05"]].forEach(([a, b, c]) => {
      lctx.fillStyle = `rgba(${c})`;
      lctx.beginPath(); lctx.arc(cx, cy, R * b, 0, TAU); lctx.arc(cx, cy, R * a, 0, TAU, true); lctx.fill();
    });
    lctx.lineWidth = 1;
    [0.25, 0.5, 0.75, 1].forEach((f) => {
      lctx.strokeStyle = f === 0.5 || f === 0.75 ? "rgba(62,240,161,.32)" : "rgba(62,240,161,.16)";
      lctx.beginPath(); lctx.arc(cx, cy, R * f, 0, TAU); lctx.stroke();
    });
    lctx.strokeStyle = "rgba(62,240,161,.10)";
    lctx.beginPath();
    lctx.moveTo(cx - R, cy); lctx.lineTo(cx + R, cy);
    lctx.moveTo(cx, cy - R); lctx.lineTo(cx, cy + R);
    lctx.stroke();
    lctx.strokeStyle = "rgba(62,240,161,.28)";
    for (let d = 0; d < 360; d += 10) {
      const a = (d * Math.PI) / 180, p = d % 30 === 0 ? 8 : 4;
      lctx.beginPath();
      lctx.moveTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
      lctx.lineTo(cx + Math.cos(a) * (R - p), cy + Math.sin(a) * (R - p));
      lctx.stroke();
    }
    lctx.font = FONT; lctx.fillStyle = "rgba(135,152,177,.85)"; lctx.textAlign = "left";
    lctx.fillText("INTERNAL", cx + 5, cy - R * 0.5 + 12);
    lctx.fillText("DMZ", cx + 5, cy - R * 0.75 + 12);
    lctx.fillText("LUAR GERBANG", cx + 5, cy - R + 12);
    lctx.textAlign = "center"; lctx.fillStyle = "rgba(135,152,177,.6)";
    lctx.fillText("MARKAS", cx, cy + 16);
  }

  // 3) Sorotan senter: sprite diputar ke sudut sekarang + garis depan terang
  function gambarSapuan() {
    const sisi = (R + 2) * 2;
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(sudut);
    ctx.drawImage(sapuan, -sisi / 2, -sisi / 2, sisi, sisi);
    ctx.restore();
    const ex = cx + Math.cos(sudut) * R, ey = cy + Math.sin(sudut) * R;
    ctx.lineCap = "round";
    ctx.strokeStyle = "rgba(62,240,161,.18)"; ctx.lineWidth = 6;   // pendar murah (tanpa shadowBlur)
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke();
    ctx.strokeStyle = "rgba(62,240,161,.95)"; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke();
  }

  // 4) Satu benda: inti + riak yang melebar saat baru tersorot
  function gambarTitik(b, hidup) {
    const x = cx + Math.cos(b.sudut) * b.r * R, y = cy + Math.sin(b.sudut) * b.r * R;
    b.x = x; b.y = y; b.hidup = hidup;
    const c = WARNA[b.status] || WARNA.normal, umur = 1 - hidup;
    if (umur < 0.6) {
      ctx.strokeStyle = `rgba(${c},${((0.6 - umur) * 0.8).toFixed(3)})`; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(x, y, 4 + umur * 18, 0, TAU); ctx.stroke();
    }
    if (b.prob >= 50) {                           // v3: aset yang DIPREDIKSI diserang (CTI) → cincin kuning putus-putus
      ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
      ctx.strokeStyle = `rgba(242,193,78,${Math.max(0.25, hidup * 0.8).toFixed(3)})`;
      ctx.beginPath(); ctx.arc(x, y, 9, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.fillStyle = `rgba(${c},${hidup.toFixed(3)})`;
    if (b.status === "isolasi") {               // diblokir: kotak kecil, bukan bulatan
      ctx.fillRect(x - 3, y - 3, 6, 6);
    } else {
      ctx.beginPath(); ctx.arc(x, y, b.status === "normal" ? 2.6 : 3.6, 0, TAU); ctx.fill();
    }
  }

  // 5) Satu bingkai. Dipanggil Penjadwal HANYA saat kanvas terlihat & tab aktif (dt sudah dibatasi 50 ms).
  function bingkai(t, dt) {
    const langkah = kecepatan * dt;
    sudut = (sudut + langkah) % TAU;

    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(latar, 0, 0, W, H);         // tempel bagian diam (murah)
    gambarSapuan();
    for (const b of titik) {
      // Apakah senter melewati sudut benda ini di antara bingkai lalu dan sekarang?
      const selisih = (((sudut - b.sudut) % TAU) + TAU) % TAU;
      if (selisih <= langkah) b.hit = t;
      let hidup = 1 - (t - b.hit) / pudarMs;
      if (b.status === "kritis" && b.hit > 0) hidup = Math.max(hidup, 0.2); // ancaman tetap ditandai samar
      if (hidup > 0) gambarTitik(b, hidup); else b.hidup = 0;
    }
    ctx.fillStyle = "rgba(62,240,161,.9)";
    ctx.beginPath(); ctx.arc(cx, cy, 3, 0, TAU); ctx.fill();
    if (mouse) perbaruiTip();
  }

  function perbaruiTip() {
    let dekat = null, jarak = 14;
    for (const b of titik) {
      if (!(b.hidup > 0.05)) continue;
      const d = Math.hypot(b.x - mouse.x, b.y - mouse.y);
      if (d < jarak) { jarak = d; dekat = b; }
    }
    // Tidak dekat titik mana pun tetapi di dalam radar → jelaskan ZONA di bawah kursor
    const jarakPusat = Math.hypot(mouse.x - cx, mouse.y - cy) / R;
    const target = dekat || (jarakPusat <= 1 ? `zona:${zonaDariR(jarakPusat)}` : null);
    if (target === tipTerakhir) {             // Fase 3: tidak ada perubahan = DOM tidak disentuh
      if (typeof target === "string") { tip.style.left = `${mouse.x}px`; tip.style.top = `${mouse.y}px`; }
      return;
    }
    tipTerakhir = target;
    if (!target) { tip.classList.remove("tampil"); return; }
    const baris = (kelas, teks) => { const d = document.createElement("div"); if (kelas) d.className = kelas; d.textContent = teks; return d; };
    if (!dekat) {
      const z = ZONA[target.slice(5)];
      tip.replaceChildren(baris("judul-tip", `Zona ${z.nama} (${z.cincin})`), baris(null, z.arti),
        baris("redup", "Arahkan kursor ke titik untuk rinciannya"));
      tip.dataset.status = "zona";
      tip.style.left = `${mouse.x}px`; tip.style.top = `${mouse.y}px`;
    } else {
      const z = ZONA[dekat.zona || zonaDariR(dekat.r)];
      const isi = [
        baris("judul-tip", dekat.nama),
        baris("ip", `${dekat.ip}${dekat.port ? `:${dekat.port}` : ""}`),
        baris(null, `Zona: ${z.nama} · ${z.cincin}`),
        baris(`status-tip ${dekat.status}`, `Status: ${STATUS[dekat.status] || dekat.status}`),
      ];
      const label = STATUS[dekat.status] || "";
      if (dekat.catatan && !label.toLowerCase().startsWith(dekat.catatan.toLowerCase())) isi.push(baris("redup", dekat.catatan));
      if (dekat.prob >= 50) isi.push(baris("prediksi-tip", `Prediksi CTI: ${dekat.prob}% diserang (cincin putus-putus)`));
      tip.replaceChildren(...isi);
      tip.dataset.status = dekat.status;
      tip.style.left = `${dekat.x}px`; tip.style.top = `${dekat.y}px`;
    }
    tip.classList.add("tampil");
  }

  const mulai = () => Penjadwal.bangun();

  return {
    init(elCanvas, elKotak, elTip) {
      canvas = elCanvas; tip = elTip; ctx = canvas.getContext("2d");
      latar = document.createElement("canvas"); lctx = latar.getContext("2d");
      const arahkan = (e) => {
        const k = canvas.getBoundingClientRect();
        mouse = { x: e.clientX - k.left, y: e.clientY - k.top };
        if (!berjalan) perbaruiTip();          // radar dijeda: tooltip tetap berfungsi tanpa bingkai baru
      };
      canvas.addEventListener("pointermove", arahkan);
      canvas.addEventListener("pointerdown", arahkan);   // layar sentuh: ketuk titik untuk rinciannya
      canvas.addEventListener("pointerleave", () => { mouse = null; tipTerakhir = null; tip.classList.remove("tampil"); });
      new ResizeObserver(() => { ukur(); mulai(); }).observe(elKotak);
      // Hemat baterai & GPU: digambar hanya bila terlihat di layar, tab aktif, tidak dijeda, dan berukuran
      Penjadwal.daftar("radar", { elemen: canvas, gambar: bingkai, boleh: () => berjalan && W > 0 });
    },
    /** Data dari server. Waktu "tersorot" titik lama dipertahankan agar tidak berkedip. */
    aturTitik(daftar) {
      const lama = new Map(titik.map((b) => [b.ip, b]));
      titik = daftar.map((b) => ({ ...b, hit: lama.get(b.ip)?.hit ?? -1e9, hidup: 0 }));
      tipTerakhir = null;                     // objek titik baru: tooltip dihitung ulang
    },
    /** Kecepatan dari server: makin genting, makin cepat penjaga berputar. */
    aturPutaran(ms) {
      putaranMs = ms * (lambat ? 2.5 : 1);
      kecepatan = TAU / putaranMs;
      pudarMs = putaranMs * 0.85;
      return putaranMs;
    },
    alih() { berjalan = !berjalan; if (berjalan) mulai(); return berjalan; },   // dijeda = Penjadwal melewatinya
    mulai,
  };
})();
